"""Mullvad VPN CLI wrapper (Linux only).

Controls Mullvad VPN via asyncio.create_subprocess_exec (safe, no shell).
Gracefully errors on Windows/macOS.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import shutil
from typing import Optional

logger = logging.getLogger(__name__)


def _is_available() -> bool:
    """Check if mullvad CLI is installed and we're on a supported platform."""
    if platform.system() == "Windows":
        return False
    return shutil.which("mullvad") is not None


async def _run_mullvad(*args: str) -> tuple[str, str, int]:
    """Run a mullvad CLI command safely via create_subprocess_exec."""
    proc = await asyncio.create_subprocess_exec(
        "mullvad", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
        proc.returncode or 0,
    )


async def connect(country: Optional[str] = None) -> dict:
    """Connect to Mullvad VPN.

    Args:
        country: Two-letter country code for relay selection (e.g., "us", "se", "de").
    """
    if not _is_available():
        return {
            "status": "unavailable",
            "error": f"Mullvad CLI not available on {platform.system()}. Requires Linux with mullvad-vpn installed.",
        }

    try:
        if country:
            await _run_mullvad("relay", "set", "location", country.lower())
        await _run_mullvad("connect")
        return await status()
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def disconnect() -> dict:
    """Disconnect from Mullvad VPN."""
    if not _is_available():
        return {"status": "unavailable", "error": f"Mullvad CLI not available on {platform.system()}"}

    try:
        await _run_mullvad("disconnect")
        return {"status": "disconnected"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def status() -> dict:
    """Get Mullvad VPN connection status."""
    if not _is_available():
        return {"status": "unavailable", "error": f"Mullvad CLI not available on {platform.system()}"}

    try:
        stdout, _, _ = await _run_mullvad("status")
        connected = "connected" in stdout.lower()
        return {
            "status": "connected" if connected else "disconnected",
            "details": stdout,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
