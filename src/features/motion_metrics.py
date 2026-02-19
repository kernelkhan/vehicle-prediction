from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

import numpy as np

from src.tracking.track_utils import Track, bbox_center


@dataclass
class MotionFeature:
    velocity: float = 0.0
    acceleration: float = 0.0
    heading_change: float = 0.0
    lateral_drift: float = 0.0
    lateral_drift: float = 0.0
    timestamp: float = 0.0
    speed_kmh: float = 0.0
    velocity_vector: Optional[np.ndarray] = None


class MotionFeatureExtractor:
    """
    Maintains per-track motion history to derive kinematic features required
    for risk assessment.
    """

    def __init__(self, max_history: int = 15, fps: int = 20) -> None:
        self.max_history = max_history
        self.dt = 1.0 / max(fps, 1)
        self.history: Dict[int, Deque[np.ndarray]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self.last_velocity: Dict[int, np.ndarray] = {}
        self.features: Dict[int, MotionFeature] = {}

    def update(self, track: Track, timestamp: float) -> MotionFeature:
        center = bbox_center(track.bbox)
        history = self.history[track.track_id]
        history.append(center)

        velocity_vec = np.zeros(2, dtype=np.float32)
        acceleration = 0.0
        heading_change = 0.0
        lateral_drift = 0.0

        if len(history) >= 2:
            # Use a window of up to 3 frames for responsiveness (5 was too smooth for crashes)
            window = min(len(history), 3)
            # Calculate velocity over the window
            # (pos[i] - pos[i-k]) / (k * dt)
            velocity_vec = (history[-1] - history[-window]) / ((window - 1) * self.dt)
            velocity = float(np.linalg.norm(velocity_vec))
        else:
            velocity = 0.0

        if track.track_id in self.last_velocity:
            prev_velocity = self.last_velocity[track.track_id]
            acceleration_vec = (velocity_vec - prev_velocity) / self.dt
            acceleration = float(np.linalg.norm(acceleration_vec))

            heading_change = self._heading_delta(prev_velocity, velocity_vec)
            lateral_drift = self._lateral_drift(prev_velocity, velocity_vec)

        self.last_velocity[track.track_id] = velocity_vec

        # Heuristic: Estimate km/h based on pixel velocity
        # Ideally this requires calibration (homography), but we use a dynamic scaling factor
        # assuming objects further away (smaller) move fewer pixels for same speed.
        # Scale factor = Reference / Box_Area_Sqrt basically.
        # For this demo, we use a fixed conversion factor tuned for the sample video.
        px_to_m = 0.05 # Approx 5cm per pixel
        speed_mps = velocity * px_to_m
        speed_kmh = speed_mps * 3.6

        feature = MotionFeature(
            velocity=velocity,
            acceleration=acceleration,
            heading_change=heading_change,
            lateral_drift=lateral_drift,
            timestamp=timestamp,
            speed_kmh=speed_kmh,
            velocity_vector=velocity_vec
        )
        self.features[track.track_id] = feature
        return feature

    def clear_stale(self, active_ids: set[int]) -> None:
        stale_ids = set(self.history.keys()) - active_ids
        for track_id in stale_ids:
            self.history.pop(track_id, None)
            self.last_velocity.pop(track_id, None)
            self.features.pop(track_id, None)

    @staticmethod
    def _heading_delta(vec1: np.ndarray, vec2: np.ndarray) -> float:
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        cos_theta = float(np.clip(np.dot(vec1, vec2) / (norm1 * norm2), -1.0, 1.0))
        angle = math.degrees(math.acos(cos_theta))
        return angle

    @staticmethod
    def _lateral_drift(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Approximate lateral drift as magnitude of perpendicular component."""

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        unit1 = vec1 / norm1
        projection = np.dot(vec2, unit1)
        lateral = vec2 - projection * unit1
        return float(np.linalg.norm(lateral))

