from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger


@dataclass
class AlertMessage:
    body: str
    media_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Notifier:
    """
    Sends alerts via SMS/WhatsApp using Twilio. Supports email fallback.
    """

    def __init__(
        self,
        sms_enabled: bool,
        whatsapp_enabled: bool,
        twilio_sid: Optional[str],
        twilio_token: Optional[str],
        sms_from: Optional[str],
        whatsapp_from: Optional[str],
        sms_to: Optional[str],
        whatsapp_to: Optional[str],
        email_to: Optional[str] = None,
        log_dir=None,
    ) -> None:
        self.sms_enabled = sms_enabled
        self.whatsapp_enabled = whatsapp_enabled
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token
        self.sms_from = sms_from
        self.whatsapp_from = whatsapp_from
        self.sms_to = sms_to
        self.whatsapp_to = whatsapp_to
        self.email_to = email_to
        self.logger = get_logger("Notifier", log_dir)
        self._twilio_client = self._init_twilio()

    def _init_twilio(self):
        if not (self.twilio_sid and self.twilio_token):
            self.logger.warning("Twilio credentials not provided - alerts limited.")
            return None
        try:
            from twilio.rest import Client

            return Client(self.twilio_sid, self.twilio_token)
        except Exception as exc:
            self.logger.error("Failed to initialize Twilio client: %s", exc)
            return None

    def send_alert(self, message: AlertMessage) -> None:
        if self.sms_enabled and self.sms_to and self.sms_from:
            self._send_twilio(message, channel="sms")
        if self.whatsapp_enabled and self.whatsapp_to and self.whatsapp_from:
            self._send_twilio(message, channel="whatsapp")
        if self.email_to:
            self._send_email(message)

    def _send_twilio(self, message: AlertMessage, channel: str) -> None:
        if not self._twilio_client:
            self.logger.warning("Twilio client unavailable; skipping %s alert.", channel)
            return

        to = self.sms_to if channel == "sms" else f"whatsapp:{self.whatsapp_to}"
        from_ = self.sms_from if channel == "sms" else f"whatsapp:{self.whatsapp_from}"

        try:
            payload = {
                "body": message.body,
                "from_": from_,
                "to": to,
            }
            if message.media_url:
                payload["media_url"] = [message.media_url]
            self._twilio_client.messages.create(**payload)
            self.logger.info("Dispatched %s alert to %s", channel, to)
        except Exception as exc:
            self.logger.error("Failed to send %s alert: %s", channel, exc)

    def _send_email(self, message: AlertMessage) -> None:
        try:
            import smtplib
            from email.message import EmailMessage

            email = EmailMessage()
            email["Subject"] = "Accident Alert"
            email["From"] = self.email_to
            email["To"] = self.email_to
            email.set_content(message.body)
            with smtplib.SMTP("localhost") as smtp:
                smtp.send_message(email)
            self.logger.info("Email alert sent to %s", self.email_to)
        except Exception as exc:
            self.logger.warning("Email alert failed: %s", exc)

