from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from src.risk.heuristics import RiskThresholds, RiskWeights


class PathsConfig(BaseModel):
    base_dir: str = Field(default=str(Path.cwd()))
    media_dir: str = "data/media"
    log_dir: str = "data/logs"
    event_log: str = "data/logs/events.json"

    @computed_field
    @property
    def media_dir_abs(self) -> str:
        return str((Path(self.base_dir) / self.media_dir).resolve())

    @computed_field
    @property
    def log_dir_abs(self) -> str:
        return str((Path(self.base_dir) / self.log_dir).resolve())

    @computed_field
    @property
    def event_log_abs(self) -> str:
        return str((Path(self.base_dir) / self.event_log).resolve())


class ModelConfig(BaseModel):
    path: str = "models/yolov8_accident.onnx"
    classes: List[str] = [
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "bus",
        "truck",
    ]
    conf_threshold: float = 0.45
    iou_threshold: float = 0.5
    providers: List[str] = Field(default_factory=lambda: ["CPUExecutionProvider"])


class StreamConfig(BaseModel):
    video_source: int | str = 0
    resolution: List[int] = Field(default_factory=lambda: [1280, 720])
    fps: int = 20
    display: bool = False


class TrackerSettings(BaseModel):
    track_buffer: int = 20
    match_threshold: float = 0.7
    min_box_area: float = 100.0


class FeatureSettings(BaseModel):
    history: int = 15
    max_ttc_distance: float = 180.0


class AlertSettings(BaseModel):
    sms_enabled: bool = False
    whatsapp_enabled: bool = False
    sms_from: Optional[str] = None
    sms_to: Optional[str] = None
    whatsapp_from: Optional[str] = None
    whatsapp_to: Optional[str] = None
    email_to: Optional[str] = None
    twilio_sid: Optional[str] = None
    twilio_token: Optional[str] = None
    # Email Settings
    email_to: Optional[str] = None
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_user: Optional[str] = None
    email_password: Optional[str] = None
    
    clip_seconds: int = 12
    clip_codec: str = "XVID"  # More compatible than mp4v on Windows
    cooldown_seconds: float = 5.0  # Minimum seconds between alerts for same track


class HardwareSettings(BaseModel):
    use_imu: bool = True
    use_gps: bool = True
    imu_interval: float = 0.2
    gps_interval: float = 5.0


class RiskSettings(BaseModel):
    thresholds: RiskThresholds = RiskThresholds()
    weights: RiskWeights = RiskWeights()
    imu_jerk_threshold: float = 20.0


class FirebaseSettings(BaseModel):
    credentials_path: Optional[str] = None
    database_url: Optional[str] = None
    storage_bucket: Optional[str] = None


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    paths: PathsConfig = PathsConfig()
    model: ModelConfig = ModelConfig()
    stream: StreamConfig = StreamConfig()
    tracker: TrackerSettings = TrackerSettings()
    features: FeatureSettings = FeatureSettings()
    alert: AlertSettings = AlertSettings()
    hardware: HardwareSettings = HardwareSettings()
    risk: RiskSettings = RiskSettings()
    firebase: Optional[FirebaseSettings] = None


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    if env_path is None:
        env_path = Path(".env")

    if env_path.exists() and load_dotenv:
        load_dotenv(dotenv_path=env_path, override=True)

    cfg = AppConfig()

    env_overrides = {}
    if "VIDEO_SOURCE" in os.environ:
        value = os.environ["VIDEO_SOURCE"]
        env_overrides.setdefault("stream", {})["video_source"] = (
            int(value) if value.isdigit() else value
        )
    if "DISPLAY_STREAM" in os.environ:
        env_overrides.setdefault("stream", {})["display"] = (
            os.environ["DISPLAY_STREAM"].lower() == "true"
        )
    if "MEDIA_DIR" in os.environ:
        env_overrides.setdefault("paths", {})["media_dir"] = os.environ["MEDIA_DIR"]
    if "LOG_DIR" in os.environ:
        env_overrides.setdefault("paths", {})["log_dir"] = os.environ["LOG_DIR"]
    if "EVENT_LOG" in os.environ:
        env_overrides.setdefault("paths", {})["event_log"] = os.environ["EVENT_LOG"]
    if "SMS_ENABLED" in os.environ:
        env_overrides.setdefault("alert", {})["sms_enabled"] = (
            os.environ["SMS_ENABLED"].lower() == "true"
        )
    for key in (
        "SMS_FROM",
        "SMS_TO",
        "WHATSAPP_FROM",
        "WHATSAPP_TO",
        "ALERT_EMAIL",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "EMAIL_HOST",
        "EMAIL_PORT",
        "EMAIL_USER",
        "EMAIL_PASSWORD",
    ):
        if key in os.environ:
            field = key.lower()
            if key == "ALERT_EMAIL":
                field = "email_to"
            if key == "TWILIO_ACCOUNT_SID":
                field = "twilio_sid"
            if key == "TWILIO_AUTH_TOKEN":
                field = "twilio_token"
            if key == "EMAIL_HOST":
                field = "email_host"
            if key == "EMAIL_PORT":
                field = "email_port"
            if key == "EMAIL_USER":
                field = "email_user"
            if key == "EMAIL_PASSWORD":
                field = "email_password"
                
            env_overrides.setdefault("alert", {})[field] = os.environ[key]
    if "WHATSAPP_ENABLED" in os.environ:
        env_overrides.setdefault("alert", {})["whatsapp_enabled"] = (
            os.environ["WHATSAPP_ENABLED"].lower() == "true"
        )
    if "USE_IMU" in os.environ:
        env_overrides.setdefault("hardware", {})["use_imu"] = (
            os.environ["USE_IMU"].lower() == "true"
        )
    if "USE_GPS" in os.environ:
        env_overrides.setdefault("hardware", {})["use_gps"] = (
            os.environ["USE_GPS"].lower() == "true"
        )

    firebase_config = {}
    if "FIREBASE_CREDENTIALS_PATH" in os.environ:
        firebase_config["credentials_path"] = os.environ["FIREBASE_CREDENTIALS_PATH"]
    if "FIREBASE_DATABASE_URL" in os.environ:
        firebase_config["database_url"] = os.environ["FIREBASE_DATABASE_URL"]
    if "FIREBASE_STORAGE_BUCKET" in os.environ:
        firebase_config["storage_bucket"] = os.environ["FIREBASE_STORAGE_BUCKET"]
    if firebase_config:
        env_overrides["firebase"] = firebase_config

    if env_overrides:
        if "paths" in env_overrides:
            cfg.paths = cfg.paths.model_copy(update=env_overrides["paths"])
        if "model" in env_overrides:
            cfg.model = cfg.model.model_copy(update=env_overrides["model"])
        if "stream" in env_overrides:
            cfg.stream = cfg.stream.model_copy(update=env_overrides["stream"])
        if "tracker" in env_overrides:
            cfg.tracker = cfg.tracker.model_copy(update=env_overrides["tracker"])
        if "features" in env_overrides:
            cfg.features = cfg.features.model_copy(update=env_overrides["features"])
        if "alert" in env_overrides:
            cfg.alert = cfg.alert.model_copy(update=env_overrides["alert"])
        if "hardware" in env_overrides:
            cfg.hardware = cfg.hardware.model_copy(update=env_overrides["hardware"])
        if "risk" in env_overrides:
            cfg.risk = cfg.risk.model_copy(update=env_overrides["risk"])
        if "firebase" in env_overrides:
            cfg.firebase = FirebaseSettings(**env_overrides["firebase"])
    return cfg

