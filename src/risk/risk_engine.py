from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

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
    color: tuple = (0, 255, 0) # Default green


class RiskEngine:
    """
    Rule-based risk evaluator combining motion heuristics and TTC estimates.
    """

    def __init__(self, heuristics: Optional[RiskHeuristics] = None, log_dir=None):
        self.heuristics = heuristics or RiskHeuristics()
        self.logger = get_logger("RiskEngine", log_dir)
        self.freeze_tracker: Dict[int, float] = {}

    def _risk_color(self, score: float) -> tuple:
        """Return BGR color tuple for risk level."""
        if score < 0.25:
            return (0, 255, 0) # Green for low
        elif score < 0.5:
            return (0, 255, 255) # Yellow for medium
        else:
            # Both High and Critical are RED as requested
            return (0, 0, 255) # Red

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
        
        # --- Wrong Way Detection ---
        wrong_way_map = self._check_wrong_way(tracks, motion_features)
        
        intermediate_risks = {}

        for track in tracks:
            feature = motion_features.get(track.track_id)
            if feature is None:
                continue

            score = 0.0
            reasons: List[str] = []
            thresholds = self.heuristics.thresholds
            weights = self.heuristics.weights

            # 0. Low Speed Noise Filter
            # Ignore physics risks if moving slow (prevents false positives while parking/turning)
            # The actual "Collision" check (IoU/Proximity) happens LATER and will still catch stopped crashes.
            if feature.speed_kmh < 15.0:
                 # Just check stillness
                 pass 
            else:
                # 1. Deceleration Check (Only at speed)
                deceleration = -feature.acceleration if feature.velocity < 0 else feature.acceleration
                if deceleration > thresholds.deceleration_high:
                    severity = (deceleration / thresholds.deceleration_high) ** 2
                    score += weights.deceleration * min(severity, 2.0)
                    if severity > 1.5:
                        score += 0.5 
                        reasons.append("CRASH IMPACT")
                    else:
                        reasons.append("sudden deceleration")

                # 2. Heading/Swerving Check
                heading = abs(feature.heading_change)
                if heading > 150.0 and feature.speed_kmh > 15.0:
                    score += 2.0 # Guaranteed Crash (Bounce)
                    reasons.append("CRASH IMPACT (BOUNCE)")
                elif heading > thresholds.heading_change_high:
                    score += weights.heading
                    reasons.append("swerving")

                # 3. Lateral Drift
                if feature.lateral_drift > thresholds.lateral_drift_high:
                    score += weights.lateral
                    reasons.append("drifting")
            
            # 3.5. Wrong Way Check
            if track.track_id in wrong_way_map:
                ww_score = wrong_way_map[track.track_id]
                score += ww_score
                reasons.append("WRONG WAY DRIVER")

            # 4. Time To Collision (Critical)
            ttc_value, rel_speed = ttc_lookup.get(track.track_id, (None, None))
            if ttc_value is not None:
                if ttc_value <= thresholds.ttc_critical:
                    # Exponential penalty for very low TTC
                    urgency = 1.0 + (thresholds.ttc_critical - ttc_value)
                    score += weights.ttc * urgency
                    reasons.append(f"CRITICAL TTC {ttc_value:.1f}s")
                elif ttc_value <= thresholds.ttc_warning:
                    score += weights.ttc * 0.6
                    reasons.append(f"low TTC {ttc_value:.1f}s")
                
                # Check closing speed if TTC is relevant
                if rel_speed and rel_speed > thresholds.velocity_high:
                    reasons.append("rapid closing speed")
                    score += 0.15

            # 5. Stopped Vehicle Check (Stationary / Breakdown)
            if feature.velocity < 2.0: # < 2 km/h is effectively stopped
                freeze_start = self.freeze_tracker.setdefault(track.track_id, timestamp)
                duration = timestamp - freeze_start
                
                # Warning Phase (3s - 10s)
                if duration > 10.0:
                    score += 2.0 # CRITICAL: Breakdown / Hazard
                    reasons.append(f"STOPPED {int(duration)}s (HAZARD)")
                elif duration > 3.0:
                    score += 0.4 # MEDIUM: Potential Hazard
                    reasons.append(f"STOPPED {int(duration)}s")
            else:
                # Reset if moving > 5 km/h to avoid jitter
                if feature.speed_kmh > 5.0:
                    self.freeze_tracker.pop(track.track_id, None)
            
            intermediate_risks[track.track_id] = {"score": score, "reasons": reasons}


        # 2. Pairwise Collision Check (New)
        collision_pairs = set()
        for i, t1 in enumerate(tracks):
            for j, t2 in enumerate(tracks):
                if i >= j: continue
                
                # Check Overlap (IoU assumption or simple box intersection)
                box1 = t1.bbox
                box2 = t2.bbox
                
                # Intersection coordinates
                xi1 = max(box1[0], box2[0])
                yi1 = max(box1[1], box2[1])
                xi2 = min(box1[2], box2[2])
                yi2 = min(box1[3], box2[3])
                
                inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
                box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
                box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
                
                # If meaningful overlap relative to smaller car
                # Robust: 5% overlap triggers detected collision
                min_area = min(box1_area, box2_area)
                if min_area > 0 and (inter_area / min_area) > 0.45: 
                     collision_pairs.add(t1.track_id)
                     collision_pairs.add(t2.track_id)
                
                # Proximity Hazard 
                # calculated for TTC elsewhere, no need to force collision state here.

        # 3. Finalize Assessments
        assessments = []
        for track in tracks:
            # Retrieve previously calculated physics-based risk
            track_risk_data = intermediate_risks.get(track.track_id, {"score": 0.0, "reasons": []})
            score = track_risk_data["score"]
            reasons = list(track_risk_data["reasons"]) # Make a mutable copy

            # --- Collision Override ---
            if track.track_id in collision_pairs:
                score = 2.0 # Max risk
                reasons.append("COLLISION DETECTED")

            # Cap and Assess
            total_risk = min(score, 1.25)
            risk_level = self._risk_level(total_risk)
            color = self._risk_color(total_risk)
            
            if total_risk > 0.15: # Only report if there is some meaningful risk
                assessments.append(
                    RiskAssessment(
                        track_id=track.track_id,
                        risk_score=round(total_risk, 3),
                        risk_level=risk_level,
                        reasons=reasons,
                        timestamp=timestamp,
                        color=color
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

    def _check_wrong_way(self, tracks: List[Track], motion_features: Dict[int, MotionFeature]) -> Dict[int, float]:
        """
        Detect vehicles moving against the dominant traffic flow.
        Returns a map of track_id -> risk_score_penalty.
        """
        wrong_way_risks = {}
        
        # 1. Calculate Dominant Flow Vector
        flow_vectors = []
        
        for t in tracks:
            feat = motion_features.get(t.track_id)
            # Only consider vehicles moving fast enough to indicate flow (> 20 km/h)
            if feat and feat.speed_kmh > 20.0 and feat.velocity_vector is not None:
                flow_vectors.append(feat.velocity_vector)
        
        if len(flow_vectors) < 2:
            return {} # Not enough data to establish reliable flow
            
        avg_flow = np.mean(flow_vectors, axis=0)
        norm_flow = np.linalg.norm(avg_flow)
        
        if norm_flow < 0.1: 
            return {} # Flow is too weak/ambiguous
            
        # 2. Check Each Vehicle against Flow
        for t in tracks:
            feat = motion_features.get(t.track_id)
            if not feat or feat.speed_kmh < 15.0:
                continue
                
            vec = feat.velocity_vector
            if vec is None: continue
            
            norm_vec = np.linalg.norm(vec)
            if norm_vec < 0.1: continue
            
            # Calculate Cosine Similarity
            # dot = |a||b|cos(theta)
            dot = np.dot(vec, avg_flow)
            cos_theta = dot / (norm_vec * norm_flow)
            
            # Threshold: cos(150 deg) ~= -0.866
            # If similarity is less than -0.8, it's opposing flow
            # We use -0.7 to be slightly more aggressive (approx 135 deg)
            if cos_theta < -0.7:
                wrong_way_risks[t.track_id] = 2.0 # Immediate High/Critical Risk
                
        return wrong_way_risks

