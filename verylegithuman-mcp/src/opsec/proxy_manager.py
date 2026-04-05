"""Proxy management for residential proxy providers + generic URLs.

Supports: IPRoyal, Bright Data, Decodo/Smartproxy, and generic (user-provided).
Generates proxy URLs with sticky sessions and country targeting.
"""

from __future__ import annotations

import logging
import random
import string
import uuid
from datetime import datetime
from typing import Optional

import httpx

from ..config import (
    BRIGHTDATA_CUSTOMER_ID,
    BRIGHTDATA_PROXY_HOST,
    BRIGHTDATA_PROXY_PORT,
    BRIGHTDATA_ZONE_PASSWORD,
    DECODO_PASSWORD,
    DECODO_PROXY_HOST,
    DECODO_PROXY_PORT,
    DECODO_USERNAME,
    GEOLOCATION_TIMEOUT,
    IP_CHECK_URL,
    IPROYAL_API_KEY,
    IPROYAL_PROXY_HOST,
    IPROYAL_PROXY_PORT,
)

logger = logging.getLogger(__name__)


def _random_session_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def generate_proxy_url(
    provider: str,
    country: str = "us",
    city: Optional[str] = None,
    sticky: bool = True,
) -> dict:
    """Generate a proxy URL for the given provider.

    Returns dict with: proxy_url, provider, country, sticky_session.
    Raises RuntimeError if credentials are missing.
    """
    country = country.lower()
    session_id = _random_session_id() if sticky else ""

    if provider == "iproyal":
        if not IPROYAL_API_KEY:
            raise RuntimeError("IPROYAL_API_KEY environment variable not set")
        # IPRoyal format: http://user:pass_country-CC_session-SID@host:port
        password_parts = [IPROYAL_API_KEY, f"country-{country}"]
        if city:
            password_parts.append(f"city-{city}")
        if sticky:
            password_parts.append(f"session-{session_id}")
        password = "_".join(password_parts)
        proxy_url = f"http://customer:{password}@{IPROYAL_PROXY_HOST}:{IPROYAL_PROXY_PORT}"

    elif provider == "brightdata":
        if not BRIGHTDATA_CUSTOMER_ID or not BRIGHTDATA_ZONE_PASSWORD:
            raise RuntimeError("BRIGHTDATA_CUSTOMER_ID and BRIGHTDATA_ZONE_PASSWORD environment variables not set")
        # Bright Data format: http://customer-ID-cc-CC-session-SID:password@host:port
        username_parts = [f"customer-{BRIGHTDATA_CUSTOMER_ID}", f"cc-{country}"]
        if sticky:
            username_parts.append(f"session-{session_id}")
        username = "-".join(username_parts)
        proxy_url = f"http://{username}:{BRIGHTDATA_ZONE_PASSWORD}@{BRIGHTDATA_PROXY_HOST}:{BRIGHTDATA_PROXY_PORT}"

    elif provider == "decodo":
        if not DECODO_USERNAME or not DECODO_PASSWORD:
            raise RuntimeError("DECODO_USERNAME and DECODO_PASSWORD environment variables not set")
        # Decodo/Smartproxy format: http://user-cc-CC-sessid-SID:pass@host:port
        username_parts = [DECODO_USERNAME, f"cc-{country}"]
        if sticky:
            username_parts.append(f"sessid-{session_id}")
        username = "-".join(username_parts)
        proxy_url = f"http://{username}:{DECODO_PASSWORD}@{DECODO_PROXY_HOST}:{DECODO_PROXY_PORT}"

    elif provider == "generic":
        raise ValueError("Generic provider requires proxy_url to be supplied directly")

    else:
        raise ValueError(f"Unknown provider: {provider}")

    return {
        "proxy_url": proxy_url,
        "provider": provider,
        "country": country,
        "city": city,
        "sticky_session": session_id,
    }


def rotate_session(proxy_url: str, provider: str, country: str = "us", city: Optional[str] = None) -> dict:
    """Generate a new proxy URL with a fresh sticky session (new IP)."""
    if provider == "generic":
        return {"proxy_url": proxy_url, "provider": "generic", "note": "Generic proxies cannot be rotated automatically"}
    return generate_proxy_url(provider, country, city, sticky=True)


async def test_proxy_connection(proxy_url: str) -> dict:
    """Test a proxy by making a request through it and returning the exit IP.

    Returns dict with: exit_ip, status, latency_ms.
    """
    try:
        start = datetime.utcnow()
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=GEOLOCATION_TIMEOUT,
            verify=False,
        ) as client:
            resp = await client.get(IP_CHECK_URL)
            resp.raise_for_status()
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            data = resp.json()
            return {
                "exit_ip": data.get("ip", resp.text.strip()),
                "status": "connected",
                "latency_ms": round(elapsed),
                "proxy_url": proxy_url,
            }
    except Exception as e:
        return {
            "exit_ip": None,
            "status": "failed",
            "error": str(e),
            "proxy_url": proxy_url,
        }
