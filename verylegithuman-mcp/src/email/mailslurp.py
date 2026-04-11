"""MailSlurp SDK wrapper for email provisioning.

Requires API key (env var MAILSLURP_API_KEY).
All sync SDK calls wrapped in asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..config import MAILSLURP_API_KEY

logger = logging.getLogger(__name__)

_SDK_AVAILABLE = False
try:
    import mailslurp_client
    _SDK_AVAILABLE = True
except ImportError:
    logger.info("mailslurp-client not installed — MailSlurp provider unavailable")


def _check_available() -> None:
    if not _SDK_AVAILABLE:
        raise RuntimeError("mailslurp-client not installed. Run: pip install mailslurp-client")
    if not MAILSLURP_API_KEY:
        raise RuntimeError("MAILSLURP_API_KEY environment variable not set")


def _get_config():
    _check_available()
    config = mailslurp_client.Configuration()
    config.api_key["x-api-key"] = MAILSLURP_API_KEY
    return config


def _sync_create_inbox():
    config = _get_config()
    with mailslurp_client.ApiClient(config) as api_client:
        inbox = mailslurp_client.InboxControllerApi(api_client).create_inbox_with_defaults()
    return {
        "address": inbox.email_address,
        "inbox_id": inbox.id,
        "domain": inbox.email_address.split("@")[-1] if "@" in inbox.email_address else "",
        "provider": "mailslurp",
    }


def _sync_get_messages(inbox_id: str, limit: int):
    config = _get_config()
    with mailslurp_client.ApiClient(config) as api_client:
        emails = mailslurp_client.InboxControllerApi(api_client).get_emails(inbox_id, size=limit, sort="DESC")
    return [
        {
            "id": str(e.id),
            "from_address": e.sender.raw_value if hasattr(e, "sender") and e.sender else str(getattr(e, "from_", "")),
            "subject": e.subject or "",
            "intro": (e.body_excerpt or "")[:200] if hasattr(e, "body_excerpt") else "",
            "received_at": str(e.created_at) if e.created_at else "",
            "is_read": getattr(e, "read", False),
        }
        for e in emails
    ]


def _sync_read_message(email_id: str):
    config = _get_config()
    with mailslurp_client.ApiClient(config) as api_client:
        email = mailslurp_client.EmailControllerApi(api_client).get_email(email_id)
    return {
        "id": str(email.id),
        "from_address": str(getattr(email, "from_", "")),
        "subject": email.subject or "",
        "body_text": email.body or "",
        "body_html": email.body or "",
        "received_at": str(email.created_at) if email.created_at else "",
    }


def _sync_delete_inbox(inbox_id: str):
    config = _get_config()
    with mailslurp_client.ApiClient(config) as api_client:
        mailslurp_client.InboxControllerApi(api_client).delete_inbox(inbox_id)
    return True


async def create_inbox(name: Optional[str] = None) -> dict:
    _check_available()
    return await asyncio.to_thread(_sync_create_inbox)


async def get_messages(inbox_id: str, limit: int = 20) -> list[dict]:
    _check_available()
    return await asyncio.to_thread(_sync_get_messages, inbox_id, limit)


async def read_message(email_id: str) -> dict:
    _check_available()
    return await asyncio.to_thread(_sync_read_message, email_id)


async def delete_inbox(inbox_id: str) -> bool:
    _check_available()
    return await asyncio.to_thread(_sync_delete_inbox, inbox_id)
