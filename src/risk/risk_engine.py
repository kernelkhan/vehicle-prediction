from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.features.motion_metrics import MotionFeature
from src.features.ttc_estimator import TTCResult
from src.tracking.track_utils import Track
from src.utils.logger import get_logger

from .heuristics import RiskHeuristics


@dataclass
class RiskAssessment:
    track_id: int
    risk_score: float
    risk_level: str
    reasons: List[str]
    timestamp: float


class RiskEngine:
    """
    Rule-based risk evaluator combining motion heuristics and TTC estimates.
    """

    def __init__(self, heuristics: Optional[RiskHeuristics] = None, log_dir=None):
        self.heuristics = heuristics or RiskHeuristics()
        self.logger = get_logger("RiskEngine", log_dir)
        self.freeze_tracker: Dict[int, float] = {}

    def evaluate(
        self,
        tracks: List[Track],
        motion_features: Dict[int, MotionFeature],
        ttc_results: List[TTCResult],
        timestamp: Optional[float] = None,
    ) -> List[RiskAssessment]:
        timestamp = timestamp or time.time()
        assessments: List[RiskAssessment] = []
        ttc_lookup = self._build_ttc_lookup(ttc_results)

        active_ids = {track.track_id for track in tracks}
        self._cleanup_freeze(active_ids)

        for track in tracks:
            feature = motion_features.get(track.track_id)
            if feature is None:
                continue

            score = 0.0
            reasons: List[str] = []
            thresholds = self.heuristics.thresholds
            weights = self.heuristics.weights

            deceleration = -feature.acceleration if feature.velocity < 0 else feature.acceleration
            if deceleration > thresholds.deceleration_high:
                score += weights.deceleration
                reasons.append("sudden deceleration")

            heading = abs(feature.heading_change)
            if heading > thresholds.heading_change_high:
                score += weights.heading
                reasons.append("abrupt heading change")

            if feature.lateral_drift > thresholds.lateral_drift_high:
                score += weights.lateral
                reasons.append("lateral drift")

            ttc_value, rel_speed = ttc_lookup.get(track.track_id, (None, None))
            if ttc_value is not None:
                if ttc_value <= thresholds.ttc_critical:
                    score += weights.ttc
                    reasons.append(f"critical TTC ({ttc_value:.1f}s)")
                elif ttc_value <= thresholds.ttc_warning:
                    score += weights.ttc * 0.5
                    reasons.append(f"low TTC ({ttc_value:.1f}s)")
                if rel_speed and rel_speed > thresholds.velocity_high:
                    reasons.append("high closing speed")
                    score += 0.1

            if feature.velocity < 0.1:
                freeze_start = self.freeze_tracker.setdefault(track.track_id, timestamp)
                if timestamp - freeze_start > thresholds.freeze_duration:
                    score += weights.freeze
                    reasons.append("possible impact freeze")
            else:
                self.freeze_tracker.pop(track.track_id, None)

            risk_level = self._risk_level(score)
            if score > 0:
                assessments.append(
                    RiskAssessment(
                        track_id=track.track_id,
                        risk_score=round(min(score, 1.0), 3),
                        risk_level=risk_level,
                        reasons=reasons,
                        timestamp=timestamp,
                    )
                )

        return assessments

    def _cleanup_freeze(self, active_ids: set[int]) -> None:
        stale = set(self.freeze_tracker.keys()) - active_ids
        for track_id in stale:
            self.freeze_tracker.pop(track_id, None)

    @staticmethod
    def _build_ttc_lookup(ttc_results: List[TTCResult]) -> Dict[int, tuple[Optional[float], Optional[float]]]:
        lookup: Dict[int, tuple[Optional[float], Optional[float]]] = {}
        for result in ttc_results:
            current = lookup.get(result.subject_id)
            if current is None or (result.ttc < current[0]):
                lookup[result.subject_id] = (result.ttc, result.relative_speed)
        return lookup

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 0.75:
            return "critical"
        if score >= 0.5:
            return "high"
        if score >= 0.25:
            return "medium"
        return "low"

