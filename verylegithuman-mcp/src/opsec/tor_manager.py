"""Tor integration with dual backend: Stem (daemon) and Torpy (pure Python).

Stem requires a running Tor daemon. Torpy is a pure Python fallback.
All sync Stem calls wrapped in asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx

from ..config import (
    GEOLOCATION_TIMEOUT,
    IP_CHECK_URL,
    TOR_CONTROL_PASSWORD,
    TOR_CONTROL_PORT,
    TOR_SOCKS_PORT,
)

logger = logging.getLogger(__name__)

_STEM_AVAILABLE = False
try:
    from stem import Signal
    from stem.control import Controller
    _STEM_AVAILABLE = True
except ImportError:
    logger.info("stem not installed — Tor daemon control unavailable")

_TORPY_AVAILABLE = False
try:
    import torpy
    _TORPY_AVAILABLE = True
except ImportError:
    logger.info("torpy not installed — Pure Python Tor unavailable")


def _sync_stem_check() -> bool:
    """Check if Tor daemon is running (sync, for use with to_thread)."""
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
            ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
            return True
    except Exception:
        return False


def _sync_stem_version() -> str:
    with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
        ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
        return str(ctrl.get_version())


def _sync_stem_newnym() -> None:
    with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
        ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
        ctrl.signal(Signal.NEWNYM)
    time.sleep(2)  # Wait for new circuit (sync sleep is fine inside to_thread)


def _sync_stem_circuits() -> list[dict]:
    with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
        ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
        return [
            {
                "id": circ.id,
                "status": circ.status,
                "path": [fp for fp, _ in circ.path] if circ.path else [],
            }
            for circ in ctrl.get_circuits()
        ]


def get_available_backend() -> Optional[str]:
    """Detect which Tor backend is available. Stem preferred over Torpy.

    Note: This is sync and calls Stem directly. Callers in async context
    should use await asyncio.to_thread(get_available_backend).
    """
    if _STEM_AVAILABLE:
        if _sync_stem_check():
            return "stem"
    if _TORPY_AVAILABLE:
        return "torpy"
    return None


def get_socks_url() -> str:
    return f"socks5://127.0.0.1:{TOR_SOCKS_PORT}"


async def start_tor(country: Optional[str] = None) -> dict:
    backend = await asyncio.to_thread(get_available_backend)

    if backend == "stem":
        try:
            version = await asyncio.to_thread(_sync_stem_version)
            exit_ip = await _get_exit_ip()
            return {
                "backend": "stem",
                "socks_url": get_socks_url(),
                "exit_ip": exit_ip,
                "tor_version": version,
                "status": "connected",
                "country_filter": country,
            }
        except Exception as e:
            return {"backend": "stem", "status": "error", "error": str(e)}

    elif backend == "torpy":
        return {
            "backend": "torpy",
            "socks_url": get_socks_url(),
            "status": "available",
            "note": "Torpy provides direct HTTP wrapping. Use socks_url for browser proxy.",
        }

    return {
        "backend": None,
        "status": "unavailable",
        "error": "Neither stem nor torpy is available. Install: pip install stem (+ Tor daemon) or pip install torpy",
    }


async def new_identity() -> dict:
    if not _STEM_AVAILABLE:
        return {"error": "Stem not available. New identity requires Tor daemon + stem."}

    try:
        await asyncio.to_thread(_sync_stem_newnym)
        exit_ip = await _get_exit_ip()
        return {
            "status": "new_identity_requested",
            "exit_ip": exit_ip,
            "socks_url": get_socks_url(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_status() -> dict:
    backend = await asyncio.to_thread(get_available_backend)

    if backend == "stem":
        try:
            circuits = await asyncio.to_thread(_sync_stem_circuits)
            exit_ip = await _get_exit_ip()
            return {
                "backend": "stem",
                "status": "connected",
                "exit_ip": exit_ip,
                "circuit_count": len(circuits),
                "circuits": circuits[:5],
            }
        except Exception as e:
            return {"backend": "stem", "status": "error", "error": str(e)}

    elif backend == "torpy":
        return {
            "backend": "torpy",
            "status": "available",
            "note": "Torpy doesn't support circuit inspection.",
        }

    return {"backend": None, "status": "unavailable"}


async def _get_exit_ip() -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            proxy=get_socks_url(),
            timeout=GEOLOCATION_TIMEOUT,
        ) as client:
            resp = await client.get(IP_CHECK_URL)
            data = resp.json()
            return data.get("ip", resp.text.strip())
    except Exception:
        return None
