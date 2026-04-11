"""Platform constraints and content scaffolding for social media posting.

Provides character limits, formatting rules, and best practices per platform.
Claude uses these constraints to generate properly formatted post content.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

PLATFORM_CONSTRAINTS: dict[str, dict] = {
    "x": {
        "char_limit": 280,
        "max_hashtags": 3,
        "max_media": 4,
        "supports_threads": True,
        "supports_markdown": False,
        "requires_media": False,
        "best_practices": (
            "Short, punchy statements. Use 1-2 hashtags max for organic feel. "
            "Ask questions to drive engagement. Retweet/quote relevant content. "
            "Avoid link-only tweets. Thread longer thoughts."
        ),
    },
    "reddit": {
        "title_char_limit": 300,
        "body_char_limit": 40000,
        "max_hashtags": 0,
        "supports_markdown": True,
        "requires_subreddit": True,
        "requires_media": False,
        "best_practices": (
            "Follow each subreddit's rules strictly. Be authentic and add value. "
            "No self-promotion in first posts. Comment on others' posts before posting your own. "
            "Use markdown formatting. Flair posts when required."
        ),
    },
    "linkedin": {
        "char_limit": 3000,
        "max_hashtags": 5,
        "supports_articles": True,
        "supports_markdown": False,
        "requires_media": False,
        "best_practices": (
            "Professional tone. Share industry insights, not opinions. "
            "Use line breaks for readability. Open with a hook. "
            "Tag relevant people/companies. Post during business hours (Tue-Thu)."
        ),
    },
    "instagram": {
        "caption_char_limit": 2200,
        "max_hashtags": 30,
        "supports_stories": True,
        "supports_reels": True,
        "requires_media": True,
        "best_practices": (
            "Visual-first platform. Captions should complement the image. "
            "Put hashtags in first comment, not caption. Use Stories for engagement. "
            "Post consistently. Engage with similar accounts."
        ),
    },
    "mastodon": {
        "char_limit": 500,
        "max_hashtags": 5,
        "supports_content_warnings": True,
        "supports_markdown": False,
        "requires_media": False,
        "best_practices": (
            "Use content warnings (CW) for sensitive topics. Alt-text for images. "
            "Be respectful of instance rules. Boost others' content. "
            "Use hashtags for discovery (Mastodon doesn't have an algorithm)."
        ),
    },
    "bluesky": {
        "char_limit": 300,
        "max_hashtags": 3,
        "max_media": 4,
        "supports_threads": True,
        "requires_media": False,
        "best_practices": (
            "Similar to early Twitter. Conversational tone. "
            "Use starter packs and feeds for discovery. "
            "Engage with replies. Cross-post quality content from X."
        ),
    },
    "tiktok": {
        "caption_char_limit": 2200,
        "max_hashtags": 10,
        "requires_media": True,
        "media_type": "video",
        "best_practices": (
            "Video-first. Hook viewers in first 3 seconds. "
            "Use trending sounds. Keep videos 15-60 seconds. "
            "Post 1-3 times daily for growth. Engage with comments."
        ),
    },
    "threads": {
        "char_limit": 500,
        "max_media": 10,
        "supports_threads": True,
        "requires_media": False,
        "best_practices": (
            "Conversational, casual tone. Think Twitter but warmer. "
            "Cross-post from Instagram for follower transfer. "
            "Use threads for longer thoughts. Engage authentically."
        ),
    },
    "medium": {
        "char_limit": None,  # Long-form
        "supports_markdown": True,
        "requires_media": False,
        "best_practices": (
            "Long-form articles (800-2000 words). Use headers and images. "
            "Publish in relevant publications for reach. "
            "Catchy title + subtitle. Include a call-to-action."
        ),
    },
    "pinterest": {
        "title_char_limit": 100,
        "description_char_limit": 500,
        "requires_media": True,
        "best_practices": (
            "Vertical images (2:3 ratio). Rich, keyword-heavy descriptions. "
            "Create boards around themes. Pin consistently. "
            "Link back to content (blog, product, etc.)."
        ),
    },
}


def get_constraints(platform: str) -> dict:
    """Get posting constraints for a platform."""
    platform = platform.lower()
    if platform not in PLATFORM_CONSTRAINTS:
        return {
            "platform": platform,
            "error": f"Unknown platform. Available: {', '.join(sorted(PLATFORM_CONSTRAINTS.keys()))}",
        }
    constraints = PLATFORM_CONSTRAINTS[platform].copy()
    constraints["platform"] = platform
    return constraints


def generate_posting_schedule(
    posts_per_week: int = 4,
    days_ahead: int = 7,
    timezone_offset_hours: int = 0,
) -> list[dict]:
    """Generate a realistic posting schedule with human-like jitter.

    Returns list of time slots with randomized timing to mimic real behavior.
    """
    slots: list[dict] = []
    now = datetime.utcnow() + timedelta(hours=timezone_offset_hours)

    # Distribute posts across the week
    posts_remaining = posts_per_week
    for day_offset in range(days_ahead):
        if posts_remaining <= 0:
            break

        day = now + timedelta(days=day_offset + 1)

        # Skip some days randomly (humans don't post every day)
        if random.random() < 0.3 and posts_remaining > 1:
            continue

        # 1-2 posts per active day
        posts_today = min(random.choice([1, 1, 1, 2]), posts_remaining)

        for _ in range(posts_today):
            # Realistic posting hours: 8am-10pm with peak at lunch and evening
            hour_weights = {
                8: 1, 9: 2, 10: 3, 11: 3, 12: 5, 13: 4, 14: 3,
                15: 2, 16: 3, 17: 4, 18: 5, 19: 5, 20: 4, 21: 3, 22: 1,
            }
            hours = list(hour_weights.keys())
            weights = list(hour_weights.values())
            hour = random.choices(hours, weights=weights, k=1)[0]
            minute = random.randint(0, 59)

            slot_time = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # Add jitter: +/- 0-15 minutes
            jitter = random.randint(-15, 15)
            slot_time += timedelta(minutes=jitter)

            slots.append({
                "scheduled_at": slot_time.isoformat(),
                "day_of_week": slot_time.strftime("%A"),
                "time_local": slot_time.strftime("%I:%M %p"),
            })
            posts_remaining -= 1

    slots.sort(key=lambda s: s["scheduled_at"])
    return slots
