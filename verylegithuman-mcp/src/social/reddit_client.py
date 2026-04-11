"""Reddit client via PRAW for direct posting and interaction.

Requires env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
All sync PRAW calls wrapped in asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
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


def _get_reddit(username: str, password: str):
    _check_available()
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=username,
        password=password,
    )


def _sync_post(username, password, subreddit, title, content, link_url):
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


def _sync_comment(username, password, post_url, comment):
    reddit = _get_reddit(username, password)
    submission = reddit.submission(url=post_url)
    reply = submission.reply(comment)
    return {
        "comment_id": reply.id,
        "post_url": post_url,
        "platform": "reddit",
    }


async def post_to_subreddit(
    username: str,
    password: str,
    subreddit: str,
    title: str,
    content: str,
    link_url: Optional[str] = None,
) -> dict:
    return await asyncio.to_thread(_sync_post, username, password, subreddit, title, content, link_url)


async def post_comment(
    username: str,
    password: str,
    post_url: str,
    comment: str,
) -> dict:
    return await asyncio.to_thread(_sync_comment, username, password, post_url, comment)
