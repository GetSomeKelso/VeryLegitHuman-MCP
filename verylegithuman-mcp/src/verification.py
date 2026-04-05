"""Verification code and link extraction from email/SMS bodies."""

from __future__ import annotations

import re
from typing import Optional

from .config import OTP_PATTERNS, VERIFICATION_LINK_PATTERNS


def extract_verification_data(
    text: Optional[str] = None,
    html: Optional[str] = None,
) -> dict:
    """Extract OTP codes and verification links from message content.

    Searches both plain text and HTML bodies. Returns the most likely
    verification code and all found verification links.

    Returns:
        {
            "codes": ["123456", ...],
            "primary_code": "123456" or None,
            "links": ["https://...verify...", ...],
            "primary_link": "https://..." or None,
        }
    """
    codes: list[str] = []
    links: list[str] = []

    # Search both text sources
    sources = []
    if text:
        sources.append(text)
    if html:
        sources.append(html)

    combined = "\n".join(sources)

    # Extract OTP codes
    for pattern in OTP_PATTERNS:
        matches = re.findall(pattern, combined)
        for m in matches:
            # Filter out common false positives
            if m in ("0000", "1234", "12345", "123456", "1234567", "12345678"):
                continue
            # Skip years (1900-2099)
            if len(m) == 4 and m.startswith(("19", "20")):
                continue
            codes.append(m)

    # Extract verification links
    for pattern in VERIFICATION_LINK_PATTERNS:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        for m in matches:
            # Clean up trailing punctuation
            m = m.rstrip(".,;:!?)\"'>")
            if m not in links:
                links.append(m)

    # Deduplicate codes while preserving order
    seen: set[str] = set()
    unique_codes: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique_codes.append(c)

    # Primary code: prefer 6-digit numeric (most common OTP format)
    primary_code = None
    for c in unique_codes:
        if len(c) == 6 and c.isdigit():
            primary_code = c
            break
    if not primary_code and unique_codes:
        primary_code = unique_codes[0]

    return {
        "codes": unique_codes,
        "primary_code": primary_code,
        "links": links,
        "primary_link": links[0] if links else None,
    }
