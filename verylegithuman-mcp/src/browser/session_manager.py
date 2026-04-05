"""Managed browser session lifecycle.

Stores live Playwright browser objects in memory, keyed by session UUID.
Supports both Patchright (Chromium) and Camoufox (Firefox) engines.
"""

from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..config import BROWSER_MAX_SESSIONS, BROWSER_SCREENSHOT_DIR, BROWSER_TYPE_DELAY

logger = logging.getLogger(__name__)


@dataclass
class BrowserSession:
    id: str
    engine: str
    browser: Any
    context: Any
    page: Any
    playwright: Any  # Playwright instance (patchright) or AsyncCamoufox cm
    created_at: str
    persona_id: Optional[str] = None
    proxy: Optional[dict] = None
    user_agent: Optional[str] = None

    @property
    def url(self) -> str:
        try:
            return self.page.url
        except Exception:
            return "about:blank"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "engine": self.engine,
            "url": self.url,
            "persona_id": self.persona_id,
            "created_at": self.created_at,
            "user_agent": self.user_agent,
            "has_proxy": self.proxy is not None,
        }


class SessionManager:
    """Manages browser sessions across both engines."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    async def create_session(
        self,
        engine: str = "patchright",
        headless: bool = True,
        proxy: Optional[dict] = None,
        user_agent: Optional[str] = None,
        viewport: Optional[tuple[int, int]] = None,
        persona_id: Optional[str] = None,
    ) -> BrowserSession:
        if len(self._sessions) >= BROWSER_MAX_SESSIONS:
            raise RuntimeError(f"Max {BROWSER_MAX_SESSIONS} concurrent sessions. Close one first.")

        if engine == "patchright":
            from . import patchright_engine
            if not patchright_engine.is_available():
                raise RuntimeError("patchright not installed. Run: pip install patchright && patchright install chromium")
            result = await patchright_engine.launch(
                headless=headless, proxy=proxy, user_agent=user_agent, viewport=viewport,
            )
        elif engine == "camoufox":
            from . import camoufox_engine
            if not camoufox_engine.is_available():
                raise RuntimeError("camoufox not installed. Run: pip install camoufox[geoip]")
            result = await camoufox_engine.launch(
                headless=headless, proxy=proxy, user_agent=user_agent, viewport=viewport,
            )
        else:
            raise ValueError(f"Unknown engine: {engine}. Use 'patchright' or 'camoufox'.")

        session = BrowserSession(
            id=str(uuid.uuid4()),
            engine=engine,
            browser=result["browser"],
            context=result["context"],
            page=result["page"],
            playwright=result["playwright"],
            created_at=datetime.utcnow().isoformat(),
            persona_id=persona_id,
            proxy=proxy,
            user_agent=user_agent,
        )
        self._sessions[session.id] = session
        logger.info("Browser session created: %s (%s)", session.id[:8], engine)
        return session

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if not session:
            return False

        try:
            if session.engine == "camoufox":
                from . import camoufox_engine
                await camoufox_engine.cleanup(session.playwright)
            else:
                # Patchright / standard Playwright cleanup
                await session.context.close()
                await session.browser.close()
                await session.playwright.stop()
        except Exception as e:
            logger.warning("Session cleanup error (%s): %s", session_id[:8], e)

        logger.info("Browser session closed: %s", session_id[:8])
        return True

    async def close_all(self) -> int:
        ids = list(self._sessions.keys())
        count = 0
        for sid in ids:
            if await self.close_session(sid):
                count += 1
        return count

    def list_sessions(self) -> list[dict]:
        return [s.to_dict() for s in self._sessions.values()]

    # --- Page actions ---

    async def goto(self, session_id: str, url: str, wait_until: str = "load") -> dict:
        session = self._get(session_id)
        response = await session.page.goto(url, wait_until=wait_until)
        return {
            "url": session.page.url,
            "title": await session.page.title(),
            "status": response.status if response else None,
        }

    async def back(self, session_id: str) -> dict:
        session = self._get(session_id)
        await session.page.go_back()
        return {"url": session.page.url, "title": await session.page.title()}

    async def click(self, session_id: str, selector: str) -> dict:
        session = self._get(session_id)
        await session.page.click(selector)
        return {"clicked": selector, "url": session.page.url}

    async def type_text(self, session_id: str, selector: str, text: str, delay: int = BROWSER_TYPE_DELAY) -> dict:
        session = self._get(session_id)
        await session.page.fill(selector, "")  # Clear first
        await session.page.type(selector, text, delay=delay)
        return {"typed": len(text), "selector": selector}

    async def select_option(self, session_id: str, selector: str, value: str) -> dict:
        session = self._get(session_id)
        await session.page.select_option(selector, value)
        return {"selected": value, "selector": selector}

    async def screenshot(self, session_id: str, full_page: bool = False) -> dict:
        session = self._get(session_id)
        BROWSER_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id[:8]}_{timestamp}.jpg"
        filepath = BROWSER_SCREENSHOT_DIR / filename

        img_bytes = await session.page.screenshot(full_page=full_page, type="jpeg", quality=80)
        filepath.write_bytes(img_bytes)

        return {
            "file_path": str(filepath),
            "filename": filename,
            "size_bytes": len(img_bytes),
            "base64": base64.b64encode(img_bytes).decode("utf-8"),
            "url": session.page.url,
        }

    async def get_text(self, session_id: str, selector: Optional[str] = None, fmt: str = "text") -> dict:
        session = self._get(session_id)
        if selector:
            element = await session.page.query_selector(selector)
            if not element:
                return {"error": f"Element not found: {selector}"}
            if fmt == "html":
                content = await element.inner_html()
            else:
                content = await element.inner_text()
        else:
            if fmt == "html":
                content = await session.page.content()
            else:
                content = await session.page.inner_text("body")
        return {"content": content, "format": fmt, "url": session.page.url}

    def _get(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session
