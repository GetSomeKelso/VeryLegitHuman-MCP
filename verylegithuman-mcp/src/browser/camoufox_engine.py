"""Camoufox (stealth Firefox) browser engine.

Camoufox is a modified Firefox with market-share-aware fingerprint spoofing,
canvas/WebGL/audio spoofing, and human-like mouse movement.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import BROWSER_DEFAULT_VIEWPORT, BROWSER_NAVIGATION_TIMEOUT

logger = logging.getLogger(__name__)

_AVAILABLE = False
try:
    from camoufox.async_api import AsyncCamoufox
    _AVAILABLE = True
except ImportError:
    logger.info("camoufox not installed — Firefox stealth engine unavailable")


def is_available() -> bool:
    return _AVAILABLE


async def launch(
    headless: bool = True,
    proxy: Optional[dict] = None,
    user_agent: Optional[str] = None,
    viewport: Optional[tuple[int, int]] = None,
) -> dict:
    """Launch a stealth Firefox browser via Camoufox.

    Returns dict with: browser_cm, browser, context, page objects.
    """
    if not _AVAILABLE:
        raise RuntimeError("camoufox not installed. Run: pip install camoufox[geoip]")

    vw, vh = viewport or BROWSER_DEFAULT_VIEWPORT

    launch_kwargs: dict[str, Any] = {
        "headless": headless,
        "humanize": True,
        "window": (vw, vh),
    }

    if proxy:
        launch_kwargs["proxy"] = {
            "server": proxy["server"],
        }
        if proxy.get("username"):
            launch_kwargs["proxy"]["username"] = proxy["username"]
        if proxy.get("password"):
            launch_kwargs["proxy"]["password"] = proxy["password"]

    # AsyncCamoufox is an async context manager
    browser_cm = AsyncCamoufox(**launch_kwargs)
    browser = await browser_cm.__aenter__()

    # Camoufox returns a BrowserContext directly
    page = await browser.new_page()
    page.set_default_timeout(BROWSER_NAVIGATION_TIMEOUT)

    return {
        "playwright": browser_cm,  # Keep for cleanup
        "browser": browser,
        "context": browser,  # context == browser in Camoufox
        "page": page,
        "engine": "camoufox",
    }


async def cleanup(browser_cm: Any) -> None:
    """Clean up a Camoufox browser session."""
    try:
        await browser_cm.__aexit__(None, None, None)
    except Exception as e:
        logger.warning("Camoufox cleanup error: %s", e)
