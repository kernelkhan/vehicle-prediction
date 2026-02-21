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
    track_buffer: int = 60 # Keep tracks for 2-3s even if lost (better for crashes)
    match_threshold: float = 0.6 # More lenient matching
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
        from scipy.optimize import linear_sum_assignment
        
        if not self._tracks:
            for det in detections:
                 self._tracks.append(self._create_new_track(det))
            return self._collect_tracks()

        # Calculate cost matrix (1 - IoU) + Distance Penalty
        n_tracks = len(self._tracks)
        n_dets = len(detections)
        cost_matrix = np.ones((n_tracks, n_dets)) * 1.0
        
        for i, track in enumerate(self._tracks):
            pred_center = track.center + track.velocity # Simple Kalman prediction
            for j, det in enumerate(detections):
                # IoU Score
                iou = self._iou(track.bbox, det.bbox)
                
                # Distance Score (normalized by diagonal)
                det_center = bbox_center(det.bbox)
                dist = np.linalg.norm(pred_center - det_center)
                max_dist = 200.0 # pixels
                dist_score = min(dist / max_dist, 1.0)
                
                # Combined cost
                cost = (1.0 - iou) * 0.7 + dist_score * 0.3
                cost_matrix[i, j] = cost

        # Hungarian Algorithm
        row_inds, col_inds = linear_sum_assignment(cost_matrix)
        
        unmatched_tracks = set(range(n_tracks))
        unmatched_dets = set(range(n_dets))
        
        matches = []
        for r, c in zip(row_inds, col_inds):
            if cost_matrix[r, c] < 0.8: # Threshold to reject bad matches
                matches.append((r, c))
                unmatched_tracks.discard(r)
                unmatched_dets.discard(c)
        
        # Update matched tracks
        for track_idx, det_idx in matches:
            self._tracks[track_idx].update(detections[det_idx])
            
        # Update unmatched tracks (mark lost)
        for track_idx in unmatched_tracks:
            self._tracks[track_idx].mark_lost()

        # Create new tracks
        for det_idx in unmatched_dets:
             self._tracks.append(self._create_new_track(detections[det_idx]))

        # Cleanup dead tracks
        self._tracks = [t for t in self._tracks if t.lost < self.config.track_buffer]
        
        return self._collect_tracks()

    def _create_new_track(self, det: Detection) -> _KalmanTrack:
        # Helper to instantiate _KalmanTrack properly
        t = _KalmanTrack(det)
        # Monkey patch the update method on the instance to keep logic encapsulated if needed
        # But _KalmanTrack is a class, so we just return the instance
        return t

    @staticmethod
    def _iou(bbox1, bbox2):
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        union = area1 + area2 - inter_area
        return inter_area / union if union > 0 else 0.0

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

