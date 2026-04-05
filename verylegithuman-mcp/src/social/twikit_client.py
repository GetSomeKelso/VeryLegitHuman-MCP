"""X/Twitter client via Twikit — no API key needed.

Uses X's internal API via authenticated sessions.
Requires persona's X credentials (username, email, password).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import TWIKIT_ENABLED

logger = logging.getLogger(__name__)

_TWIKIT_AVAILABLE = False
try:
    import twikit
    _TWIKIT_AVAILABLE = True
except ImportError:
    logger.info("twikit not installed — X/Twitter direct posting unavailable")


def _check_available() -> None:
    if not _TWIKIT_AVAILABLE:
        raise RuntimeError("twikit not installed. Run: pip install twikit")
    if not TWIKIT_ENABLED:
        raise RuntimeError("Twikit is disabled. Set TWIKIT_ENABLED=true to enable X/Twitter direct posting.")


async def post_tweet(
    username: str,
    email: str,
    password: str,
    content: str,
    media_paths: Optional[list[str]] = None,
) -> dict:
    """Post a tweet using persona's X credentials.

    Args:
        username: X username.
        email: X email.
        password: X password.
        content: Tweet text (max 280 chars).
        media_paths: Optional list of local file paths to upload.
    """
    _check_available()

    client = twikit.Client("en-US")
    await client.login(auth_info_1=username, auth_info_2=email, password=password)

    if media_paths:
        media_ids = []
        for path in media_paths:
            media = await client.upload_media(path)
            media_ids.append(media.media_id)
        tweet = await client.create_tweet(content, media_ids=media_ids)
    else:
        tweet = await client.create_tweet(content)

    return {
        "tweet_id": str(tweet.id) if hasattr(tweet, "id") else str(tweet),
        "content": content,
        "platform": "x",
    }


async def get_timeline(
    username: str,
    email: str,
    password: str,
    count: int = 20,
) -> list[dict]:
    """Get persona's timeline (home feed).

    Args:
        username: X username.
        email: X email.
        password: X password.
        count: Number of tweets to fetch.
    """
    _check_available()

    client = twikit.Client("en-US")
    await client.login(auth_info_1=username, auth_info_2=email, password=password)

    tweets = await client.get_timeline(count=count)
    return [
        {
            "id": str(t.id) if hasattr(t, "id") else "",
            "text": t.text if hasattr(t, "text") else str(t),
            "user": t.user.screen_name if hasattr(t, "user") and hasattr(t.user, "screen_name") else "",
            "created_at": str(t.created_at) if hasattr(t, "created_at") else "",
        }
        for t in tweets
    ]
