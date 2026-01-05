from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from src.tracking.track_utils import Track, bbox_center


@dataclass
class TTCResult:
    subject_id: int
    target_id: int
    ttc: float
    relative_speed: float


class TimeToCollisionEstimator:
    """
    Naive TTC estimator that evaluates pairwise track convergence along the
    direction of motion.
    """

    def __init__(self, max_distance: float = 200.0) -> None:
        self.max_distance = max_distance
        self.last_centers: Dict[int, np.ndarray] = {}

    def compute_pairwise(self, tracks: list[Track]) -> list[TTCResult]:
        results: list[TTCResult] = []
        centers = {t.track_id: bbox_center(t.bbox) for t in tracks}

        for subject in tracks:
            subject_center = centers[subject.track_id]
            velocity = self._velocity_vector(subject, subject_center)
            if np.linalg.norm(velocity) < 1e-3:
                continue

            for target in tracks:
                if subject.track_id == target.track_id:
                    continue
                target_center = centers[target.track_id]
                relative_pos = target_center - subject_center

                projection = np.dot(relative_pos, velocity)
                if projection <= 0:
                    continue  # moving away or perpendicular

                relative_speed = np.linalg.norm(velocity)
                distance = np.linalg.norm(relative_pos)
                if distance > self.max_distance or relative_speed < 1e-3:
                    continue

                ttc_value = distance / relative_speed
                results.append(
                    TTCResult(
                        subject_id=subject.track_id,
                        target_id=target.track_id,
                        ttc=ttc_value,
                        relative_speed=relative_speed,
                    )
                )

        self.last_centers = centers
        return results

    def _velocity_vector(self, track: Track, current_center: np.ndarray) -> np.ndarray:
        prev_center = self.last_centers.get(track.track_id)
        if prev_center is None:
            return np.zeros(2, dtype=np.float32)
        return current_center - prev_center

