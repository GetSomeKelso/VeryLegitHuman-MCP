"""Tor integration with dual backend: Stem (daemon) and Torpy (pure Python).

Stem requires a running Tor daemon. Torpy is a pure Python fallback.
Both provide SOCKS5 proxy URLs for browser/request routing.
"""

from __future__ import annotations

import logging
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

# Check availability of both backends
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


def get_available_backend() -> Optional[str]:
    """Detect which Tor backend is available. Stem preferred over Torpy."""
    if _STEM_AVAILABLE:
        # Check if Tor daemon is actually running
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
                ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
                return "stem"
        except Exception:
            pass
    if _TORPY_AVAILABLE:
        return "torpy"
    return None


def get_socks_url() -> str:
    """Return the Tor SOCKS5 proxy URL."""
    return f"socks5://127.0.0.1:{TOR_SOCKS_PORT}"


async def start_tor(country: Optional[str] = None) -> dict:
    """Start/verify Tor connection and return SOCKS5 proxy details.

    For Stem: verifies daemon is running and responsive.
    For Torpy: starts a pure Python Tor connection.
    """
    backend = get_available_backend()

    if backend == "stem":
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
                ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
                version = str(ctrl.get_version())
                # Get current exit IP
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
            "note": "Torpy provides direct HTTP wrapping. Use socks_url for browser proxy or use torpy requests adapter.",
        }

    else:
        return {
            "backend": None,
            "status": "unavailable",
            "error": "Neither stem nor torpy is available. Install: pip install stem (+ Tor daemon) or pip install torpy",
        }


async def new_identity() -> dict:
    """Request a new Tor circuit (new exit IP).

    Only works with Stem backend (requires Tor daemon).
    """
    if not _STEM_AVAILABLE:
        return {"error": "Stem not available. New identity requires Tor daemon + stem."}

    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
            ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
            ctrl.signal(Signal.NEWNYM)
            # Wait briefly then check new IP
            import asyncio
            await asyncio.sleep(2)
            exit_ip = await _get_exit_ip()
            return {
                "status": "new_identity_requested",
                "exit_ip": exit_ip,
                "socks_url": get_socks_url(),
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_status() -> dict:
    """Get current Tor connection status and circuit info."""
    backend = get_available_backend()

    if backend == "stem":
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
                ctrl.authenticate(password=TOR_CONTROL_PASSWORD)
                circuits = []
                for circ in ctrl.get_circuits():
                    circuits.append({
                        "id": circ.id,
                        "status": circ.status,
                        "path": [fp for fp, _ in circ.path] if circ.path else [],
                    })
                exit_ip = await _get_exit_ip()
                return {
                    "backend": "stem",
                    "status": "connected",
                    "exit_ip": exit_ip,
                    "circuit_count": len(circuits),
                    "circuits": circuits[:5],  # Limit to 5 for readability
                }
        except Exception as e:
            return {"backend": "stem", "status": "error", "error": str(e)}

    elif backend == "torpy":
        return {
            "backend": "torpy",
            "status": "available",
            "note": "Torpy doesn't support circuit inspection. Use start_tor to establish connection.",
        }

    else:
        return {"backend": None, "status": "unavailable"}


async def _get_exit_ip() -> Optional[str]:
    """Get current Tor exit IP via the SOCKS5 proxy."""
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
