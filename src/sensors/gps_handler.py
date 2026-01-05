from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Optional

from src.utils.logger import get_logger


@dataclass
class Location:
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    source: str = "unknown"
    timestamp: float = time.time()


class GPSHandler:
    """
    Reads GPS data from serial NMEA stream. Provides fallback via IP geolocation.
    """

    def __init__(
        self,
        serial_port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        log_dir=None,
    ) -> None:
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.logger = get_logger("GPSHandler", log_dir)
        self._serial = None
        self._setup()

    def _setup(self):
        try:
            import serial

            self._serial = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            self.logger.info("GPS module detected on %s", self.serial_port)
        except Exception as exc:  # pragma: no cover - hardware specific
            self.logger.warning(
                "GPS serial port unavailable: %s. Will use IP geolocation fallback.", exc
            )
            self._serial = None

    def read_location(self) -> Optional[Location]:
        timestamp = time.time()
        if self._serial:
            try:
                import pynmea2

                line = self._serial.readline().decode("ascii", errors="replace")
                if line.startswith("$GPGGA"):
                    msg = pynmea2.parse(line)
                    if msg.latitude and msg.longitude:
                        return Location(
                            latitude=msg.latitude,
                            longitude=msg.longitude,
                            accuracy=float(msg.horizontal_dilution) if msg.horizontal_dilution else None,
                            source="gps",
                            timestamp=timestamp,
                        )
            except Exception as exc:  # pragma: no cover
                self.logger.debug("Failed to parse GPS data: %s", exc)

        return self._ip_fallback(timestamp)

    def _ip_fallback(self, timestamp: float) -> Optional[Location]:
        try:
            import requests

            response = requests.get("https://ipinfo.io/json", timeout=3)
            if response.status_code == 200:
                payload = response.json()
                loc = payload.get("loc")
                if loc:
                    lat, lon = map(float, loc.split(","))
                    return Location(
                        latitude=lat,
                        longitude=lon,
                        accuracy=None,
                        source="ipinfo",
                        timestamp=timestamp,
                    )
        except Exception:
            pass
        return None

