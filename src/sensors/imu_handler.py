from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from src.utils.helpers import MovingAverage
from src.utils.logger import get_logger


@dataclass
class IMUReading:
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    jerk: float
    timestamp: float


class IMUHandler:
    """
    Interface for MPU-6050. Provides smoothed acceleration and jerk detection.
    Falls back to simulated readings if hardware not detected.
    """

    def __init__(self, address: int = 0x68, bus_id: int = 1, log_dir=None):
        self.address = address
        self.bus_id = bus_id
        self.logger = get_logger("IMUHandler", log_dir)
        self._imu = None
        self._accel_avg = MovingAverage(5)
        self._last_accel = None
        self._last_time = None
        self._setup()

    def _setup(self):
        try:
            from mpu6050 import mpu6050

            self._imu = mpu6050(self.address, bus=self.bus_id)
            self.logger.info("MPU-6050 initialized on bus %s address 0x%X", self.bus_id, self.address)
        except Exception as exc:  # pragma: no cover - hardware specific
            self.logger.warning("IMU not available: %s. Using simulated readings.", exc)
            self._imu = None

    def read(self) -> IMUReading:
        timestamp = time.time()
        if self._imu:
            data = self._imu.get_all_data()
            accel = data[0]
            gyro = data[1]
        else:
            accel = {"x": 0.0, "y": 0.0, "z": 9.81}
            gyro = {"x": 0.0, "y": 0.0, "z": 0.0}

        ax = self._accel_avg.update(accel["x"])
        ay = self._accel_avg.update(accel["y"])
        az = self._accel_avg.update(accel["z"])

        jerk = 0.0
        if self._last_accel is not None and self._last_time is not None:
            dt = max(timestamp - self._last_time, 1e-3)
            delta = math.sqrt(
                (ax - self._last_accel[0]) ** 2
                + (ay - self._last_accel[1]) ** 2
                + (az - self._last_accel[2]) ** 2
            )
            jerk = delta / dt

        self._last_accel = (ax, ay, az)
        self._last_time = timestamp

        return IMUReading(
            ax=ax,
            ay=ay,
            az=az,
            gx=gyro["x"],
            gy=gyro["y"],
            gz=gyro["z"],
            jerk=jerk,
            timestamp=timestamp,
        )

