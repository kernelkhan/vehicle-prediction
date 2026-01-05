from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventLocation(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    source: Optional[str] = None


class EventResponse(BaseModel):
    event_id: str
    timestamp: datetime
    risk_level: str
    risk_score: float
    track_id: int
    reasons: list[str]
    snapshot_path: Optional[str] = None
    clip_path: Optional[str] = None
    firebase_snapshot_url: Optional[str] = None
    firebase_clip_url: Optional[str] = None
    location: Optional[EventLocation] = None

