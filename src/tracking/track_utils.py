from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Track:
    track_id: int
    bbox: np.ndarray  # [x1, y1, x2, y2]
    score: float
    class_id: int
    class_name: str
    age: int
    lost: int
    velocity: Optional[np.ndarray] = None


def bbox_center(bbox: np.ndarray) -> np.ndarray:
    return np.array(
        [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0], dtype=np.float32
    )

