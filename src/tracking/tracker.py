from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np

from src.detection.detector import Detection
from src.utils.logger import get_logger

from .track_utils import Track, bbox_center


@dataclass
class TrackerConfig:
    track_buffer: int = 20
    match_threshold: float = 0.7
    frame_rate: int = 20
    min_box_area: float = 100.0


class _KalmanTrack:
    """Fallback tracker track with simple centroid velocity estimation."""

    _next_id = 1

    def __init__(self, detection: Detection):
        self.track_id = _KalmanTrack._next_id
        _KalmanTrack._next_id += 1
        self.bbox = detection.bbox.copy()
        self.score = detection.confidence
        self.class_id = detection.class_id
        self.class_name = detection.class_name
        self.age = 1
        self.lost = 0
        self.center = bbox_center(self.bbox)
        self.velocity = np.zeros(2, dtype=np.float32)

    def update(self, detection: Detection):
        new_center = bbox_center(detection.bbox)
        self.velocity = new_center - self.center
        self.center = new_center
        self.bbox = detection.bbox.copy()
        self.score = detection.confidence
        self.class_id = detection.class_id
        self.class_name = detection.class_name
        self.age += 1
        self.lost = 0

    def mark_lost(self):
        self.lost += 1


class MultiObjectTracker:
    """
    Wrapper around ByteTrack with graceful fallback to a lightweight Kalman filter tracker.
    """

    def __init__(
        self,
        config: TrackerConfig,
        log_dir: Optional[str] = None,
    ) -> None:
        self.logger = get_logger("MultiObjectTracker", log_dir)
        self.config = config
        self.tracker = self._init_bytetrack()
        self._tracks: list[_KalmanTrack] = []

    def _init_bytetrack(self):
        try:
            module = importlib.import_module("bytetrack")
            byte_tracker_cls = getattr(module, "BYTETracker")
            self.logger.info("Using ByteTrack backend for multi-object tracking.")
            return byte_tracker_cls(
                track_thresh=0.5,
                track_buffer=self.config.track_buffer,
                match_thresh=self.config.match_threshold,
                frame_rate=self.config.frame_rate,
            )
        except (ImportError, AttributeError):
            self.logger.warning(
                "ByteTrack not available, falling back to lightweight tracker."
            )
            return None

    def update(self, detections: Iterable[Detection]) -> List[Track]:
        detections = list(detections)
        if not detections:
            self._decay_tracks()
            return self._collect_tracks()

        if self.tracker:
            dets = np.array([np.concatenate([d.bbox, [d.confidence]]) for d in detections])
            classes = np.array([d.class_id for d in detections])
            tracks = self.tracker.update(dets, classes)
            return self._convert_byte_tracks(tracks, detections)

        return self._update_fallback(detections)

    def _convert_byte_tracks(self, tracks, detections: list[Detection]) -> List[Track]:
        out: List[Track] = []
        for t in tracks:
            bbox = np.array([t.tlbr[0], t.tlbr[1], t.tlbr[2], t.tlbr[3]], dtype=float)
            class_id = int(getattr(t, "cls", -1))
            class_name = (
                detections[0].class_name if class_id == -1 else detections[0].class_name
            )
            velocity = getattr(t, "velocity", None)
            if velocity is not None:
                velocity = np.array(velocity, dtype=float)

            out.append(
                Track(
                    track_id=int(t.track_id),
                    bbox=bbox,
                    score=float(t.score),
                    class_id=class_id if class_id >= 0 else detections[0].class_id,
                    class_name=class_name,
                    age=int(getattr(t, "age", 1)),
                    lost=int(getattr(t, "lost", 0)),
                    velocity=velocity,
                )
            )
        return out

    def _update_fallback(self, detections: list[Detection]) -> List[Track]:
        # Simple nearest-neighbor association
        unmatched_tracks = set(range(len(self._tracks)))
        unmatched_detections = set(range(len(detections)))

        if self._tracks:
            distance_matrix = np.zeros((len(self._tracks), len(detections)))
            for i, track in enumerate(self._tracks):
                for j, det in enumerate(detections):
                    distance_matrix[i, j] = np.linalg.norm(
                        bbox_center(track.bbox) - bbox_center(det.bbox)
                    )

            while distance_matrix.size > 0:
                idx = np.unravel_index(np.argmin(distance_matrix), distance_matrix.shape)
                track_idx, det_idx = idx
                if distance_matrix[track_idx, det_idx] > 100:
                    break
                self._tracks[track_idx].update(detections[det_idx])
                unmatched_tracks.discard(track_idx)
                unmatched_detections.discard(det_idx)
                distance_matrix[track_idx, :] = np.inf
                distance_matrix[:, det_idx] = np.inf

        for idx in unmatched_tracks:
            self._tracks[idx].mark_lost()

        for idx in unmatched_detections:
            self._tracks.append(_KalmanTrack(detections[idx]))

        self._tracks = [t for t in self._tracks if t.lost < self.config.track_buffer]
        return self._collect_tracks()

    def _decay_tracks(self):
        for track in self._tracks:
            track.mark_lost()
        self._tracks = [t for t in self._tracks if t.lost < self.config.track_buffer]

    def _collect_tracks(self) -> List[Track]:
        out: List[Track] = []
        for track in self._tracks:
            out.append(
                Track(
                    track_id=track.track_id,
                    bbox=track.bbox.copy(),
                    score=track.score,
                    class_id=track.class_id,
                    class_name=track.class_name,
                    age=track.age,
                    lost=track.lost,
                    velocity=track.velocity,
                )
            )
        return out

