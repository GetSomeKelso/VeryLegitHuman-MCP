"""Patchright (stealth Chromium) browser engine.

Patchright is a drop-in Playwright replacement that passes
Cloudflare, Kasada, Akamai, DataDome, and Fingerprint.com detection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import BROWSER_DEFAULT_VIEWPORT, BROWSER_NAVIGATION_TIMEOUT

logger = logging.getLogger(__name__)

_AVAILABLE = False
try:
    from patchright.async_api import async_playwright
    _AVAILABLE = True
except ImportError:
    logger.info("patchright not installed — Chromium stealth engine unavailable")


def is_available() -> bool:
    return _AVAILABLE


async def launch(
    headless: bool = True,
    proxy: Optional[dict] = None,
    user_agent: Optional[str] = None,
    viewport: Optional[tuple[int, int]] = None,
) -> dict:
    """Launch a stealth Chromium browser via Patchright.

    Returns dict with: playwright, browser, context, page objects.
    Caller is responsible for cleanup.
    """
    if not _AVAILABLE:
        raise RuntimeError("patchright not installed. Run: pip install patchright && patchright install chromium")

    pw = await async_playwright().start()

    launch_args = {
        "headless": headless,
    }

    # Proxy config
    if proxy:
        launch_args["proxy"] = {
            "server": proxy["server"],
        }
        if proxy.get("username"):
            launch_args["proxy"]["username"] = proxy["username"]
        if proxy.get("password"):
            launch_args["proxy"]["password"] = proxy["password"]

    browser = await pw.chromium.launch(**launch_args)

    # Context with viewport and optional user agent
    vw, vh = viewport or BROWSER_DEFAULT_VIEWPORT
    context_args: dict[str, Any] = {
        "viewport": {"width": vw, "height": vh},
    }
    if user_agent:
        context_args["user_agent"] = user_agent

    context = await browser.new_context(**context_args)
    context.set_default_timeout(BROWSER_NAVIGATION_TIMEOUT)

    page = await context.new_page()

    return {
        "playwright": pw,
        "browser": browser,
        "context": context,
        "page": page,
        "engine": "patchright",
    }
