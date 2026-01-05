from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2

from src.utils.logger import get_logger


class MediaManager:
    """
    Handles persistence of snapshots and clips on local storage.
    """

    def __init__(self, base_dir: Path, log_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("MediaManager", log_dir)

    def save_snapshot(self, frame, filename: str) -> Path:
        path = self.base_dir / "snapshots" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(path), frame)
        if not success:
            raise IOError(f"Failed to write snapshot to {path}")
        self.logger.info("Saved snapshot to %s", path)
        return path

    def attach_clip(self, clip_path: Path) -> Path:
        target = self.base_dir / "clips" / clip_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if clip_path.resolve() != target.resolve():
            target.write_bytes(clip_path.read_bytes())
        self.logger.info("Stored clip at %s", target)
        return target

