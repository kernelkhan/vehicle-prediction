import numpy as np

from src.features.motion_metrics import MotionFeature
from src.features.ttc_estimator import TTCResult
from src.risk.heuristics import RiskHeuristics, RiskThresholds, RiskWeights
from src.risk.risk_engine import RiskEngine
from src.tracking.track_utils import Track


def make_track(track_id=1):
    return Track(
        track_id=track_id,
        bbox=np.array([10, 10, 60, 60], dtype=float),
        score=0.9,
        class_id=2,
        class_name="car",
        age=5,
        lost=0,
        velocity=np.array([5.0, 0.0]),
    )


def test_risk_engine_flags_critical_ttc():
    heuristics = RiskHeuristics(
        thresholds=RiskThresholds(ttc_critical=1.5),
        weights=RiskWeights(ttc=0.5),
    )
    engine = RiskEngine(heuristics=heuristics)

    track = make_track()
    feature = MotionFeature(velocity=20.0, acceleration=5.0, heading_change=5.0, lateral_drift=0.5, timestamp=0.0)
    ttc_result = TTCResult(subject_id=1, target_id=2, ttc=1.0, relative_speed=25.0)

    assessments = engine.evaluate(
        tracks=[track],
        motion_features={1: feature},
        ttc_results=[ttc_result],
        timestamp=0.0,
    )

    assert assessments
    assert assessments[0].risk_level in ("high", "critical")

