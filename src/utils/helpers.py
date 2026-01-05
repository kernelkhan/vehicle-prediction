from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Optional


class MovingAverage:
    """Efficient moving average calculator used for smoothing sensor data."""

    def __init__(self, window_size: int = 5) -> None:
        self.window_size = max(1, window_size)
        self._values: Deque[float] = deque(maxlen=self.window_size)

    def update(self, value: float) -> float:
        self._values.append(value)
        return sum(self._values) / len(self._values)

    def reset(self) -> None:
        self._values.clear()


def load_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load json from a path with graceful fallback."""

    if not path.exists():
        return default or {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError:
        return default or {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Persist json ensuring parent directory exists."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def timestamp_ms() -> int:
    """Return current timestamp in milliseconds."""

    return int(time.time() * 1_000)


def batched(iterable: Iterable[Any], batch_size: int) -> Iterable[list[Any]]:
    """
    Yield successive batches from an iterable.

    Python <3.12 compatibility for itertools.batched.
    """

    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

