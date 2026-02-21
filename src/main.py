from __future__ import annotations

import signal
import time
from pathlib import Path
from typing import Dict, Optional
from collections import deque

import cv2
import numpy as np

from config.config import AppConfig, load_config
from src.alert.alert_manager import AlertManager
from src.alert.firebase_client import FirebaseClient, FirebaseConfig
from src.alert.notifier import Notifier
from src.dashboard.stream_manager import stream_manager
from src.detection.detector import YoloV8Detector
from src.features.motion_metrics import MotionFeature, MotionFeatureExtractor
from src.features.ttc_estimator import TimeToCollisionEstimator
from src.risk.heuristics import RiskHeuristics
from src.risk.risk_engine import RiskEngine
from src.sensors.gps_handler import GPSHandler, Location
from src.sensors.imu_handler import IMUHandler
from src.storage.event_logger import EventLogger
from src.storage.media_manager import MediaManager
from src.tracking.tracker import MultiObjectTracker, TrackerConfig
from src.utils.logger import get_logger, setup_logger
from src.utils.video_buffer import RingBufferRecorder


class AccidentDetectionPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        log_dir = Path(config.paths.log_dir_abs)
        setup_logger("pipeline", log_dir)
        self.logger = get_logger("pipeline", log_dir)

        self.detector = YoloV8Detector(
            model_path=Path(config.model.path),
            class_names=config.model.classes,
            conf_threshold=config.model.conf_threshold,
            iou_threshold=config.model.iou_threshold,
            providers=config.model.providers,
            log_dir=log_dir,
        )
        self.tracker = MultiObjectTracker(
            config=TrackerConfig(
                track_buffer=config.tracker.track_buffer,
                match_threshold=config.tracker.match_threshold,
                frame_rate=config.stream.fps,
                min_box_area=config.tracker.min_box_area,
            ),
            log_dir=log_dir,
        )

        self.motion = MotionFeatureExtractor(
            max_history=config.features.history,
            fps=config.stream.fps,
        )
        self.ttc = TimeToCollisionEstimator(max_distance=config.features.max_ttc_distance)
        self.risk_engine = RiskEngine(
            heuristics=RiskHeuristics(
                thresholds=config.risk.thresholds,
                weights=config.risk.weights,
            ),
            log_dir=log_dir,
        )

        self.ring_buffer = RingBufferRecorder(
            fps=config.stream.fps,
            seconds=config.alert.clip_seconds,
            resolution=tuple(config.stream.resolution),
            codec=config.alert.clip_codec,
            log_dir=log_dir,
        )

        self.media_manager = MediaManager(Path(config.paths.media_dir_abs), log_dir=log_dir)
        self.event_logger = EventLogger(Path(config.paths.event_log_abs), log_dir=log_dir)
        firebase_client = None
        if config.firebase:
            firebase_client = FirebaseClient(
                FirebaseConfig(**config.firebase.model_dump()), log_dir=log_dir
            )
        self.notifier = Notifier(
            sms_enabled=config.alert.sms_enabled,
            whatsapp_enabled=config.alert.whatsapp_enabled,
            twilio_sid=config.alert.twilio_sid,
            twilio_token=config.alert.twilio_token,
            sms_from=config.alert.sms_from,
            whatsapp_from=config.alert.whatsapp_from,
            sms_to=config.alert.sms_to,
            whatsapp_to=config.alert.whatsapp_to,
            email_to=config.alert.email_to,
            email_host=config.alert.email_host,
            email_port=config.alert.email_port,
            email_user=config.alert.email_user,
            email_password=config.alert.email_password,
            log_dir=log_dir,
        )
        self.alert_manager = AlertManager(
            media_manager=self.media_manager,
            event_logger=self.event_logger,
            notifier=self.notifier,
            firebase_client=firebase_client,
            clip_buffer=self.ring_buffer,
            log_dir=log_dir,
            cooldown_seconds=config.alert.cooldown_seconds,
        )

        self.imu_handler = IMUHandler(log_dir=log_dir) if config.hardware.use_imu else None
        self.gps_handler = GPSHandler(log_dir=log_dir) if config.hardware.use_gps else None
        self.video_source = config.stream.video_source
        self.stop_requested = False
        self.last_gps: Optional[Location] = None
        self.last_imu_jerk = 0.0
        self.last_imu_time = 0.0
        self.last_imu_time = 0.0
        self.last_gps_time = 0.0
        self.track_history: Dict[int, list] = {}
        self.risk_history = {}
        
        # UI Persistence State
        self.active_alerts: Dict[int, dict] = {} # track_id -> {expiry: float, text: str, color: tuple}
        self.accident_end_time = 0.0
        
        # New State
        self.frame_count = 0
        self.night_mode_active = False

    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        capture = cv2.VideoCapture(self.video_source)
        if not capture.isOpened():
            self.logger.error("Failed to open video source %s", self.video_source)
            return

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.stream.resolution[0])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.stream.resolution[1])
        capture.set(cv2.CAP_PROP_FPS, self.config.stream.fps)

        # Check if video source is a file (not webcam)
        is_video_file = isinstance(self.video_source, (str, Path)) and Path(self.video_source).exists()
        consecutive_failures = 0
        max_failures = 10  # Allow 10 retries before giving up
        
        self.logger.info("Pipeline started. Press Ctrl+C to exit.")
        while not self.stop_requested:
            try:
                if stream_manager.is_paused():
                    time.sleep(0.1)
                    continue

                ret, frame = capture.read()
                if not ret:
                    if is_video_file:
                        self.logger.info("Video ended. Restarting...")
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        if capture.get(cv2.CAP_PROP_POS_FRAMES) != 0:
                             capture.release()
                             capture = cv2.VideoCapture(self.video_source)
                        continue
                    else:
                        time.sleep(0.5)
                        continue

                if frame is None or frame.size == 0:
                    continue
                
                if frame is None or frame.size == 0:
                    continue
                
                self.frame_count += 1

                # --- AUTO NIGHT MODE (Low-Light Enhancement) ---
                # Check brightness (Value channel of HSV) periodically to save CPU
                if self.frame_count % 30 == 0: 
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    brightness = hsv[..., 2].mean()
                    # If very dark (< 60), enable Night Mode
                    # If bright enough (> 70), disable it (hysteresis)
                    if self.night_mode_active and brightness > 70:
                        self.night_mode_active = False
                    elif not self.night_mode_active and brightness < 60:
                        self.night_mode_active = True

                if self.night_mode_active:
                     # Apply Gamma Correction (Boost dark areas)
                     invGamma = 1.0 / 1.5
                     table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
                     frame = cv2.LUT(frame, table)
                     
                     # Add "NIGHT VISION" text to frame (top right under HUD)
                     cv2.putText(frame, "NIGHT VISION ACTIVE", (frame.shape[1] - 180, 150), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                # -----------------------------------------------

                timestamp = time.time()
                self._update_sensors(timestamp)
                
                # Robust Detection
                try:
                    detections = self.detector.infer(frame)
                    tracks = self.tracker.update(detections)
                except Exception as e:
                    self.logger.error(f"Detection/Tracking error: {e}")
                    detections = []
                    tracks = []
                
                # Update History
                try:
                    active_ids = set()
                    for t in tracks:
                        active_ids.add(t.track_id)
                        pts = self.track_history.setdefault(t.track_id, [])
                        center = (int((t.bbox[0]+t.bbox[2])/2), int((t.bbox[1]+t.bbox[3])/2))
                        pts.append(center)
                        if len(pts) > 30: 
                            pts.pop(0)
                    self.track_history = {k: v for k, v in self.track_history.items() if k in active_ids}
                except: pass

                # Analysis
                assessments = []
                try:
                    self.motion.clear_stale({t.track_id for t in tracks})
                    track_feature_map: Dict[int, MotionFeature] = {}
                    for track in tracks:
                        feature = self.motion.update(track, timestamp)
                        track_feature_map[track.track_id] = feature

                    ttc_results = self.ttc.compute_pairwise(tracks)
                    assessments = self.risk_engine.evaluate(
                        tracks=tracks,
                        motion_features=track_feature_map,
                        ttc_results=ttc_results,
                        timestamp=timestamp,
                    )
                except Exception as e:
                    self.logger.error(f"Analysis error: {e}")

                self._update_ring_buffer(frame)
                
                # Alerting
                try:
                    for assessment in assessments:
                        if assessment.risk_level in ("high", "critical") or self.last_imu_jerk > self.config.risk.imu_jerk_threshold:
                            track_obj = next((t for t in tracks if t.track_id == assessment.track_id), None)
                            if track_obj:
                                self.alert_manager.handle_risk_event(
                                    assessment=assessment,
                                    track=track_obj,
                                    frame=frame,
                                    location=self.last_gps,
                                )
                                

                except: pass

                # Annotation & Render (Must happen!)
                try:
                    annotated = self._annotate(frame, tracks, assessments)
                except Exception as e:
                    self.logger.error(f"Annotation error: {e}")
                    annotated = frame # Fallback to raw frame

                stream_manager.publish(annotated)

                if self.config.stream.display:
                    self._render(annotated)

            except Exception as e:
                self.logger.error(f"Critical Loop Error: {e}")
                continue

        capture.release()
        cv2.destroyAllWindows()
        self.logger.info("Pipeline stopped.")

    def _update_ring_buffer(self, frame) -> None:
        success, encoded = cv2.imencode(".jpg", frame)
        if success:
            self.ring_buffer.append_frame(encoded.tobytes())

    def _annotate(self, frame, tracks, assessments):
        annotated = frame.copy()
        risk_map = {a.track_id: a for a in assessments}
        current_time = time.time()
        
        # 0. Check for Accident / Critical Risk (Sticky)
        # Update Risk History (Debounce/Smoothing)
        for t in tracks:
            rid = t.track_id
            if rid not in self.risk_history:
                self.risk_history[rid] = deque(maxlen=5) # Keep last 5 frames
            
            # Check if this track has High/Critical risk THIS frame
            current_risk_val = 0.0
            if rid in risk_map:
                r = risk_map[rid]
                if r.risk_score > 0.8:
                    current_risk_val = r.risk_score
            
            self.risk_history[rid].append(current_risk_val)

        # Determine Global Accident State based on Smoothed History
        current_accident = False
        max_risk = 0.0
        
        for rid, risk_queue in self.risk_history.items():
            # Count how many frames had High Risk (>0.8)
            hits = sum(1 for r in risk_queue if r > 0.8)
            
            if hits >= 2: # 2/5 is enough for fast impacts
                # Use the max score from the queue to trigger
                avg_score = sum(risk_queue) / len(risk_queue)
                
                # Trigger massive banner for Confirmed Accident (Smoothed)
                # 1.2 confirms High Risk sustained.
                if avg_score > 1.2: 
                    current_accident = True

        # Update Stickiness
        if current_accident:
            self.accident_end_time = current_time + 3.0 # Short alert (3s) to not block view
        
        accident_detected = (current_time < self.accident_end_time)

        # 1. Draw Motion Vectors (Subtle)
        try:
            self._draw_vectors(annotated, tracks, risk_map)
        except Exception as e:
            print(f"Error drawing vectors: {e}")

        # 2. Draw HUD (Compact & Top-Right)
        try:
            self._draw_hud(annotated, tracks, accident_detected)
        except Exception as e:
            pass

        # 3. Draw Bounding Boxes and Labels
        for track in tracks:
            # Extract bbox coordinates FIRST
            x1, y1, x2, y2 = track.bbox.astype(int)
            
            # Safe class name
            cls_name = track.class_name if track.class_name else "Unknown"
            
            # Determine Risk & Color FIRST
            risk = risk_map.get(track.track_id)
            if risk:
                color = risk.color
                label = f"ID {track.track_id} | {risk.risk_level.upper()} ({risk.risk_score:.1f})"
            else:
                color = (0, 255, 0) # Default green
                label = f"ID {track.track_id}"

            # Add Speed if available
            if track.track_id in self.motion.features:
                 feat = self.motion.features[track.track_id]
                 if feat:
                    label += f" | {int(feat.speed_kmh)}km/h"
            
            # Special Alert for Wrong Way
            if risk and any("WRONG WAY" in r for r in risk.reasons):
                 # Flashing Red Text above box
                 if int(time.time() * 6) % 2 == 0: # Fast Flash
                     cv2.putText(annotated, "WRONG WAY!", (x1, y1 - 45), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3, cv2.LINE_AA)

            # Special Alert for Stopped Vehicles
            # Check reasons for string formatted "STOPPED {x}s"
            stopped_reason = next((r for r in (risk.reasons if risk else []) if "STOPPED" in r), None)
            if stopped_reason:
                # Extract Duration
                try:
                    # Extract number from "STOPPED 7s"
                    duration_s = int(''.join(filter(str.isdigit, stopped_reason)))
                except:
                    duration_s = 0
                
                # Format: 00:04
                timer_str = f"STOPPED 00:{duration_s:02d}"
                
                # Color: Yellow if warning, Red if hazard
                timer_color = (0, 255, 255) if "HAZARD" not in stopped_reason else (0, 0, 255)
                
                # Draw Timer styling
                # Small box above car
                (tw, th), _ = cv2.getTextSize(timer_str, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, y1 - 40), (x1 + tw + 10, y1 - 10), (50, 50, 50), -1)
                cv2.putText(annotated, timer_str, (x1 + 5, y1 - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, timer_color, 2, cv2.LINE_AA)
            
            # Draw Box (Futuristic Corners)
            l = 20 # Corner length
            t = 2  # Thickness
            
            # Top-Left
            cv2.line(annotated, (x1, y1), (x1 + l, y1), color, t)
            cv2.line(annotated, (x1, y1), (x1, y1 + l), color, t)
            # Top-Right
            cv2.line(annotated, (x2, y1), (x2 - l, y1), color, t)
            cv2.line(annotated, (x2, y1), (x2, y1 + l), color, t)
            # Bottom-Left
            cv2.line(annotated, (x1, y2), (x1 + l, y2), color, t)
            cv2.line(annotated, (x1, y2), (x1, y2 - l), color, t)
            # Bottom-Right
            cv2.line(annotated, (x2, y2), (x2 - l, y2), color, t)
            cv2.line(annotated, (x2, y2), (x2, y2 - l), color, t)

            # Draw Label
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - 20), (x1 + tw + 10, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # 4. Draw Risk Alert Panel (Persistent / Sticky)
        try:
            # Update Active Alerts
            for assessment in assessments:
                if assessment.risk_level in ("low", "medium"): continue
                
                # Format
                info = f"WARNING: {assessment.risk_level.upper()} | ID {assessment.track_id}"
                if assessment.risk_level == "critical":
                    info = f"CRITICAL: ID {assessment.track_id} | {', '.join(assessment.reasons)}"
                
                # Add/Refresh alert (keep for 4 seconds)
                self.active_alerts[assessment.track_id] = {
                    "expiry": current_time + 4.0, 
                    "text": info,
                    "color": assessment.color
                }
            
            # Cleanup Expired
            expired = [tid for tid, data in self.active_alerts.items() if current_time > data["expiry"]]
            for tid in expired:
                del self.active_alerts[tid]
        except: pass
            
        # 4. Draw Risk Alert Panel (Persistent / Sticky)
        try:
            # Filter for Medium/High/Critical
            critical_alerts = [
                (tid, r) for tid, r in risk_map.items() 
                if r.risk_level in ("medium", "high", "critical") and r.risk_score > 0.4
            ]
            
            # Sort by Score (Highest first)
            critical_alerts.sort(key=lambda x: x[1].risk_score, reverse=True)
            
            # Show MAX 1 alert to avoid clutter
            if critical_alerts:
                tid, r = critical_alerts[0]
                
                # Dynamic Color
                color = r.color
                text_color = (255, 255, 255)
                
                reason_str = ", ".join(r.reasons)
                # Shorten reason
                if "COLLISION" in reason_str: reason_str = "COLLISION IMMINENT"
                elif "IMPACT" in reason_str: reason_str = "IMPACT DETECTED"
                
                msg = f"ALERT: ID {tid} | {reason_str}"
                
                # Draw sleek bottom panel
                h, w = annotated.shape[:2]
                panel_h = 40
                y_pos = h - 60
                
                # Semi-transparent dark strip
                overlay = annotated.copy()
                cv2.rectangle(overlay, (0, y_pos), (w, y_pos + panel_h), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0, annotated)
                
                # Text
                (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cx = w // 2
                cv2.putText(annotated, msg, (cx - tw//2, y_pos + 28), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
                
                # Accent Line
                cv2.line(annotated, (0, y_pos), (w, y_pos), color, 2)

        except Exception as e:
            self.logger.error(f"Alert draw error: {e}")   

        # 5. System Status (Top Left) - Minimal
        cv2.putText(annotated, "REC  |  AI ACTIVE", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1, cv2.LINE_AA)

        # 6. ACCIDENT BANNER (REFINED)
        if accident_detected:
            h, w = annotated.shape[:2]
            
            # Strobe logic: Pulsing Border Only (Subtle)
            t_now = time.time()
            alpha = (np.sin(t_now * 8) + 1) / 2 # 0.0 to 1.0
            border_color = (0, 0, 255) 
            
            # Draw subtle vignettes/borders top and bottom
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (w, 50), border_color, -1)
            cv2.rectangle(overlay, (0, h-50), (w, h), border_color, -1)
            cv2.addWeighted(overlay, 0.3 * alpha, annotated, 1.0, 0, annotated)

            # Elegant Central Box
            box_w, box_h = 400, 60
            cx, cy = w // 2, 80
            
            # Glassmorphic Box
            overlay = annotated.copy()
            # Dark bg with high transparency
            cv2.rectangle(overlay, (cx - box_w//2, cy - box_h//2), (cx + box_w//2, cy + box_h//2), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.8, annotated, 0.2, 0, annotated)
            
            # Border
            cv2.rectangle(annotated, (cx - box_w//2, cy - box_h//2), (cx + box_w//2, cy + box_h//2), (50, 50, 200), 2)
            
            # Text
            text = "ACCIDENT DETECTED"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
            cv2.putText(annotated, text, (cx - tw//2, cy + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
            
            # Warning Icon (Text based)
            cv2.putText(annotated, "!", (cx - box_w//2 + 20, cy + 10), cv2.FONT_HERSHEY_COMPLEX, 1.0, (0, 0, 255), 2)
            cv2.putText(annotated, "!", (cx + box_w//2 - 40, cy + 10), cv2.FONT_HERSHEY_COMPLEX, 1.0, (0, 0, 255), 2)

        # 7. DRAW LANE LINES (ADAS VISUALIZATION)
        # Using static lines for demo purposes as real lane detection requires complex calibration
        # Perspective: Trapezoid
        h, w = annotated.shape[:2]
        lane_color = (0, 255, 255) # Yellow
        
        # Define lane points (approximate for typical dashcam view)
        p1 = (int(w * 0.2), h)
        p2 = (int(w * 0.45), int(h * 0.65))
        p3 = (int(w * 0.55), int(h * 0.65))
        p4 = (int(w * 0.8), h)
        
        # Draw translucent lane overlay
        lane_overlay = annotated.copy()
        cv2.line(lane_overlay, p1, p2, lane_color, 2)
        cv2.line(lane_overlay, p3, p4, lane_color, 2)
        cv2.addWeighted(lane_overlay, 0.3, annotated, 0.7, 0, annotated)
        
        # Check for Lane Departure (Simple Center Point check)
        for t in tracks:
            # Vehicle bottom center
            bx = int((t.bbox[0] + t.bbox[2]) / 2)
            by = int(t.bbox[3])
            
            # Very rough check if inside the trapezoid
            # We just check if they are near the lines for visual effect
            if by > h * 0.65:
                # Check distance to left line (p1-p2)
                # A simple approximation for demo
                pass 
                # Ideally: Point-Line distance. 
                # For now, just drawing the 'monitored zone' is enough for the "ADAS" visual feel.

        return annotated



    def _draw_vectors(self, frame, tracks, risk_map):
        """Draw minimal predictive motion vectors."""
        for track in tracks:
            if track.track_id not in self.motion.features:
                continue
            
            feat = self.motion.features[track.track_id]
            vector = feat.velocity_vector
            # Only draw significant motion to reduce noise
            if vector is None or np.linalg.norm(vector) < 3.0:
                pass # Continue to draw trail even if slow
                
            # Draw History Trail
            if track.track_id in self.track_history:
                pts = self.track_history[track.track_id]
                if len(pts) > 1:
                    # Draw subtle polyline
                    cv2.polylines(frame, [np.array(pts, dtype=np.int32)], False, (0, 255, 255), 1, cv2.LINE_AA)

            if vector is None or np.linalg.norm(vector) < 3.0:
                 continue

            center_x = int((track.bbox[0] + track.bbox[2]) / 2)
            center_y = int((track.bbox[1] + track.bbox[3]) / 2)
            
            # Predict position in 1.0 seconds (reduced scale)
            end_x = int(center_x + vector[0] * 10.0)
            end_y = int(center_y + vector[1] * 10.0)
            
            color = (255, 255, 0) # Cyan
            if track.track_id in risk_map:
                color = risk_map[track.track_id].color

            cv2.arrowedLine(frame, (center_x, center_y), (end_x, end_y), color, 2, tipLength=0.3)

    def _draw_hud(self, frame, tracks, accident_detected: bool = False):
        """Draw a compact, professional analytics box in top right."""
        h, w = frame.shape[:2]
        
        # Compact dimensions
        panel_w = 200
        panel_h = 110 # approx
        x = w - panel_w - 20
        y = 20
        
        # Dark semi-transparent background
        overlay = frame.copy()
        bg_color = (20, 20, 20)
        if accident_detected:
            bg_color = (50, 0, 0) # Dark red tint
            
        cv2.rectangle(overlay, (x, y), (x + panel_w, y + panel_h), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Thin tech border
        border_color = (100, 100, 100)
        if accident_detected:
            border_color = (0, 0, 255)
            
        cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), border_color, 1)
        
        # Header
        header_text = "REAL-TIME ANALYTICS"
        header_color = (200, 200, 200)
        if accident_detected:
            header_text = "CRITICAL ALERT"
            header_color = (0, 0, 255)
            
        cv2.putText(frame, header_text, (x + 10, y + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, header_color, 1, cv2.LINE_AA)
        cv2.line(frame, (x + 10, y + 28), (x + panel_w - 10, y + 28), border_color, 1)
        
        # Stats
        total_vehicles = len(tracks)
        
        # Count types
        counts = {"car": 0, "bus": 0, "truck": 0, "motorcycle": 0}
        for t in tracks:
            cls = t.class_name.lower()
            if cls in counts:
                counts[cls] += 1
        # Stats
        total_vehicles = len(tracks)
        
        # Count types (Dynamic)
        counts = {}
        for t in tracks:
            # Normalize class name
            cls = t.class_name.lower().strip()
            # Map common variations if needed, or just count exact
            counts[cls] = counts.get(cls, 0) + 1
            
        # Sort by frequency and take top 4
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:4]
                
        # Draw counts small
        cursor_y = y + 45
        if not sorted_counts:
            # If no tracks, show placeholder
            cv2.putText(frame, "No objects detected", (x + 15, cursor_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA)
            cursor_y += 15
        else:
            for cls, count in sorted_counts:
                # Capitalize first letter
                text = f"{cls.title()}: {count}"
                cv2.putText(frame, text, (x + 15, cursor_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA)
                cursor_y += 18
        
        # Total / Status
        cv2.line(frame, (x + 10, cursor_y + 5), (x + panel_w - 10, cursor_y + 5), (60, 60, 60), 1)
        cursor_y += 25
        
        status_color = (0, 255, 0)
        status_text = "FLOW: NORMAL"
        
        if accident_detected:
            status_text = "ACCIDENT DETECTED"
            status_color = (0, 0, 255)
        elif total_vehicles > 6:
             status_text = "FLOW: HIGH"
             status_color = (0, 165, 255)
             
        cv2.putText(frame, status_text, (x + 15, cursor_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1, cv2.LINE_AA)




    def _render(self, frame) -> None:
        cv2.imshow("Accident Risk Monitor", frame)
        cv2.waitKey(1)

    def _update_sensors(self, timestamp: float) -> None:
        if self.imu_handler and timestamp - self.last_imu_time > self.config.hardware.imu_interval:
            reading = self.imu_handler.read()
            self.last_imu_jerk = reading.jerk
            self.last_imu_time = timestamp

        if self.gps_handler and timestamp - self.last_gps_time > self.config.hardware.gps_interval:
            location = self.gps_handler.read_location()
            if location:
                self.last_gps = location
                self.last_gps_time = timestamp

    def _handle_signal(self, signum, frame):
        self.logger.info("Received signal %s; stopping pipeline.", signum)
        self.stop_requested = True


def main():
    config = load_config()
    pipeline = AccidentDetectionPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()

