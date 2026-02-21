from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskThresholds:
    velocity_high: float = 80.0  # px/s (Lowered significantly to catch city speeds)
    deceleration_high: float = 150.0  # px/s^2 (More sensitive to braking)
    heading_change_high: float = 30.0  # degrees (Detect smaller swerves)
    lateral_drift_high: float = 20.0  # px/s (Detect lane drift)
    ttc_critical: float = 1.5  # seconds
    ttc_warning: float = 3.0  # seconds
    freeze_duration: float = 2.0  # seconds


@dataclass
class RiskWeights:
    deceleration: float = 0.35
    ttc: float = 0.35
    heading: float = 0.15
    lateral: float = 0.1
    freeze: float = 0.05


@dataclass
class RiskHeuristics:
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    weights: RiskWeights = field(default_factory=RiskWeights)

