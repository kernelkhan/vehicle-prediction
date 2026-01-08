from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskThresholds:
    velocity_high: float = 15.0  # m/s approx 54 km/h (increased from 12.0)
    deceleration_high: float = 8.0  # m/s^2 (increased from 6.0)
    heading_change_high: float = 60.0  # degrees (increased from 45.0)
    lateral_drift_high: float = 4.0  # m/s lateral component (increased from 3.0)
    ttc_critical: float = 1.0  # seconds (decreased from 1.5 - more critical)
    ttc_warning: float = 2.5  # seconds (decreased from 3.0)
    freeze_duration: float = 2.0  # seconds without motion (increased from 1.5)


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

