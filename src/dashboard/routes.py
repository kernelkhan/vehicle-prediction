from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from config.config import load_config
from src.dashboard.schemas import EventResponse
from src.dashboard.stream_manager import stream_manager
from src.storage.event_logger import EventLogger


templates = Jinja2Templates(directory=Path("web/templates"))
router = APIRouter()


def get_event_logger(request: Request) -> EventLogger:
    return request.app.state.event_logger


@router.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/events")
async def events_page(request: Request):
    return templates.TemplateResponse("events.html", {"request": request})


@router.get("/video-feed")
async def video_feed():
    return StreamingResponse(
        stream_manager.frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/api/control/pause")
async def pause_stream():
    stream_manager.pause()
    return {"status": "paused"}


@router.post("/api/control/resume")
async def resume_stream():
    stream_manager.resume()
    return {"status": "resumed"}


@router.get("/api/control/status")
async def stream_status():
    return {"paused": stream_manager.is_paused()}


@router.get("/analytics")
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})


@router.get("/api/events", response_model=List[EventResponse])
async def api_events(event_logger: EventLogger = Depends(get_event_logger)):
    raw_events = event_logger.list_events()
    if not raw_events:
        mock_path = Path("web/assets/mock_events.json")
        if mock_path.exists():
            import json

            with mock_path.open("r", encoding="utf-8") as fp:
                raw_events = json.load(fp).get("events", [])
    events: List[EventResponse] = []
    for item in raw_events:
        try:
            events.append(_build_event(item))
        except Exception:
            continue
    return events


@router.get("/api/stats")
async def api_stats(event_logger: EventLogger = Depends(get_event_logger)):
    """Aggregate stats for dashboard analytics."""
    raw_events = event_logger.list_events()
    
    total_events = len(raw_events)
    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    hours_activity = {}
    
    for event in raw_events:
        # Risk Distribution
        level = event.get("risk_level", "low").lower()
        if level in risk_counts:
             risk_counts[level] += 1
             
        # Hourly Activity
        ts_str = event.get("timestamp")
        if ts_str:
            try:
                # Isoformat handles 'T' separator
                dt_obj = dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                hour_key = dt_obj.strftime("%H:00")
                hours_activity[hour_key] = hours_activity.get(hour_key, 0) + 1
            except:
                pass
                
    # Sort hours
    sorted_activity = dict(sorted(hours_activity.items()))
    
    return {
        "total": total_events,
        "risk_breakdown": risk_counts,
        "activity_timeline": sorted_activity
    }


def _build_event(payload: dict) -> EventResponse:
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, str):
        timestamp_dt = dt.datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    else:
        timestamp_dt = dt.datetime.utcnow()

    snapshot_path = payload.get("snapshot_path")
    clip_path = payload.get("clip_path")

    # Clean paths for web use (Hack: assumes standard structure)
    if snapshot_path and "data/media" in snapshot_path.replace("\\", "/"):
        # Extract relative path from data/media
        rel_path = snapshot_path.replace("\\", "/").split("data/media/")[-1]
        snapshot_path = f"/media/{rel_path}"

    if clip_path and "data/media" in clip_path.replace("\\", "/"):
        rel_path = clip_path.replace("\\", "/").split("data/media/")[-1]
        clip_path = f"/media/{rel_path}"

    location = payload.get("location")
    return EventResponse(
        event_id=payload.get("event_id", "unknown"),
        timestamp=timestamp_dt,
        risk_level=payload.get("risk_level", "low"),
        risk_score=float(payload.get("risk_score", 0)),
        track_id=int(payload.get("track_id", -1)),
        reasons=payload.get("reasons", []),
        snapshot_path=snapshot_path,
        clip_path=clip_path,
        firebase_snapshot_url=payload.get("firebase_snapshot_url"),
        firebase_clip_url=payload.get("firebase_clip_url"),
        location=location,
    )

