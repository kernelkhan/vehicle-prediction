from __future__ import annotations

import threading
import time
from typing import Generator, Optional

import cv2


class StreamManager:
    """
    Maintains the most recent frame for live streaming via FastAPI.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[bytes] = None

    def publish(self, frame) -> None:
        success, encoded = cv2.imencode(".jpg", frame)
        if not success:
            return
        with self._lock:
            self._frame = encoded.tobytes()

    def frame_generator(self) -> Generator[bytes, None, None]:
        while True:
            with self._lock:
                frame = self._frame
            if frame is None:
                time.sleep(0.05)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.05)


stream_manager = StreamManager()

