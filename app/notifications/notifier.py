"""NotifierProtocol and TelegramNotifier implementation."""
import asyncio
from typing import Protocol, runtime_checkable
import httpx
from app.core.config import settings
from app.core.logging import logger


@runtime_checkable
class NotifierProtocol(Protocol):

    async def send(self, message: str) -> None:
        ...


class TelegramNotifier:

    def __init__(self):
        self._token = (
            settings.TELEGRAM_BOT_TOKEN.get_secret_value()
            if settings.TELEGRAM_BOT_TOKEN
            else None
        )
        self._chat_id = settings.TELEGRAM_CHAT_ID
        self._url = (
            f"https://api.telegram.org/bot{self._token}/sendMessage"
            if self._token
            else None
        )

    async def send(self, message: str) -> None:
        if not self._url or not self._chat_id:
            return
        asyncio.create_task(
            self._send_payload(
                {"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"}
            )
        )

    async def _send_payload(self, payload: dict) -> None:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(self._url, json=payload, timeout=10.0)
                res.raise_for_status()
        except Exception as e:
            logger.warning(f"Telegram notify failed: {e}")
