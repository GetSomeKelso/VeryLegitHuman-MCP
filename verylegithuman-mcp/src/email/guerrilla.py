"""Guerrilla Mail JSON API client for temporary email.

Free, session-based (sid_token), no account creation needed.
Flow: get_email_address → check_email (poll) → fetch_email
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import GUERRILLA_BASE_URL, GUERRILLA_TIMEOUT

logger = logging.getLogger(__name__)


async def get_email_address(preferred_username: Optional[str] = None) -> dict:
    """Get a new Guerrilla Mail address.

    Returns dict with: address, sid_token, domain, alias.
    """
    params = {"f": "get_email_address", "lang": "en"}
    async with httpx.AsyncClient(timeout=GUERRILLA_TIMEOUT) as client:
        resp = await client.get(GUERRILLA_BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    result = {
        "address": data.get("email_addr", ""),
        "sid_token": data.get("sid_token", ""),
        "domain": data.get("email_addr", "").split("@")[-1] if "@" in data.get("email_addr", "") else "",
        "alias": data.get("alias", ""),
        "provider": "guerrilla",
    }

    # Set preferred username if provided
    if preferred_username and result["sid_token"]:
        params2 = {
            "f": "set_email_user",
            "email_user": preferred_username,
            "lang": "en",
            "sid_token": result["sid_token"],
        }
        async with httpx.AsyncClient(timeout=GUERRILLA_TIMEOUT) as client:
            resp2 = await client.get(GUERRILLA_BASE_URL, params=params2)
            if resp2.status_code == 200:
                data2 = resp2.json()
                result["address"] = data2.get("email_addr", result["address"])
                result["alias"] = data2.get("alias", result["alias"])

    return result


async def check_email(sid_token: str, seq: int = 0) -> list[dict]:
    """Check inbox for new messages.

    Args:
        sid_token: Session token from get_email_address.
        seq: Sequence number (0 = get all, >0 = get messages after this ID).
    """
    params = {
        "f": "check_email",
        "sid_token": sid_token,
        "seq": seq,
    }
    async with httpx.AsyncClient(timeout=GUERRILLA_TIMEOUT) as client:
        resp = await client.get(GUERRILLA_BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    messages = data.get("list", [])
    return [
        {
            "id": str(m.get("mail_id", "")),
            "from_address": m.get("mail_from", ""),
            "subject": m.get("mail_subject", ""),
            "intro": m.get("mail_excerpt", ""),
            "received_at": m.get("mail_timestamp", ""),
            "is_read": bool(m.get("mail_read", 0)),
        }
        for m in messages
    ]


async def fetch_email(sid_token: str, mail_id: str) -> dict:
    """Fetch full email content by mail_id."""
    params = {
        "f": "fetch_email",
        "sid_token": sid_token,
        "email_id": mail_id,
    }
    async with httpx.AsyncClient(timeout=GUERRILLA_TIMEOUT) as client:
        resp = await client.get(GUERRILLA_BASE_URL, params=params)
        resp.raise_for_status()
        m = resp.json()

    return {
        "id": str(m.get("mail_id", "")),
        "from_address": m.get("mail_from", ""),
        "subject": m.get("mail_subject", ""),
        "body_text": m.get("mail_body", ""),
        "body_html": m.get("mail_body", ""),
        "received_at": m.get("mail_timestamp", ""),
    }
