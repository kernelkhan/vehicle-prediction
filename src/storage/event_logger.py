from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.helpers import save_json
from src.utils.logger import get_logger


@dataclass
class EventRecord:
    event_id: str
    timestamp: str
    risk_level: str
    risk_score: float
    track_id: int
    reasons: list[str]
    snapshot_path: Optional[str] = None
    clip_path: Optional[str] = None
    location: Optional[Dict[str, Any]] = None


class EventLogger:
    """
    Persists event metadata locally for audit and synchronization.
    """

    def __init__(self, log_path: Path, log_dir: Optional[Path] = None) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("EventLogger", log_dir)

    def append(self, record: EventRecord) -> None:
        self.logger.info(
            "Logging event %s with risk level %s", record.event_id, record.risk_level
        )
        existing = self._load()
        existing.append(asdict(record))
        save_json(self.log_path, {"events": existing})

    def list_events(self) -> list[dict]:
        return self._load()

    def _load(self) -> list[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        try:
            raw = json.loads(self.log_path.read_text(encoding="utf-8"))
            return raw.get("events", [])
        except json.JSONDecodeError:
            return []

    @staticmethod
    def build_event_id(track_id: int) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{timestamp}_track{track_id}"

