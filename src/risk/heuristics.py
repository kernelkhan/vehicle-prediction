from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskThresholds:
    velocity_high: float = 12.0  # m/s approx 43 km/h
    deceleration_high: float = 6.0  # m/s^2
    heading_change_high: float = 45.0  # degrees
    lateral_drift_high: float = 3.0  # m/s lateral component
    ttc_critical: float = 1.5  # seconds
    ttc_warning: float = 3.0  # seconds
    freeze_duration: float = 1.5  # seconds without motion


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

