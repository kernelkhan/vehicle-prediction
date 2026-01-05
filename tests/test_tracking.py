import numpy as np

from src.detection.detector import Detection
from src.tracking.tracker import MultiObjectTracker, TrackerConfig


def make_detection(x1, y1, x2, y2, class_id=2):
    return Detection(
        bbox=np.array([x1, y1, x2, y2], dtype=float),
        confidence=0.9,
        class_id=class_id,
        class_name="car",
    )


def test_tracker_fallback_associates_tracks():
    tracker = MultiObjectTracker(config=TrackerConfig(), log_dir=None)
    dets_frame1 = [make_detection(10, 10, 110, 110)]
    tracks1 = tracker.update(dets_frame1)
    assert len(tracks1) == 1

    dets_frame2 = [make_detection(20, 10, 120, 110)]
    tracks2 = tracker.update(dets_frame2)
    assert len(tracks2) == 1
    assert tracks1[0].track_id == tracks2[0].track_id

