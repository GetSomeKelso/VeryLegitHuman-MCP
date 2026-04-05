"""Mail.tm REST API client for temporary email provisioning.

Free, no auth required for domain listing.
Flow: GET /domains → POST /accounts → POST /token → GET /messages
"""

from __future__ import annotations

import logging
import random
import string
from typing import Optional

import httpx

from ..config import MAILTM_BASE_URL, MAILTM_TIMEOUT

logger = logging.getLogger(__name__)

_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


async def get_domains() -> list[dict]:
    """Fetch available email domains from Mail.tm."""
    async with httpx.AsyncClient(timeout=MAILTM_TIMEOUT) as client:
        resp = await client.get(f"{MAILTM_BASE_URL}/domains", headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        # API returns {"hydra:member": [...]} or list directly
        if isinstance(data, dict):
            return data.get("hydra:member", data.get("member", []))
        return data


async def create_account(
    preferred_username: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """Create a new Mail.tm email account.

    Returns dict with: address, password, token, domain, account_id.
    """
    # Get available domains
    domains = await get_domains()
    if not domains:
        raise RuntimeError("No Mail.tm domains available")

    domain_info = domains[0]
    domain = domain_info.get("domain", domain_info.get("name", ""))

    # Generate username
    if preferred_username:
        username = preferred_username.lower().replace(" ", "")
    else:
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))

    address = f"{username}@{domain}"

    # Generate password if not provided
    if not password:
        password = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%", k=16))

    async with httpx.AsyncClient(timeout=MAILTM_TIMEOUT) as client:
        # Create account
        create_resp = await client.post(
            f"{MAILTM_BASE_URL}/accounts",
            json={"address": address, "password": password},
            headers=_HEADERS,
        )
        if create_resp.status_code == 422:
            # Address taken — try with random suffix
            username = f"{username}{random.randint(100, 999)}"
            address = f"{username}@{domain}"
            create_resp = await client.post(
                f"{MAILTM_BASE_URL}/accounts",
                json={"address": address, "password": password},
                headers=_HEADERS,
            )
        create_resp.raise_for_status()
        account_data = create_resp.json()

        # Get auth token
        token_resp = await client.post(
            f"{MAILTM_BASE_URL}/token",
            json={"address": address, "password": password},
            headers=_HEADERS,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    return {
        "address": address,
        "password": password,
        "token": token_data.get("token", ""),
        "domain": domain,
        "account_id": account_data.get("id", ""),
        "provider": "mailtm",
    }


async def get_messages(token: str, page: int = 1) -> list[dict]:
    """Fetch messages for an authenticated Mail.tm account."""
    async with httpx.AsyncClient(timeout=MAILTM_TIMEOUT) as client:
        resp = await client.get(
            f"{MAILTM_BASE_URL}/messages",
            params={"page": page},
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        messages = data.get("hydra:member", data.get("member", []))
        return [
            {
                "id": m.get("id", ""),
                "from_address": m.get("from", {}).get("address", "") if isinstance(m.get("from"), dict) else str(m.get("from", "")),
                "subject": m.get("subject", ""),
                "intro": m.get("intro", ""),
                "received_at": m.get("createdAt", ""),
                "is_read": m.get("seen", False),
            }
            for m in messages
        ]


async def read_message(token: str, message_id: str) -> dict:
    """Read a specific message by ID."""
    async with httpx.AsyncClient(timeout=MAILTM_TIMEOUT) as client:
        resp = await client.get(
            f"{MAILTM_BASE_URL}/messages/{message_id}",
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        m = resp.json()
        return {
            "id": m.get("id", ""),
            "from_address": m.get("from", {}).get("address", "") if isinstance(m.get("from"), dict) else str(m.get("from", "")),
            "subject": m.get("subject", ""),
            "body_text": m.get("text", ""),
            "body_html": m.get("html", [None])[0] if isinstance(m.get("html"), list) else m.get("html", ""),
            "received_at": m.get("createdAt", ""),
        }


async def delete_account(token: str, account_id: str) -> bool:
    """Delete a Mail.tm account."""
    async with httpx.AsyncClient(timeout=MAILTM_TIMEOUT) as client:
        resp = await client.delete(
            f"{MAILTM_BASE_URL}/accounts/{account_id}",
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
        )
        return resp.status_code in (200, 204)
