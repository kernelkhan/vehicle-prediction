from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.utils.logger import get_logger


@dataclass
class FirebaseConfig:
    credentials_path: Optional[str] = None
    database_url: Optional[str] = None
    storage_bucket: Optional[str] = None


class FirebaseClient:
    """
    Lightweight wrapper around firebase_admin SDK.
    """

    def __init__(self, config: FirebaseConfig, log_dir=None):
        self.logger = get_logger("FirebaseClient", log_dir)
        self.config = config
        self.app = None
        self.db = None
        self.bucket = None
        self._initialize()

    def _initialize(self):
        if not self.config.credentials_path:
            self.logger.warning("Firebase credentials not provided; uploads disabled.")
            return
        try:
            import firebase_admin
            from firebase_admin import credentials, db, storage

            cred = credentials.Certificate(self.config.credentials_path)
            self.app = firebase_admin.initialize_app(
                cred,
                {
                    "databaseURL": self.config.database_url,
                    "storageBucket": self.config.storage_bucket,
                }
                if self.config.database_url or self.config.storage_bucket
                else None,
            )
            self.db = db
            self.bucket = storage.bucket() if self.config.storage_bucket else None
            self.logger.info("Firebase client initialized.")
        except Exception as exc:
            self.logger.error("Failed to initialize Firebase: %s", exc)
            self.app = None

    def log_event(self, data: Dict[str, Any]) -> None:
        if not self.db:
            self.logger.debug("Firebase DB unavailable, skipping log_event.")
            return
        try:
            ref = self.db.reference("events")
            ref.push(data)
            self.logger.info("Pushed event to Firebase.")
        except Exception as exc:
            self.logger.error("Failed to push event to Firebase: %s", exc)

    def upload_media(self, local_path: str, destination: str) -> Optional[str]:
        if not self.bucket:
            self.logger.debug("Firebase storage unavailable; skipping upload.")
            return None
        try:
            blob = self.bucket.blob(destination)
            blob.upload_from_filename(local_path)
            blob.make_public()
            self.logger.info("Uploaded media to Firebase storage at %s", destination)
            return blob.public_url
        except Exception as exc:
            self.logger.error("Failed to upload media: %s", exc)
            return None

