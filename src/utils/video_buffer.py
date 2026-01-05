from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Optional

import cv2
import numpy as np

from .logger import get_logger


class RingBufferRecorder:
    """
    Maintains an in-memory video ring buffer and supports exporting clips.

    Designed for lightweight accident pre/post event recording on Raspberry Pi.
    """

    def __init__(
        self,
        fps: int = 20,
        seconds: int = 12,
        resolution: tuple[int, int] = (640, 480),
        codec: str = "mp4v",
        log_dir: Optional[Path] = None,
    ) -> None:
        self.fps = fps
        self.buff_size = max(1, fps * seconds)
        self.resolution = resolution
        self.codec = codec
        self.buffer: Deque[tuple[float, bytes]] = deque(maxlen=self.buff_size)
        self._lock = threading.Lock()
        self.logger = get_logger("RingBufferRecorder", log_dir)

    def append_frame(self, frame: bytes, timestamp: Optional[float] = None) -> None:
        ts = timestamp or time.time()
        with self._lock:
            self.buffer.append((ts, frame))

    def export_clip(
        self,
        output_path: Path,
        seconds_before: float = 6.0,
        seconds_after: float = 6.0,
        event_time: Optional[float] = None,
    ) -> Optional[Path]:
        """
        Export a clip around the event time from the ring buffer.
        """

        if not self.buffer:
            self.logger.warning("Ring buffer empty; skipping clip export.")
            return None

        event_time = event_time or time.time()
        with self._lock:
            frames = list(self.buffer)

        pre_window = event_time - seconds_before
        post_window = event_time + seconds_after
        selected = [
            (ts, frame) for ts, frame in frames if pre_window <= ts <= post_window
        ]

        if not selected:
            self.logger.warning("No frames found in requested window.")
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = None
        try:
            for _, frame_bytes in selected:
                frame = self._decode_frame(frame_bytes)
                if frame is None:
                    continue

                if writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*self.codec)
                    writer = cv2.VideoWriter(
                        str(output_path), fourcc, self.fps, self.resolution
                    )

                writer.write(frame)
        finally:
            if writer is not None:
                writer.release()

        self.logger.info("Exported clip to %s", output_path)
        return output_path

    def _decode_frame(self, frame_bytes: bytes):
        np_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        return frame

