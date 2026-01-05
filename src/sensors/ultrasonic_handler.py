from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from src.utils.logger import get_logger


@dataclass
class ProximityReading:
    distance_cm: float
    timestamp: float


class UltrasonicHandler:
    """
    Interface for HC-SR04 ultrasonic distance sensor via GPIO.
    Optional component for obstacle awareness.
    """

    def __init__(
        self,
        trigger_pin: int = 23,
        echo_pin: int = 24,
        speed_of_sound: float = 34300.0,  # cm/s
        log_dir=None,
    ) -> None:
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.speed_of_sound = speed_of_sound
        self.logger = get_logger("UltrasonicHandler", log_dir)
        self._gpio = None
        self._setup()

    def _setup(self):
        try:
            import RPi.GPIO as GPIO

            self._gpio = GPIO
            self._gpio.setmode(GPIO.BCM)
            self._gpio.setup(self.trigger_pin, GPIO.OUT)
            self._gpio.setup(self.echo_pin, GPIO.IN)
            self.logger.info(
                "Ultrasonic sensor initialized on trigger=%s echo=%s",
                self.trigger_pin,
                self.echo_pin,
            )
        except Exception as exc:  # pragma: no cover - hardware specific
            self.logger.warning(
                "GPIO unavailable (%s). Ultrasonic sensor will be simulated.", exc
            )
            self._gpio = None

    def read_distance(self) -> Optional[ProximityReading]:
        timestamp = time.time()
        if not self._gpio:
            return ProximityReading(distance_cm=999.0, timestamp=timestamp)

        gpio = self._gpio
        gpio.output(self.trigger_pin, True)
        time.sleep(0.00001)
        gpio.output(self.trigger_pin, False)

        start_time = time.time()
        stop_time = time.time()

        while gpio.input(self.echo_pin) == 0:
            start_time = time.time()
        while gpio.input(self.echo_pin) == 1:
            stop_time = time.time()
        elapsed = stop_time - start_time
        distance = (elapsed * self.speed_of_sound) / 2
        return ProximityReading(distance_cm=distance, timestamp=timestamp)

