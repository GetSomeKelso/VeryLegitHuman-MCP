"""Reddit client via PRAW for direct posting and interaction.

Requires env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
Rate limit: 100 queries/min (auto-handled by PRAW).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

logger = logging.getLogger(__name__)

_PRAW_AVAILABLE = False
try:
    import praw
    _PRAW_AVAILABLE = True
except ImportError:
    logger.info("praw not installed — Reddit direct posting unavailable")


def _check_available() -> None:
    if not _PRAW_AVAILABLE:
        raise RuntimeError("praw not installed. Run: pip install praw")
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables not set")


def _get_reddit(username: str, password: str) -> praw.Reddit:
    """Create an authenticated Reddit instance for a persona."""
    _check_available()
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=username,
        password=password,
    )


async def post_to_subreddit(
    username: str,
    password: str,
    subreddit: str,
    title: str,
    content: str,
    link_url: Optional[str] = None,
) -> dict:
    """Post to a subreddit.

    Args:
        username: Reddit username for the persona.
        password: Reddit password for the persona.
        subreddit: Target subreddit name (without r/).
        title: Post title.
        content: Post body (self-text) or ignored if link_url provided.
        link_url: Optional URL for a link post.
    """
    reddit = _get_reddit(username, password)
    sub = reddit.subreddit(subreddit)

    if link_url:
        submission = sub.submit(title=title, url=link_url)
    else:
        submission = sub.submit(title=title, selftext=content)

    return {
        "post_id": submission.id,
        "url": f"https://reddit.com{submission.permalink}",
        "subreddit": subreddit,
        "title": title,
        "platform": "reddit",
    }


async def post_comment(
    username: str,
    password: str,
    post_url: str,
    comment: str,
) -> dict:
    """Comment on a Reddit post.

    Args:
        username: Reddit username.
        password: Reddit password.
        post_url: Full URL of the post to comment on.
        comment: Comment text.
    """
    reddit = _get_reddit(username, password)
    submission = reddit.submission(url=post_url)
    reply = submission.reply(comment)

    return {
        "comment_id": reply.id,
        "post_url": post_url,
        "platform": "reddit",
    }
