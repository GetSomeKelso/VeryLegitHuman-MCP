"""Postiz REST API client for multi-platform social media scheduling.

Supports 18+ platforms. Requires POSTIZ_API_KEY env var.
Rate limit: 30 requests/hour.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import POSTIZ_API_KEY, POSTIZ_BASE_URL, POSTIZ_TIMEOUT

logger = logging.getLogger(__name__)


def _check_available() -> None:
    if not POSTIZ_API_KEY:
        raise RuntimeError("POSTIZ_API_KEY environment variable not set")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {POSTIZ_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def list_integrations() -> list[dict]:
    """List connected social media integrations in Postiz."""
    _check_available()
    async with httpx.AsyncClient(timeout=POSTIZ_TIMEOUT) as client:
        resp = await client.get(f"{POSTIZ_BASE_URL}/integrations", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def schedule_post(
    content: str,
    integration_id: str,
    scheduled_at: Optional[str] = None,
    media_urls: Optional[list[str]] = None,
) -> dict:
    """Schedule a post via Postiz.

    Args:
        content: Post text content.
        integration_id: Postiz integration ID for the target platform account.
        scheduled_at: ISO timestamp. If None, posts immediately.
        media_urls: Optional list of media URLs to attach.
    """
    _check_available()

    payload: dict = {
        "content": content,
        "integration_id": integration_id,
    }
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at
    if media_urls:
        payload["media"] = media_urls

    async with httpx.AsyncClient(timeout=POSTIZ_TIMEOUT) as client:
        resp = await client.post(f"{POSTIZ_BASE_URL}/posts", json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def list_posts(integration_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    """List scheduled and published posts."""
    _check_available()
    params: dict = {"limit": limit}
    if integration_id:
        params["integration_id"] = integration_id

    async with httpx.AsyncClient(timeout=POSTIZ_TIMEOUT) as client:
        resp = await client.get(f"{POSTIZ_BASE_URL}/posts", params=params, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", data.get("posts", []))


async def get_post(post_id: str) -> dict:
    """Get details of a specific post."""
    _check_available()
    async with httpx.AsyncClient(timeout=POSTIZ_TIMEOUT) as client:
        resp = await client.get(f"{POSTIZ_BASE_URL}/posts/{post_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def delete_post(post_id: str) -> bool:
    """Delete a scheduled post."""
    _check_available()
    async with httpx.AsyncClient(timeout=POSTIZ_TIMEOUT) as client:
        resp = await client.delete(f"{POSTIZ_BASE_URL}/posts/{post_id}", headers=_headers())
        return resp.status_code in (200, 204)
