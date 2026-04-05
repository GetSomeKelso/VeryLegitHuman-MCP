"""Username availability checking via Sherlock subprocess."""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from typing import Optional

from ..config import DEFAULT_PLATFORMS, SHERLOCK_TIMEOUT

logger = logging.getLogger(__name__)


def _sherlock_available() -> bool:
    """Check if sherlock CLI is installed."""
    return shutil.which("sherlock") is not None


async def check_username_availability(
    username: str,
    platforms: Optional[list[str]] = None,
) -> dict:
    """Check username availability across platforms using Sherlock.

    Uses asyncio.create_subprocess_exec (not shell) for safety.
    Falls back to a stub result if Sherlock is not installed.
    Returns dict with username, platform results, and metadata.
    """
    target_platforms = platforms or DEFAULT_PLATFORMS[:20]
    checked_at = datetime.utcnow().isoformat()

    if not _sherlock_available():
        logger.warning("Sherlock not installed — returning unchecked results")
        return {
            "username": username,
            "platforms": {p: None for p in target_platforms},
            "checked_at": checked_at,
            "sherlock_installed": False,
            "note": "Install sherlock-project for real availability checks: pip install sherlock-project",
        }

    # Build args list for subprocess_exec (no shell injection risk)
    args = [
        username,
        "--print-found",
        "--timeout", "10",
    ]

    # Add site filters if specific platforms requested
    if platforms:
        for p in platforms:
            args.extend(["--site", p])

    try:
        proc = await asyncio.create_subprocess_exec(
            "sherlock", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=SHERLOCK_TIMEOUT,
        )

        output = stdout.decode("utf-8", errors="replace")
        # Parse Sherlock output — lines with "[+]" indicate found (taken) accounts
        found_platforms: set[str] = set()
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("[+]"):
                # Format: "[+] PlatformName: https://..."
                parts = line.split(":", 1)
                if parts:
                    platform_name = parts[0].replace("[+]", "").strip().lower()
                    found_platforms.add(platform_name)

        # Build availability dict: True = available (not found), False = taken
        results: dict[str, bool] = {}
        for p in target_platforms:
            p_lower = p.lower()
            results[p] = p_lower not in found_platforms

        return {
            "username": username,
            "platforms": results,
            "checked_at": checked_at,
            "sherlock_installed": True,
            "found_count": len(found_platforms),
            "available_count": sum(1 for v in results.values() if v),
        }

    except asyncio.TimeoutError:
        logger.error("Sherlock timed out after %ds for username '%s'", SHERLOCK_TIMEOUT, username)
        return {
            "username": username,
            "platforms": {p: None for p in target_platforms},
            "checked_at": checked_at,
            "sherlock_installed": True,
            "error": f"Sherlock timed out after {SHERLOCK_TIMEOUT}s",
        }
    except Exception as e:
        logger.error("Sherlock error for '%s': %s", username, e)
        return {
            "username": username,
            "platforms": {p: None for p in target_platforms},
            "checked_at": checked_at,
            "sherlock_installed": True,
            "error": str(e),
        }
