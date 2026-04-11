"""Twilio SDK wrapper for phone number provisioning and SMS.

Requires env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN.
All sync SDK calls wrapped in asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

logger = logging.getLogger(__name__)

_SDK_AVAILABLE = False
try:
    from twilio.rest import Client as TwilioClient
    _SDK_AVAILABLE = True
except ImportError:
    logger.info("twilio not installed — Twilio provider unavailable")


def _check_available() -> None:
    if not _SDK_AVAILABLE:
        raise RuntimeError("twilio not installed. Run: pip install twilio")
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables not set")


def _get_client() -> TwilioClient:
    _check_available()
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def _sync_search(country: str, limit: int):
    client = _get_client()
    numbers = client.available_phone_numbers(country).local.list(sms_enabled=True, limit=limit)
    return [
        {
            "number": n.phone_number,
            "friendly_name": n.friendly_name,
            "locality": getattr(n, "locality", ""),
            "region": getattr(n, "region", ""),
            "capabilities": {
                "sms": getattr(n.capabilities, "sms", True) if hasattr(n, "capabilities") else True,
                "voice": getattr(n.capabilities, "voice", True) if hasattr(n, "capabilities") else True,
            },
        }
        for n in numbers
    ]


def _sync_provision(country: str):
    client = _get_client()
    available = client.available_phone_numbers(country).local.list(sms_enabled=True, limit=1)
    if not available:
        raise RuntimeError(f"No available numbers in {country}")
    incoming = client.incoming_phone_numbers.create(phone_number=available[0].phone_number)
    return {
        "number": incoming.phone_number,
        "provider_id": incoming.sid,
        "country": country,
        "capabilities": {"sms": True, "voice": True},
        "provider": "twilio",
    }


def _sync_get_sms(phone_number: str, limit: int):
    client = _get_client()
    messages = client.messages.list(to=phone_number, limit=limit)
    return [
        {
            "id": m.sid,
            "from_number": m.from_,
            "body": m.body,
            "received_at": str(m.date_sent) if m.date_sent else str(m.date_created),
        }
        for m in messages
    ]


def _sync_release(sid: str):
    client = _get_client()
    client.incoming_phone_numbers(sid).delete()
    return True


async def search_available_numbers(country: str = "US", limit: int = 5) -> list[dict]:
    _check_available()
    return await asyncio.to_thread(_sync_search, country, limit)


async def provision_number(country: str = "US") -> dict:
    _check_available()
    return await asyncio.to_thread(_sync_provision, country)


async def get_incoming_sms(phone_number: str, limit: int = 20) -> list[dict]:
    _check_available()
    return await asyncio.to_thread(_sync_get_sms, phone_number, limit)


async def release_number(sid: str) -> bool:
    _check_available()
    return await asyncio.to_thread(_sync_release, sid)
