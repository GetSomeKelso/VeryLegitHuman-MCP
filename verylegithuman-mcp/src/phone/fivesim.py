"""5sim.net REST API client for cheap phone verification.

Requires env var: FIVESIM_API_KEY.
Cost: ~$0.008-0.50 per verification depending on country/service.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import FIVESIM_API_KEY, FIVESIM_BASE_URL, FIVESIM_TIMEOUT

logger = logging.getLogger(__name__)


def _check_available() -> None:
    if not FIVESIM_API_KEY:
        raise RuntimeError("FIVESIM_API_KEY environment variable not set")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {FIVESIM_API_KEY}",
        "Accept": "application/json",
    }


async def get_available_products(country: str = "any", service: str = "any") -> dict:
    """List available products and prices.

    Args:
        country: Country code (e.g., "russia", "usa", "any").
        service: Service name (e.g., "google", "facebook", "any").
    """
    _check_available()
    async with httpx.AsyncClient(timeout=FIVESIM_TIMEOUT) as client:
        resp = await client.get(
            f"{FIVESIM_BASE_URL}/guest/products/{country}/{service}",
        )
        resp.raise_for_status()
        return resp.json()


async def buy_activation(
    country: str = "any",
    operator: str = "any",
    service: str = "any",
) -> dict:
    """Buy a phone number activation for verification.

    Returns dict with: order_id, number, country, operator, provider.
    """
    _check_available()
    async with httpx.AsyncClient(timeout=FIVESIM_TIMEOUT) as client:
        resp = await client.get(
            f"{FIVESIM_BASE_URL}/user/buy/activation/{country}/{operator}/{service}",
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "order_id": str(data.get("id", "")),
        "number": data.get("phone", ""),
        "country": data.get("country", country),
        "operator": data.get("operator", operator),
        "service": service,
        "status": data.get("status", ""),
        "provider": "fivesim",
        "provider_id": str(data.get("id", "")),
    }


async def check_order(order_id: str) -> dict:
    """Check status of an activation order (poll for SMS).

    Returns dict with: status, sms (list of received messages).
    """
    _check_available()
    async with httpx.AsyncClient(timeout=FIVESIM_TIMEOUT) as client:
        resp = await client.get(
            f"{FIVESIM_BASE_URL}/user/check/{order_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    sms_list = data.get("sms", []) or []
    return {
        "order_id": order_id,
        "status": data.get("status", ""),
        "number": data.get("phone", ""),
        "sms": [
            {
                "id": str(s.get("id", "")),
                "from_number": s.get("sender", ""),
                "body": s.get("text", s.get("code", "")),
                "received_at": s.get("created_at", ""),
            }
            for s in sms_list
        ],
    }


async def finish_order(order_id: str) -> bool:
    """Mark an activation as finished (confirms SMS received)."""
    _check_available()
    async with httpx.AsyncClient(timeout=FIVESIM_TIMEOUT) as client:
        resp = await client.get(
            f"{FIVESIM_BASE_URL}/user/finish/{order_id}",
            headers=_headers(),
        )
        return resp.status_code == 200


async def cancel_order(order_id: str) -> bool:
    """Cancel an activation order (if no SMS received yet)."""
    _check_available()
    async with httpx.AsyncClient(timeout=FIVESIM_TIMEOUT) as client:
        resp = await client.get(
            f"{FIVESIM_BASE_URL}/user/cancel/{order_id}",
            headers=_headers(),
        )
        return resp.status_code == 200
