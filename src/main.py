from __future__ import annotations

import signal
import time
from pathlib import Path
from typing import Dict, Optional

import cv2

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
        self.last_gps_time = 0.0

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
            ret, frame = capture.read()
            if not ret:
                consecutive_failures += 1
                if is_video_file and consecutive_failures >= max_failures:
                    self.logger.info("Video file ended or reached end of stream. Stopping pipeline.")
                    break
                elif not is_video_file:
                    self.logger.warning("Frame grab failed; retrying...")
                    time.sleep(0.1)
                else:
                    self.logger.warning("Frame grab failed (%d/%d); retrying...", consecutive_failures, max_failures)
                    time.sleep(0.1)
                continue
            
            consecutive_failures = 0  # Reset on successful read

            timestamp = time.time()
            self._update_sensors(timestamp)
            detections = self.detector.infer(frame)
            tracks = self.tracker.update(detections)

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

            self._update_ring_buffer(frame)

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

            annotated = self._annotate(frame, tracks, assessments)
            stream_manager.publish(annotated)

            if self.config.stream.display:
                self._render(annotated)

        capture.release()
        cv2.destroyAllWindows()
        self.logger.info("Pipeline stopped.")

    def _update_ring_buffer(self, frame) -> None:
        success, encoded = cv2.imencode(".jpg", frame)
        if success:
            self.ring_buffer.append_frame(encoded.tobytes())

    def _annotate(self, frame, tracks, assessments):
        annotated = frame.copy()
        for track in tracks:
            x1, y1, x2, y2 = track.bbox.astype(int)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                f"{track.class_name}:{track.track_id}",
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        for idx, assessment in enumerate(assessments):
            cv2.putText(
                annotated,
                f"ID {assessment.track_id}: {assessment.risk_level}",
                (10, 30 + idx * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
        return annotated

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

