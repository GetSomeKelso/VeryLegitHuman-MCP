"""Security hardening module — OWASP MCP Top 10 + LLM Top 10.

Provides: input validation, output sanitization, SSRF blocking,
rate limiting, and structured audit logging.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from .config import (
    ALLOWED_URL_SCHEMES,
    AUDIT_LOG_ENABLED,
    BLOCKED_IP_PREFIXES,
    BLOCKED_IP_RANGES_172,
    BLOCKED_URL_SCHEMES,
    MAX_BIO_LENGTH,
    MAX_CONTENT_LENGTH,
    MAX_STRING_LENGTH,
    MAX_TEXT_OUTPUT_BYTES,
    MAX_URL_LENGTH,
    SENSITIVE_FIELDS,
    VALID_ENGINES,
    VALID_PLATFORMS,
    VALID_PROVIDERS_EMAIL,
    VALID_PROVIDERS_PHONE,
    VALID_PROVIDERS_PROXY,
    VALID_STATUSES,
)

logger = logging.getLogger("verylegithuman.security")
audit_logger = logging.getLogger("verylegithuman.audit")


# ===========================================================================
# Input Validation (MCP05, LLM07)
# ===========================================================================

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_url(url: str, allow_internal: bool = False) -> str:
    """Validate a URL for safe schemes and block SSRF targets.

    MCP04 (Privilege Escalation) + MCP10 (SSRF)
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL is required")

    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(f"URL exceeds {MAX_URL_LENGTH} character limit")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # Block dangerous schemes
    if scheme in BLOCKED_URL_SCHEMES:
        raise ValidationError(f"Blocked URL scheme: {scheme}://")

    # Require allowed schemes
    if scheme and scheme not in ALLOWED_URL_SCHEMES:
        raise ValidationError(f"URL scheme '{scheme}' not allowed. Use http:// or https://")

    # SSRF: Block internal IPs
    if not allow_internal:
        hostname = parsed.hostname or ""
        if hostname == "localhost":
            raise ValidationError("SSRF blocked: localhost access not allowed")

        for prefix in BLOCKED_IP_PREFIXES:
            if hostname.startswith(prefix):
                raise ValidationError(f"SSRF blocked: internal IP range ({hostname})")

        # Check 172.16-31.x.x
        if hostname.startswith("172."):
            parts = hostname.split(".")
            if len(parts) >= 2:
                try:
                    second_octet = int(parts[1])
                    if second_octet in BLOCKED_IP_RANGES_172:
                        raise ValidationError(f"SSRF blocked: private IP range ({hostname})")
                except ValueError:
                    pass

    return url


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate UUID format."""
    if not value or not isinstance(value, str):
        raise ValidationError(f"{field_name} is required")
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        raise ValidationError(f"Invalid UUID format for {field_name}: {value}")


def validate_enum(value: str, valid_values: set, field_name: str) -> str:
    """Validate against a set of allowed values."""
    if not value or not isinstance(value, str):
        raise ValidationError(f"{field_name} is required")
    value = value.lower().strip()
    if value not in valid_values:
        raise ValidationError(f"Invalid {field_name}: '{value}'. Allowed: {', '.join(sorted(valid_values))}")
    return value


def truncate_string(value: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """Truncate a string to max length."""
    if not isinstance(value, str):
        return str(value)
    if len(value) > max_length:
        return value[:max_length] + f"... [truncated at {max_length} chars]"
    return value


def validate_selector(selector: str) -> str:
    """Validate CSS selector — block obvious injection patterns.

    MCP05 (Input Validation)
    """
    if not selector or not isinstance(selector, str):
        raise ValidationError("CSS selector is required")

    selector = selector.strip()
    if len(selector) > 500:
        raise ValidationError("CSS selector too long (max 500 chars)")

    # Block script injection via selectors
    dangerous_patterns = [
        r'<script', r'javascript:', r'on\w+\s*=', r'eval\s*\(',
        r'expression\s*\(', r'url\s*\(', r'import\s',
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, selector, re.IGNORECASE):
            raise ValidationError(f"Potentially dangerous CSS selector blocked")

    return selector


def sanitize_arguments(tool_name: str, arguments: dict) -> dict:
    """Centralized input sanitization for all tool calls.

    MCP05 (Input Validation) — applies length limits, strips control chars,
    validates enums and UUIDs.
    """
    sanitized = {}

    for key, value in arguments.items():
        if value is None:
            sanitized[key] = value
            continue

        # String sanitization
        if isinstance(value, str):
            # Strip null bytes and control characters (except newlines/tabs)
            value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)

            # Field-specific length limits
            if key in ("bio",):
                value = truncate_string(value, MAX_BIO_LENGTH)
            elif key in ("content", "body_text", "body_html"):
                value = truncate_string(value, MAX_CONTENT_LENGTH)
            elif key in ("url",):
                if len(value) > MAX_URL_LENGTH:
                    raise ValidationError(f"URL exceeds {MAX_URL_LENGTH} chars")
            elif key in ("selector",):
                value = validate_selector(value)
            else:
                value = truncate_string(value, MAX_STRING_LENGTH)

        # Numeric clamping
        elif isinstance(value, int):
            if key in ("limit", "offset", "count", "per_page"):
                value = max(0, min(value, 1000))
            elif key in ("delay",):
                value = max(0, min(value, 5000))
            elif key in ("days_back", "days_ahead"):
                value = max(1, min(value, 365))
            elif key in ("posts_per_week",):
                value = max(1, min(value, 21))
            elif key in ("likes", "shares", "comments"):
                value = max(0, min(value, 1_000_000))

        sanitized[key] = value

    return sanitized


# ===========================================================================
# Output Sanitization (MCP03, MCP06, LLM02, LLM06)
# ===========================================================================

def redact_sensitive_fields(data: Any) -> Any:
    """Recursively redact sensitive fields from tool output.

    MCP06 (Sensitive Data Exposure) — masks passwords, tokens, API keys.
    """
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if key in SENSITIVE_FIELDS:
                if isinstance(value, str) and len(value) > 0:
                    redacted[key] = value[:2] + "****" + value[-2:] if len(value) > 4 else "****"
                elif isinstance(value, dict):
                    redacted[key] = {k: "****" for k in value}
                else:
                    redacted[key] = "****"
            else:
                redacted[key] = redact_sensitive_fields(value)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_fields(item) for item in data]
    return data


def sanitize_html_output(html: Optional[str]) -> Optional[str]:
    """Strip dangerous HTML tags from email/page content returned to LLM.

    LLM02 (Insecure Output Handling) — prevents script injection via tool output.
    """
    if not html:
        return html

    # Remove script tags and their content
    html = re.sub(r'<script[^>]*>.*?</script>', '[SCRIPT REMOVED]', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove event handlers
    html = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
    # Remove iframe tags
    html = re.sub(r'<iframe[^>]*>.*?</iframe>', '[IFRAME REMOVED]', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove object/embed tags
    html = re.sub(r'<(object|embed)[^>]*>.*?</\1>', '[EMBED REMOVED]', html, flags=re.DOTALL | re.IGNORECASE)

    return html


def truncate_output(data: Any) -> Any:
    """Truncate large text outputs to prevent context window flooding.

    LLM04 (Denial of Service)
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in ("content", "body_text", "body_html", "base64") and isinstance(value, str):
                if len(value) > MAX_TEXT_OUTPUT_BYTES:
                    result[key] = value[:MAX_TEXT_OUTPUT_BYTES] + f"\n... [truncated at {MAX_TEXT_OUTPUT_BYTES} bytes]"
                else:
                    result[key] = value
            elif key == "body_html" and isinstance(value, str):
                result[key] = sanitize_html_output(value)
            else:
                result[key] = truncate_output(value)
        return result
    elif isinstance(data, list):
        return [truncate_output(item) for item in data]
    return data


def sanitize_tool_output(tool_name: str, data: Any) -> Any:
    """Full output sanitization pipeline.

    Applies: sensitive field redaction, HTML sanitization, output truncation.
    """
    data = redact_sensitive_fields(data)
    data = truncate_output(data)
    return data


# ===========================================================================
# Rate Limiting (MCP02, LLM04)
# ===========================================================================

class RateLimiter:
    """Simple in-memory rate limiter using sliding window counters."""

    def __init__(self) -> None:
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._limits: dict[str, tuple[int, float]] = {
            # key: (max_calls, window_seconds)
            "mailtm": (8, 1.0),         # Mail.tm: 8 req/s
            "guerrilla": (4, 1.0),      # Guerrilla: 4 req/s
            "postiz": (30, 3600.0),     # Postiz: 30 req/hour
            "browser_launch": (1, 5.0), # 1 browser launch per 5 seconds
            "default": (60, 60.0),      # Default: 60 req/min
        }

    def check(self, key: str) -> bool:
        """Check if a call is allowed. Returns True if within limits."""
        max_calls, window = self._limits.get(key, self._limits["default"])
        now = time.time()
        cutoff = now - window

        # Clean old entries
        self._calls[key] = [t for t in self._calls[key] if t > cutoff]

        if len(self._calls[key]) >= max_calls:
            return False

        self._calls[key].append(now)
        return True

    def wait_time(self, key: str) -> float:
        """Return seconds until next call is allowed. 0 if allowed now."""
        max_calls, window = self._limits.get(key, self._limits["default"])
        now = time.time()
        cutoff = now - window

        calls = [t for t in self._calls[key] if t > cutoff]
        if len(calls) < max_calls:
            return 0.0

        return calls[0] + window - now


# Global rate limiter instance
rate_limiter = RateLimiter()


# ===========================================================================
# Audit Logging (MCP08)
# ===========================================================================

def audit_log_call(tool_name: str, arguments: dict, call_id: Optional[str] = None) -> str:
    """Log a tool call for audit purposes.

    MCP08 (Insufficient Logging) — logs tool name and arg keys (not values)
    to avoid leaking sensitive data.
    Returns the call_id for correlation.
    """
    if not AUDIT_LOG_ENABLED:
        return call_id or ""

    call_id = call_id or str(uuid.uuid4())[:8]
    entry = {
        "event": "tool_call_start",
        "call_id": call_id,
        "tool": tool_name,
        "arg_keys": sorted(arguments.keys()),
        "timestamp": datetime.utcnow().isoformat(),
    }
    audit_logger.info(json.dumps(entry))
    return call_id


def audit_log_result(tool_name: str, call_id: str, success: bool, elapsed_ms: float) -> None:
    """Log tool call completion."""
    if not AUDIT_LOG_ENABLED:
        return

    entry = {
        "event": "tool_call_end",
        "call_id": call_id,
        "tool": tool_name,
        "success": success,
        "elapsed_ms": round(elapsed_ms, 1),
        "timestamp": datetime.utcnow().isoformat(),
    }
    level = logging.INFO if success else logging.WARNING
    audit_logger.log(level, json.dumps(entry))


# Sensitive tools that get elevated logging
SENSITIVE_TOOLS = {
    "create_email", "delete_email_account", "provision_phone", "release_phone",
    "launch_browser", "post_now", "configure_proxy", "start_tor",
    "mullvad_connect", "register_social_account", "schedule_post",
}
