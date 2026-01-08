from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from src.alert.firebase_client import FirebaseClient
from src.alert.notifier import AlertMessage, Notifier
from src.features.motion_metrics import MotionFeature
from src.risk.risk_engine import RiskAssessment
from src.sensors.gps_handler import Location
from src.storage.event_logger import EventLogger, EventRecord
from src.storage.media_manager import MediaManager
from src.tracking.track_utils import Track
from src.utils.logger import get_logger
from src.utils.video_buffer import RingBufferRecorder


class AlertManager:
    """
    Coordinates media capture, alert delivery, and event logging.
    """

    def __init__(
        self,
        media_manager: MediaManager,
        event_logger: EventLogger,
        notifier: Notifier,
        firebase_client: Optional[FirebaseClient] = None,
        clip_buffer: Optional[RingBufferRecorder] = None,
        log_dir: Optional[Path] = None,
        cooldown_seconds: float = 5.0,
    ) -> None:
        self.media_manager = media_manager
        self.event_logger = event_logger
        self.notifier = notifier
        self.firebase_client = firebase_client
        self.clip_buffer = clip_buffer
        self.logger = get_logger("AlertManager", log_dir)
        self.cooldown_seconds = cooldown_seconds
        self.last_alert_time: dict[int, float] = {}  # track_id -> last alert timestamp

    def handle_risk_event(
        self,
        assessment: RiskAssessment,
        track: Track,
        frame,
        location: Optional[Location],
    ) -> None:
        # Cooldown check: prevent duplicate alerts for the same track
        current_time = time.time()
        last_time = self.last_alert_time.get(track.track_id, 0)
        if current_time - last_time < self.cooldown_seconds:
            self.logger.debug(
                "Skipping alert for track %d (cooldown: %.1fs remaining)",
                track.track_id,
                self.cooldown_seconds - (current_time - last_time),
            )
            return
        
        # Update cooldown timestamp
        self.last_alert_time[track.track_id] = current_time
        
        event_id = EventLogger.build_event_id(track.track_id)
        snapshot_path = self._capture_snapshot(event_id, frame)
        clip_path = self._export_clip(event_id)
        firebase_snapshot = None
        firebase_clip = None

        if self.firebase_client:
            if snapshot_path:
                firebase_snapshot = self.firebase_client.upload_media(
                    str(snapshot_path), f"snapshots/{snapshot_path.name}"
                )
            if clip_path:
                firebase_clip = self.firebase_client.upload_media(
                    str(clip_path), f"clips/{clip_path.name}"
                )

        alert_body = self._compose_alert_body(assessment, location)
        media_url = firebase_snapshot or firebase_clip
        self.notifier.send_alert(
            AlertMessage(
                body=alert_body,
                media_url=media_url,
                latitude=location.latitude if location else None,
                longitude=location.longitude if location else None,
            )
        )

        # Use provided location or default to a mock location (India center) for map display
        event_location = location
        if not event_location:
            # Default location: India center (useful for testing/demo)
            event_location = Location(latitude=20.5937, longitude=78.9629, accuracy=0.0)
        
        record = EventRecord(
            event_id=event_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(assessment.timestamp)),
            risk_level=assessment.risk_level,
            risk_score=assessment.risk_score,
            track_id=assessment.track_id,
            reasons=assessment.reasons,
            snapshot_path=str(snapshot_path) if snapshot_path else None,
            clip_path=str(clip_path) if clip_path else None,
            location=asdict(event_location) if event_location else None,
        )
        self.event_logger.append(record)

        if self.firebase_client:
            event_payload = asdict(record)
            event_payload["firebase_snapshot_url"] = firebase_snapshot
            event_payload["firebase_clip_url"] = firebase_clip
            self.firebase_client.log_event(event_payload)

        self.logger.info("Processed alert for event %s", event_id)

    def _capture_snapshot(self, event_id: str, frame) -> Optional[Path]:
        if frame is None:
            self.logger.warning("Frame unavailable; snapshot skipped.")
            return None
        filename = f"{event_id}.jpg"
        return self.media_manager.save_snapshot(frame, filename)

    def _export_clip(self, event_id: str) -> Optional[Path]:
        if not self.clip_buffer:
            return None
        output = Path(self.media_manager.base_dir) / "clips" / f"{event_id}.mp4"
        clip = self.clip_buffer.export_clip(output_path=output)
        return clip

    def _compose_alert_body(
        self, assessment: RiskAssessment, location: Optional[Location]
    ) -> str:
        location_str = ""
        if location:
            location_str = f"\nLocation: {location.latitude:.5f}, {location.longitude:.5f} ({location.source})"
        reasons = ", ".join(assessment.reasons) if assessment.reasons else "unspecified"
        return (
            "Accident risk detected!\n"
            f"Risk level: {assessment.risk_level} ({assessment.risk_score:.2f})\n"
            f"Reasons: {reasons}"
            f"{location_str}"
        )

