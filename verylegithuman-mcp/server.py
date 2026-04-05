"""VeryLegitHuman MCP Server — Persona lifecycle management for authorized OSINT/red team ops.

Phase 1: Identity generation (personas, faces, usernames)
Phase 2: Email/phone provisioning (Mail.tm, Guerrilla, MailSlurp, Twilio, 5sim)
Phase 3: Stealth browser automation (Patchright Chromium, Camoufox Firefox)
Phase 4: OpSec infrastructure (proxies, Tor, Mullvad VPN, IP geolocation)
Phase 5: Social history building (Postiz, Reddit/PRAW, X/Twikit, scheduling)
Phase 6: OWASP MCP Top 10 + LLM Top 10 hardening (input validation, SSRF blocking,
         output sanitization, audit logging, rate limiting)
Built on FastMCP 3.x with aiosqlite persistence. 54 tools total.
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastmcp import Context, FastMCP

from src.config import DATA_DIR, DB_DIR, FACES_DIR
from src.database import DatabaseManager
from src.identity.faces import fetch_face_tpdne
from src.identity.generator import generate_identity, generate_usernames_for_identity
from src.identity.usernames import check_username_availability
from src.email import mailtm, guerrilla, mailslurp
from src.phone import twilio_client, fivesim
from src.verification import extract_verification_data
from src.browser.session_manager import SessionManager
from src.opsec import proxy_manager, tor_manager, mullvad, geolocation
from src.social import postiz_client, reddit_client, twikit_client
from src.social.content import get_constraints, generate_posting_schedule
from src.security import (
    ValidationError,
    audit_log_call,
    audit_log_result,
    rate_limiter,
    redact_sensitive_fields,
    sanitize_arguments,
    sanitize_tool_output,
    validate_url,
    validate_uuid,
    validate_enum,
    SENSITIVE_TOOLS,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("verylegithuman")


# ---------------------------------------------------------------------------
# Lifespan — DB init/cleanup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastMCP):
    """Initialize database and session manager on startup, cleanup on shutdown."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)

    db = DatabaseManager()
    await db.init_db()
    sessions = SessionManager()
    logger.info("VeryLegitHuman MCP server started")

    try:
        yield {"db": db, "sessions": sessions}
    finally:
        closed = await sessions.close_all()
        if closed:
            logger.info("Closed %d browser sessions", closed)
        await db.close()
        logger.info("VeryLegitHuman MCP server stopped")


# ---------------------------------------------------------------------------
# FastMCP App
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="VeryLegitHuman MCP",
    instructions=(
        "VeryLegitHuman MCP server for authorized OSINT and red team operations. "
        "54 tools across identity generation, email/phone provisioning, stealth browser automation, "
        "OpSec infrastructure (proxies, Tor, VPN, geolocation), and social history building."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helper: get DB from context
# ---------------------------------------------------------------------------

def _get_db(ctx: Context) -> DatabaseManager:
    """Extract DatabaseManager from FastMCP context."""
    return ctx.request_context.lifespan_context["db"]


def _get_sessions(ctx: Context) -> SessionManager:
    """Extract SessionManager from FastMCP context."""
    return ctx.request_context.lifespan_context["sessions"]


# ===========================================================================
# TOOL 1: create_persona
# ===========================================================================

@mcp.tool
async def create_persona(
    ctx: Context,
    locale: str = "en_US",
    gender: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    nationality: Optional[str] = None,
    occupation: Optional[str] = None,
    codename: Optional[str] = None,
) -> dict:
    """Generate and persist a new persona identity.

    Creates a complete persona with name, DOB, address, email placeholder,
    phone placeholder, occupation, and company.

    Args:
        locale: Faker locale (e.g., "en_US", "de_DE", "ja_JP"). Default "en_US".
        gender: "male" or "female". Random if omitted.
        age_min: Minimum age (18-90). Default 21.
        age_max: Maximum age (18-90). Default 55.
        nationality: Override nationality. Auto-detected from locale if omitted.
        occupation: Override job title. Random if omitted.
        codename: Custom codename. Auto-generated (e.g., "shadow-wolf-42") if omitted.
    """
    db = _get_db(ctx)
    identity = generate_identity(
        locale=locale,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        nationality=nationality,
        occupation=occupation,
        codename=codename,
    )
    persona = await db.create_persona(identity)
    logger.info("Created persona: %s (%s)", persona["codename"], persona["full_name"])
    return persona


# ===========================================================================
# TOOL 2: get_persona
# ===========================================================================

@mcp.tool
async def get_persona(
    ctx: Context,
    persona_id: Optional[str] = None,
    codename: Optional[str] = None,
) -> dict:
    """Fetch a persona by ID or codename.

    Returns the full persona record including notes, usernames, and face info.

    Args:
        persona_id: UUID of the persona.
        codename: Codename alias (e.g., "shadow-wolf-42").
    """
    db = _get_db(ctx)
    persona = await db.get_persona(persona_id=persona_id, codename=codename)
    if not persona:
        return {"error": "Persona not found", "persona_id": persona_id, "codename": codename}
    return persona


# ===========================================================================
# TOOL 3: update_persona
# ===========================================================================

@mcp.tool
async def update_persona(
    ctx: Context,
    persona_id: str,
    codename: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    gender: Optional[str] = None,
    email_personal: Optional[str] = None,
    phone: Optional[str] = None,
    occupation: Optional[str] = None,
    company: Optional[str] = None,
    bio: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Update fields on an existing persona.

    Only provided fields are updated; others remain unchanged.

    Args:
        persona_id: UUID of the persona to update.
        codename: New codename.
        first_name: New first name.
        last_name: New last name.
        gender: New gender.
        email_personal: New email.
        phone: New phone.
        occupation: New occupation.
        company: New company.
        bio: Backstory or biography text.
        status: "active", "burned", or "retired".
    """
    db = _get_db(ctx)
    field_values = {
        "codename": codename, "first_name": first_name, "last_name": last_name,
        "gender": gender, "email_personal": email_personal, "phone": phone,
        "occupation": occupation, "company": company, "bio": bio, "status": status,
    }
    updates = {k: v for k, v in field_values.items() if v is not None}

    # Recompute full_name if name fields changed
    if "first_name" in updates or "last_name" in updates:
        existing = await db.get_persona(persona_id=persona_id)
        if existing:
            fn = updates.get("first_name", existing["first_name"])
            ln = updates.get("last_name", existing["last_name"])
            updates["full_name"] = f"{fn} {ln}"

    if not updates:
        return {"error": "No fields provided to update"}

    persona = await db.update_persona(persona_id, updates)
    if not persona:
        return {"error": "Persona not found", "persona_id": persona_id}
    logger.info("Updated persona: %s", persona["codename"])
    return persona


# ===========================================================================
# TOOL 4: list_personas
# ===========================================================================

@mcp.tool
async def list_personas(
    ctx: Context,
    status: Optional[str] = None,
    locale: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List all personas with optional filters.

    Args:
        status: Filter by status ("active", "burned", "retired").
        locale: Filter by locale (e.g., "en_US").
        limit: Max results (default 50).
        offset: Pagination offset.
    """
    db = _get_db(ctx)
    personas = await db.list_personas(status=status, locale=locale, limit=limit, offset=offset)
    return {"count": len(personas), "personas": personas}


# ===========================================================================
# TOOL 5: preview_identity (no persist, no DB needed)
# ===========================================================================

@mcp.tool
async def preview_identity(
    locale: str = "en_US",
    gender: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    nationality: Optional[str] = None,
    occupation: Optional[str] = None,
) -> dict:
    """Generate identity data WITHOUT persisting. For previewing before committing.

    Returns a complete identity dict that can be reviewed and then saved
    via create_persona if desired.

    Args:
        locale: Faker locale. Default "en_US".
        gender: "male" or "female". Random if omitted.
        age_min: Minimum age (18-90).
        age_max: Maximum age (18-90).
        nationality: Override nationality.
        occupation: Override job title.
    """
    identity = generate_identity(
        locale=locale,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        nationality=nationality,
        occupation=occupation,
    )
    identity.pop("usernames_json", None)
    identity.pop("username_availability_json", None)
    identity.pop("metadata_json", None)
    return {"preview": True, "identity": identity}


# ===========================================================================
# TOOL 6: generate_backstory
# ===========================================================================

@mcp.tool
async def generate_backstory(
    ctx: Context,
    persona_id: str,
    detail_level: str = "medium",
) -> dict:
    """Generate backstory building blocks for a persona.

    Returns structured data the AI agent can use to write a natural backstory.
    The calling LLM assembles the final narrative.

    Args:
        persona_id: UUID of the persona.
        detail_level: "brief", "medium", or "detailed".
    """
    db = _get_db(ctx)
    p = await db.get_persona(persona_id=persona_id)
    if not p:
        return {"error": "Persona not found"}

    addr = p.get("address", {})
    city = addr.get("city", "")
    state = addr.get("state", "")
    country = addr.get("country", "")

    ingredients = {
        "name": p["full_name"],
        "age": p["age"],
        "gender": p["gender"],
        "nationality": p.get("nationality"),
        "city": city,
        "state": state,
        "country": country,
        "occupation": p["occupation"],
        "company": p["company"],
        "detail_level": detail_level,
    }

    if detail_level == "brief":
        ingredients["prompt_hint"] = (
            f"Write a 2-3 sentence bio for {p['full_name']}, a {p['age']}-year-old "
            f"{p['gender']} {p['occupation']} from {city}, {state}."
        )
    elif detail_level == "detailed":
        ingredients["prompt_hint"] = (
            f"Write a detailed 2-paragraph backstory for {p['full_name']}, a {p['age']}-year-old "
            f"{p['gender']} {p['occupation']} at {p['company']} from {city}, "
            f"{state}, {country}. Include education background, "
            f"career journey, hobbies, and personality traits."
        )
    else:
        ingredients["prompt_hint"] = (
            f"Write a 4-5 sentence backstory for {p['full_name']}, a {p['age']}-year-old "
            f"{p['gender']} {p['occupation']} at {p['company']} from {city}, "
            f"{state}. Include a brief career note and one personal detail."
        )

    return {
        "persona_id": persona_id,
        "codename": p["codename"],
        "ingredients": ingredients,
        "note": "Use the prompt_hint to generate the backstory, then save it via update_persona(bio=...)",
    }


# ===========================================================================
# TOOL 7: bulk_generate (no DB needed)
# ===========================================================================

@mcp.tool
async def bulk_generate(
    locale: str = "en_US",
    gender: Optional[str] = None,
    count: int = 5,
) -> dict:
    """Generate multiple identities at once WITHOUT persisting.

    Useful for reviewing a batch and picking the best candidates.

    Args:
        locale: Faker locale. Default "en_US".
        gender: "male" or "female". Random per identity if omitted.
        count: Number to generate (1-20). Default 5.
    """
    count = max(1, min(20, count))
    identities = []
    for _ in range(count):
        identity = generate_identity(locale=locale, gender=gender)
        identity.pop("usernames_json", None)
        identity.pop("username_availability_json", None)
        identity.pop("metadata_json", None)
        identities.append(identity)

    return {"count": len(identities), "identities": identities}


# ===========================================================================
# TOOL 8: generate_face
# ===========================================================================

@mcp.tool
async def generate_face(
    ctx: Context,
    persona_id: Optional[str] = None,
) -> dict:
    """Fetch an AI-generated face from ThisPersonDoesNotExist.

    Saves the JPEG locally. If persona_id is provided, attaches the face
    to that persona automatically.

    Args:
        persona_id: Optional UUID to attach the face to an existing persona.
    """
    result = await fetch_face_tpdne(persona_id=persona_id)

    if persona_id:
        db = _get_db(ctx)
        updated = await db.update_face(persona_id, result["file_path"], "thispersondoesnotexist")
        if updated:
            result["attached_to"] = persona_id
            logger.info("Face attached to persona %s", persona_id)

    return result


# ===========================================================================
# TOOL 9: set_persona_face
# ===========================================================================

@mcp.tool
async def set_persona_face(
    ctx: Context,
    persona_id: str,
    face_path: Optional[str] = None,
    face_url: Optional[str] = None,
    source: str = "manual",
) -> dict:
    """Attach a face image to a persona by path or URL.

    Args:
        persona_id: UUID of the persona.
        face_path: Local file path to face image.
        face_url: URL to face image.
        source: Source identifier (e.g., "manual", "generated_photos", "tpdne").
    """
    db = _get_db(ctx)
    face_ref = face_path or face_url
    if not face_ref:
        return {"error": "Provide either face_path or face_url"}

    updated = await db.update_face(persona_id, face_ref, source)
    if not updated:
        return {"error": "Persona not found", "persona_id": persona_id}

    return {"persona_id": persona_id, "face_url": face_ref, "face_source": source}


# ===========================================================================
# TOOL 10: generate_usernames
# ===========================================================================

@mcp.tool
async def generate_usernames(
    ctx: Context,
    persona_id: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    style: str = "professional",
    count: int = 5,
) -> dict:
    """Generate username candidates for a persona.

    Provide either persona_id (to look up name) or first_name+last_name directly.

    Args:
        persona_id: UUID of existing persona.
        first_name: First name (if not using persona_id).
        last_name: Last name (if not using persona_id).
        style: "professional", "casual", or "random".
        count: Number of candidates (1-10). Default 5.
    """
    if persona_id:
        db = _get_db(ctx)
        persona = await db.get_persona(persona_id=persona_id)
        if not persona:
            return {"error": "Persona not found"}
        first_name = persona["first_name"]
        last_name = persona["last_name"]

    if not first_name or not last_name:
        return {"error": "Provide persona_id or both first_name and last_name"}

    count = max(1, min(10, count))
    candidates = generate_usernames_for_identity(first_name, last_name, style, count)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "style": style,
        "usernames": candidates,
    }


# ===========================================================================
# TOOL 11: check_username (no DB needed)
# ===========================================================================

@mcp.tool
async def check_username(
    username: str,
    platforms: Optional[list[str]] = None,
) -> dict:
    """Check username availability across platforms via Sherlock.

    Args:
        username: The username to check.
        platforms: Optional list of platforms to check. Default checks top 20 sites.
    """
    return await check_username_availability(username, platforms)


# ===========================================================================
# TOOL 12: assign_username
# ===========================================================================

@mcp.tool
async def assign_username(
    ctx: Context,
    persona_id: str,
    platform: str,
    username: str,
) -> dict:
    """Save a chosen username to a persona for a specific platform.

    Args:
        persona_id: UUID of the persona.
        platform: Platform name (e.g., "twitter", "github", "reddit").
        username: The username to assign.
    """
    db = _get_db(ctx)
    updated = await db.assign_username(persona_id, platform.lower(), username)
    if not updated:
        return {"error": "Persona not found", "persona_id": persona_id}

    return {
        "persona_id": persona_id,
        "platform": platform,
        "username": username,
        "all_usernames": updated["usernames"],
    }


# ===========================================================================
# TOOL 13: create_email
# ===========================================================================

@mcp.tool
async def create_email(
    ctx: Context,
    provider: str = "mailtm",
    persona_id: Optional[str] = None,
    preferred_username: Optional[str] = None,
) -> dict:
    """Create a new temporary email account.

    Args:
        provider: "mailtm", "guerrilla", or "mailslurp".
        persona_id: Optional UUID to link this email to a persona.
        preferred_username: Optional username prefix for the email address.
    """
    db = _get_db(ctx)

    try:
        if provider == "mailtm":
            result = await mailtm.create_account(preferred_username=preferred_username)
            account_data = {
                "persona_id": persona_id,
                "provider": "mailtm",
                "address": result["address"],
                "password": result["password"],
                "token": result["token"],
                "domain": result["domain"],
            }
        elif provider == "guerrilla":
            result = await guerrilla.get_email_address(preferred_username=preferred_username)
            account_data = {
                "persona_id": persona_id,
                "provider": "guerrilla",
                "address": result["address"],
                "token": result["sid_token"],
                "domain": result["domain"],
            }
        elif provider == "mailslurp":
            result = await mailslurp.create_inbox(name=preferred_username)
            account_data = {
                "persona_id": persona_id,
                "provider": "mailslurp",
                "address": result["address"],
                "token": result["inbox_id"],
                "domain": result["domain"],
            }
        else:
            return {"error": f"Unknown provider: {provider}. Use 'mailtm', 'guerrilla', or 'mailslurp'."}

        saved = await db.create_email_account(account_data)
        logger.info("Created email: %s (%s)", saved["address"], provider)
        return redact_sensitive_fields(saved)

    except Exception as e:
        return {"error": str(e), "provider": provider}


# ===========================================================================
# TOOL 14: list_email_accounts
# ===========================================================================

@mcp.tool
async def list_email_accounts(
    ctx: Context,
    persona_id: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List all provisioned email accounts.

    Args:
        persona_id: Filter by persona UUID.
        provider: Filter by provider ("mailtm", "guerrilla", "mailslurp").
        status: Filter by status ("active", "expired", "burned").
    """
    db = _get_db(ctx)
    accounts = await db.list_email_accounts(persona_id=persona_id, provider=provider, status=status)
    return {"count": len(accounts), "accounts": [redact_sensitive_fields(a) for a in accounts]}


# ===========================================================================
# TOOL 15: check_inbox
# ===========================================================================

@mcp.tool
async def check_inbox(
    ctx: Context,
    email_id: Optional[str] = None,
    address: Optional[str] = None,
) -> dict:
    """Fetch new messages for an email account.

    Provide either email_id (from create_email) or the email address.

    Args:
        email_id: UUID of the email account.
        address: The email address to check.
    """
    db = _get_db(ctx)
    account = await db.get_email_account(email_id=email_id, address=address)
    if not account:
        return {"error": "Email account not found"}

    try:
        provider = account["provider"]
        token = account.get("token", "")

        if provider == "mailtm":
            messages = await mailtm.get_messages(token)
        elif provider == "guerrilla":
            messages = await guerrilla.check_email(token)
        elif provider == "mailslurp":
            messages = await mailslurp.get_messages(token)
        else:
            return {"error": f"Unknown provider: {provider}"}

        # Save messages to DB
        for m in messages:
            m["email_account_id"] = account["id"]
            await db.save_email_message(m)

        # Update last_checked_at
        from datetime import datetime
        await db.update_email_account(account["id"], {"last_checked_at": datetime.utcnow().isoformat()})

        return {"account": account["address"], "provider": provider, "message_count": len(messages), "messages": messages}

    except Exception as e:
        return {"error": str(e), "account": account["address"]}


# ===========================================================================
# TOOL 16: read_email
# ===========================================================================

@mcp.tool
async def read_email(
    ctx: Context,
    message_id: str,
) -> dict:
    """Read a specific email message with full body content.

    Also auto-extracts any verification codes or links found.

    Args:
        message_id: ID of the message (from check_inbox results).
    """
    db = _get_db(ctx)

    # Check if we have it cached in DB with full body
    cached = await db.get_email_message(message_id)
    if cached and cached.get("body_text"):
        verification = extract_verification_data(cached.get("body_text"), cached.get("body_html"))
        return sanitize_tool_output("read_email", {**cached, "verification": verification})

    # Need to fetch from provider — find which account this belongs to
    # Try fetching from each provider's API using the message_id
    accounts = await db.list_email_accounts(status="active")
    for account in accounts:
        try:
            provider = account["provider"]
            token = account.get("token", "")

            if provider == "mailtm":
                msg = await mailtm.read_message(token, message_id)
            elif provider == "guerrilla":
                msg = await guerrilla.fetch_email(token, message_id)
            elif provider == "mailslurp":
                msg = await mailslurp.read_message(message_id)
            else:
                continue

            if msg and msg.get("subject"):
                # Save to DB
                msg["email_account_id"] = account["id"]
                await db.save_email_message(msg)
                verification = extract_verification_data(msg.get("body_text"), msg.get("body_html"))
                return sanitize_tool_output("read_email", {**msg, "verification": verification})
        except Exception:
            continue

    return {"error": "Message not found", "message_id": message_id}


# ===========================================================================
# TOOL 17: extract_verification
# ===========================================================================

@mcp.tool
async def extract_verification(
    ctx: Context,
    message_id: str,
) -> dict:
    """Extract verification codes and links from an email message.

    Parses OTP codes (4-8 digit), alphanumeric codes, and verification URLs.

    Args:
        message_id: ID of the email message to parse.
    """
    db = _get_db(ctx)
    msg = await db.get_email_message(message_id)
    if not msg:
        return {"error": "Message not found. Use read_email first to fetch the full message.", "message_id": message_id}

    result = extract_verification_data(msg.get("body_text"), msg.get("body_html"))
    result["message_id"] = message_id
    result["subject"] = msg.get("subject", "")
    return result


# ===========================================================================
# TOOL 18: delete_email_account
# ===========================================================================

@mcp.tool
async def delete_email_account(
    ctx: Context,
    email_id: str,
) -> dict:
    """Delete/burn an email account.

    Marks as burned in DB and deletes on provider if supported.

    Args:
        email_id: UUID of the email account.
    """
    db = _get_db(ctx)
    account = await db.get_email_account(email_id=email_id)
    if not account:
        return {"error": "Email account not found"}

    provider = account["provider"]
    token = account.get("token", "")
    deleted_on_provider = False

    try:
        if provider == "mailtm" and token:
            deleted_on_provider = await mailtm.delete_account(token, account.get("password", ""))
        elif provider == "mailslurp" and token:
            deleted_on_provider = await mailslurp.delete_inbox(token)
        # Guerrilla Mail doesn't support deletion
    except Exception as e:
        logger.warning("Failed to delete on provider %s: %s", provider, e)

    await db.update_email_account(email_id, {"status": "burned"})
    return {"email_id": email_id, "address": account["address"], "status": "burned", "deleted_on_provider": deleted_on_provider}


# ===========================================================================
# TOOL 19: provision_phone
# ===========================================================================

@mcp.tool
async def provision_phone(
    ctx: Context,
    provider: str = "twilio",
    country: str = "US",
    persona_id: Optional[str] = None,
    service: str = "any",
) -> dict:
    """Provision a phone number for SMS verification.

    Args:
        provider: "twilio" or "fivesim".
        country: Country code (default "US"). For 5sim use lowercase (e.g., "usa", "russia").
        persona_id: Optional UUID to link to a persona.
        service: For 5sim only — target service (e.g., "google", "facebook", "any").
    """
    db = _get_db(ctx)

    try:
        if provider == "twilio":
            result = await twilio_client.provision_number(country=country)
        elif provider == "fivesim":
            result = await fivesim.buy_activation(country=country, service=service)
        else:
            return {"error": f"Unknown provider: {provider}. Use 'twilio' or 'fivesim'."}

        phone_data = {
            "persona_id": persona_id,
            "provider": provider,
            "number": result["number"],
            "country": result.get("country", country),
            "capabilities": result.get("capabilities", {"sms": True}),
            "provider_id": result.get("provider_id", result.get("order_id", "")),
        }
        saved = await db.create_phone_number(phone_data)
        logger.info("Provisioned phone: %s (%s)", saved["number"], provider)
        return saved

    except Exception as e:
        return {"error": str(e), "provider": provider}


# ===========================================================================
# TOOL 20: list_phone_numbers
# ===========================================================================

@mcp.tool
async def list_phone_numbers(
    ctx: Context,
    persona_id: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List provisioned phone numbers.

    Args:
        persona_id: Filter by persona UUID.
        provider: Filter by provider ("twilio", "fivesim").
        status: Filter by status ("active", "released", "expired").
    """
    db = _get_db(ctx)
    numbers = await db.list_phone_numbers(persona_id=persona_id, provider=provider, status=status)
    return {"count": len(numbers), "numbers": numbers}


# ===========================================================================
# TOOL 21: check_sms
# ===========================================================================

@mcp.tool
async def check_sms(
    ctx: Context,
    phone_id: str,
) -> dict:
    """Check for received SMS messages on a phone number.

    Args:
        phone_id: UUID of the phone number (from provision_phone).
    """
    db = _get_db(ctx)
    phone = await db.get_phone_number(phone_id)
    if not phone:
        return {"error": "Phone number not found"}

    try:
        provider = phone["provider"]
        provider_id = phone.get("provider_id", "")

        if provider == "twilio":
            messages = await twilio_client.get_incoming_sms(phone["number"])
        elif provider == "fivesim":
            result = await fivesim.check_order(provider_id)
            messages = result.get("sms", [])
        else:
            return {"error": f"Unknown provider: {provider}"}

        # Save messages to DB
        for m in messages:
            m["phone_number_id"] = phone_id
            await db.save_sms_message(m)

        # Auto-extract verification from latest message
        verification = None
        if messages:
            latest_body = messages[0].get("body", "")
            verification = extract_verification_data(text=latest_body)

        return {
            "number": phone["number"],
            "provider": provider,
            "message_count": len(messages),
            "messages": messages,
            "verification": verification,
        }

    except Exception as e:
        return {"error": str(e), "number": phone["number"]}


# ===========================================================================
# TOOL 22: release_phone
# ===========================================================================

@mcp.tool
async def release_phone(
    ctx: Context,
    phone_id: str,
) -> dict:
    """Release/dispose of a phone number.

    Releases on the provider and marks as released in DB.

    Args:
        phone_id: UUID of the phone number.
    """
    db = _get_db(ctx)
    phone = await db.get_phone_number(phone_id)
    if not phone:
        return {"error": "Phone number not found"}

    provider = phone["provider"]
    provider_id = phone.get("provider_id", "")
    released = False

    try:
        if provider == "twilio" and provider_id:
            released = await twilio_client.release_number(provider_id)
        elif provider == "fivesim" and provider_id:
            released = await fivesim.finish_order(provider_id)
    except Exception as e:
        logger.warning("Failed to release on provider %s: %s", provider, e)

    await db.update_phone_status(phone_id, "released")
    return {"phone_id": phone_id, "number": phone["number"], "status": "released", "released_on_provider": released}


# ===========================================================================
# TOOL 23: launch_browser
# ===========================================================================

@mcp.tool
async def launch_browser(
    ctx: Context,
    engine: str = "patchright",
    headless: bool = True,
    persona_id: Optional[str] = None,
    proxy_server: Optional[str] = None,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Launch a stealth browser session.

    Supports two engines: Patchright (anti-detect Chromium) and Camoufox (anti-detect Firefox).
    Sessions persist across tool calls until explicitly closed.

    Args:
        engine: "patchright" (Chromium) or "camoufox" (Firefox). Default "patchright".
        headless: Run without GUI. Default true.
        persona_id: Optional UUID to track which persona is browsing.
        proxy_server: Proxy URL (e.g., "http://proxy:8080" or "socks5://proxy:1080").
        proxy_username: Proxy auth username.
        proxy_password: Proxy auth password.
        user_agent: Override user agent string.
    """
    sessions = _get_sessions(ctx)
    proxy = None
    if proxy_server:
        proxy = {"server": proxy_server, "username": proxy_username, "password": proxy_password}

    try:
        session = await sessions.create_session(
            engine=engine,
            headless=headless,
            proxy=proxy,
            user_agent=user_agent,
            persona_id=persona_id,
        )
        return session.to_dict()
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 24: close_browser
# ===========================================================================

@mcp.tool
async def close_browser(
    ctx: Context,
    session_id: str,
) -> dict:
    """Close a browser session and free resources.

    Args:
        session_id: UUID of the session (from launch_browser).
    """
    sessions = _get_sessions(ctx)
    closed = await sessions.close_session(session_id)
    if not closed:
        return {"error": "Session not found", "session_id": session_id}
    return {"session_id": session_id, "status": "closed"}


# ===========================================================================
# TOOL 25: list_browser_sessions
# ===========================================================================

@mcp.tool
async def list_browser_sessions(
    ctx: Context,
) -> dict:
    """List all active browser sessions with URLs, engines, and persona links."""
    sessions = _get_sessions(ctx)
    session_list = sessions.list_sessions()
    return {"count": len(session_list), "sessions": session_list}


# ===========================================================================
# TOOL 26: browser_goto
# ===========================================================================

@mcp.tool
async def browser_goto(
    ctx: Context,
    session_id: str,
    url: str,
    wait_until: str = "load",
) -> dict:
    """Navigate to a URL in a browser session.

    URL is validated for safe schemes (http/https only) and SSRF protection
    (internal IPs blocked).

    Args:
        session_id: UUID of the session.
        url: URL to navigate to.
        wait_until: "load", "domcontentloaded", or "networkidle". Default "load".
    """
    try:
        url = validate_url(url)
    except ValidationError as e:
        return {"error": str(e)}

    sessions = _get_sessions(ctx)
    try:
        return await sessions.goto(session_id, url, wait_until)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 27: browser_back
# ===========================================================================

@mcp.tool
async def browser_back(
    ctx: Context,
    session_id: str,
) -> dict:
    """Go back in browser history.

    Args:
        session_id: UUID of the session.
    """
    sessions = _get_sessions(ctx)
    try:
        return await sessions.back(session_id)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 28: browser_click
# ===========================================================================

@mcp.tool
async def browser_click(
    ctx: Context,
    session_id: str,
    selector: str,
) -> dict:
    """Click an element by CSS selector.

    Args:
        session_id: UUID of the session.
        selector: CSS selector (e.g., "button.submit", "#login", "a[href='/signup']").
    """
    sessions = _get_sessions(ctx)
    try:
        return await sessions.click(session_id, selector)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 29: browser_type
# ===========================================================================

@mcp.tool
async def browser_type(
    ctx: Context,
    session_id: str,
    selector: str,
    text: str,
    delay: int = 50,
) -> dict:
    """Type text into an input element with human-like keystroke delay.

    Args:
        session_id: UUID of the session.
        selector: CSS selector of the input element.
        text: Text to type.
        delay: Milliseconds between keystrokes (default 50, for human-like typing).
    """
    sessions = _get_sessions(ctx)
    try:
        return await sessions.type_text(session_id, selector, text, delay)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 30: browser_select
# ===========================================================================

@mcp.tool
async def browser_select(
    ctx: Context,
    session_id: str,
    selector: str,
    value: str,
) -> dict:
    """Select a dropdown option by value.

    Args:
        session_id: UUID of the session.
        selector: CSS selector of the select element.
        value: Option value to select.
    """
    sessions = _get_sessions(ctx)
    try:
        return await sessions.select_option(session_id, selector, value)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 31: browser_screenshot
# ===========================================================================

@mcp.tool
async def browser_screenshot(
    ctx: Context,
    session_id: str,
    full_page: bool = False,
) -> dict:
    """Capture a screenshot of the current page.

    Saves JPEG to data/screenshots/ and returns base64 + file path.

    Args:
        session_id: UUID of the session.
        full_page: Capture entire scrollable page (default false, viewport only).
    """
    sessions = _get_sessions(ctx)
    try:
        result = await sessions.screenshot(session_id, full_page)
        result["security_note"] = "Screenshot may contain sensitive page content (login forms, credentials). Review before sharing."
        return result
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 32: browser_get_text
# ===========================================================================

@mcp.tool
async def browser_get_text(
    ctx: Context,
    session_id: str,
    selector: Optional[str] = None,
    format: str = "text",
) -> dict:
    """Extract visible text or HTML from the page or a specific element.

    Args:
        session_id: UUID of the session.
        selector: Optional CSS selector. If omitted, extracts from entire page body.
        format: "text" for visible text, "html" for raw HTML.
    """
    sessions = _get_sessions(ctx)
    try:
        result = await sessions.get_text(session_id, selector, format)
        return sanitize_tool_output("browser_get_text", result)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 33: configure_proxy
# ===========================================================================

@mcp.tool
async def configure_proxy(
    ctx: Context,
    provider: str = "generic",
    persona_id: Optional[str] = None,
    country: str = "us",
    city: Optional[str] = None,
    proxy_url: Optional[str] = None,
    sticky: bool = True,
) -> dict:
    """Set up a proxy for a persona. Supports IPRoyal, Bright Data, Decodo, and generic URLs.

    Args:
        provider: "iproyal", "brightdata", "decodo", or "generic". Default "generic".
        persona_id: UUID to link this proxy to a persona.
        country: Target exit country code (default "us").
        city: Optional target city.
        proxy_url: For "generic" provider — supply your own proxy URL (http/socks5).
        sticky: Use sticky session for consistent IP (default true).
    """
    db = _get_db(ctx)
    try:
        if provider == "generic":
            if not proxy_url:
                return {"error": "Generic provider requires proxy_url parameter"}
            result = {"proxy_url": proxy_url, "provider": "generic", "country": country, "sticky_session": ""}
        else:
            result = proxy_manager.generate_proxy_url(provider, country, city, sticky)

        config = {
            "persona_id": persona_id,
            "provider": provider,
            "proxy_url": result["proxy_url"],
            "country": result.get("country", country),
            "city": city,
            "sticky_session": result.get("sticky_session", ""),
        }
        saved = await db.create_proxy_config(config)
        logger.info("Proxy configured: %s (%s) for persona %s", provider, country, persona_id)
        return saved
    except Exception as e:
        return {"error": str(e), "provider": provider}


# ===========================================================================
# TOOL 34: rotate_proxy
# ===========================================================================

@mcp.tool
async def rotate_proxy(
    ctx: Context,
    proxy_id: Optional[str] = None,
    persona_id: Optional[str] = None,
) -> dict:
    """Rotate to a new IP for a persona's proxy (new sticky session).

    Args:
        proxy_id: UUID of the proxy config.
        persona_id: UUID of the persona (uses their active proxy).
    """
    db = _get_db(ctx)
    if proxy_id:
        config = await db.get_proxy_config(proxy_id)
    elif persona_id:
        config = await db.get_proxy_for_persona(persona_id)
    else:
        return {"error": "Provide proxy_id or persona_id"}

    if not config:
        return {"error": "Proxy config not found"}

    try:
        if config["provider"] == "tor":
            result = await tor_manager.new_identity()
            return {**result, "proxy_id": config["id"]}

        new_proxy = proxy_manager.rotate_session(
            config["proxy_url"], config["provider"], config.get("country", "us"), config.get("city"),
        )
        from datetime import datetime
        await db.update_proxy_config(config["id"], {
            "proxy_url": new_proxy["proxy_url"],
            "sticky_session": new_proxy.get("sticky_session", ""),
            "last_rotated_at": datetime.utcnow().isoformat(),
        })
        return {"proxy_id": config["id"], "new_proxy_url": new_proxy["proxy_url"], "provider": config["provider"]}
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# TOOL 35: list_proxy_configs
# ===========================================================================

@mcp.tool
async def list_proxy_configs(
    ctx: Context,
    persona_id: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List all proxy configurations.

    Args:
        persona_id: Filter by persona UUID.
        provider: Filter by provider.
        status: Filter by status ("active", "expired", "failed").
    """
    db = _get_db(ctx)
    configs = await db.list_proxy_configs(persona_id=persona_id, provider=provider, status=status)
    return {"count": len(configs), "configs": configs}


# ===========================================================================
# TOOL 36: remove_proxy
# ===========================================================================

@mcp.tool
async def remove_proxy(
    ctx: Context,
    proxy_id: str,
) -> dict:
    """Remove a proxy configuration.

    Args:
        proxy_id: UUID of the proxy config to remove.
    """
    db = _get_db(ctx)
    deleted = await db.delete_proxy_config(proxy_id)
    if not deleted:
        return {"error": "Proxy config not found", "proxy_id": proxy_id}
    return {"proxy_id": proxy_id, "status": "removed"}


# ===========================================================================
# TOOL 37: test_proxy
# ===========================================================================

@mcp.tool
async def test_proxy(
    ctx: Context,
    proxy_id: Optional[str] = None,
    proxy_url: Optional[str] = None,
) -> dict:
    """Test a proxy connection and return the exit IP + geolocation.

    Args:
        proxy_id: UUID of an existing proxy config to test.
        proxy_url: Raw proxy URL to test directly (http/socks5).
    """
    if proxy_id:
        db = _get_db(ctx)
        config = await db.get_proxy_config(proxy_id)
        if not config:
            return {"error": "Proxy config not found"}
        proxy_url = config["proxy_url"]

    if not proxy_url:
        return {"error": "Provide proxy_id or proxy_url"}

    result = await proxy_manager.test_proxy_connection(proxy_url)

    # If connected, look up geolocation
    if result.get("exit_ip"):
        geo = await geolocation.lookup_ip(result["exit_ip"])
        result["geolocation"] = geo

    return result


# ===========================================================================
# TOOL 38: start_tor
# ===========================================================================

@mcp.tool
async def start_tor(
    ctx: Context,
    persona_id: Optional[str] = None,
    country: Optional[str] = None,
) -> dict:
    """Start a Tor connection (Stem if daemon available, Torpy fallback).

    Returns SOCKS5 proxy URL for browser/request routing.
    Optionally saves as a proxy config linked to a persona.

    Args:
        persona_id: Optional persona to link the Tor proxy to.
        country: Optional exit country preference.
    """
    result = await tor_manager.start_tor(country=country)

    if persona_id and result.get("socks_url"):
        db = _get_db(ctx)
        config = {
            "persona_id": persona_id,
            "provider": "tor",
            "proxy_url": result["socks_url"],
            "country": country or "",
        }
        saved = await db.create_proxy_config(config)
        result["proxy_config_id"] = saved["id"]

    return result


# ===========================================================================
# TOOL 39: tor_new_identity
# ===========================================================================

@mcp.tool
async def tor_new_identity(
    ctx: Context,
) -> dict:
    """Request a new Tor circuit (new exit IP).

    Only works when Tor daemon + Stem are available.
    """
    return await tor_manager.new_identity()


# ===========================================================================
# TOOL 40: tor_status
# ===========================================================================

@mcp.tool
async def tor_status(
    ctx: Context,
) -> dict:
    """Check Tor connection status, current exit IP, and circuit info."""
    return await tor_manager.get_status()


# ===========================================================================
# TOOL 41: mullvad_connect
# ===========================================================================

@mcp.tool
async def mullvad_connect(
    ctx: Context,
    action: str = "status",
    country: Optional[str] = None,
) -> dict:
    """Control Mullvad VPN (Linux only).

    Args:
        action: "connect", "disconnect", or "status". Default "status".
        country: Relay country code for connect (e.g., "us", "se", "de").
    """
    if action == "connect":
        return await mullvad.connect(country=country)
    elif action == "disconnect":
        return await mullvad.disconnect()
    else:
        return await mullvad.status()


# ===========================================================================
# TOOL 42: verify_ip
# ===========================================================================

@mcp.tool
async def verify_ip(
    ctx: Context,
    ip: str = "auto",
) -> dict:
    """Look up geolocation for any IP address.

    Uses IPinfo API with MaxMind GeoLite2 as fallback.

    Args:
        ip: IP address to check. Use "auto" to check your current public IP.
    """
    if ip == "auto":
        ip = await geolocation.get_current_ip()
        if not ip:
            return {"error": "Could not determine current IP"}

    return await geolocation.lookup_ip(ip)


# ===========================================================================
# TOOL 43: verify_persona_opsec
# ===========================================================================

@mcp.tool
async def verify_persona_opsec(
    ctx: Context,
    persona_id: str,
) -> dict:
    """Comprehensive OpSec check for a persona.

    Checks: proxy configured, exit IP matches claimed country, anonymity detection.
    Returns pass/fail checklist with recommendations.

    Args:
        persona_id: UUID of the persona to verify.
    """
    db = _get_db(ctx)
    persona = await db.get_persona(persona_id=persona_id)
    if not persona:
        return {"error": "Persona not found"}

    proxy_config = await db.get_proxy_for_persona(persona_id)
    return await geolocation.verify_persona_opsec(persona, proxy_config)


# ===========================================================================
# TOOL 44: check_ip_reputation
# ===========================================================================

@mcp.tool
async def check_ip_reputation(
    ctx: Context,
    ip: str,
) -> dict:
    """Check if an IP is flagged as VPN/proxy/bot.

    Cross-references IPinfo anonymity data and returns risk assessment.

    Args:
        ip: IP address to check.
    """
    return await geolocation.check_ip_reputation(ip)


# ===========================================================================
# TOOL 45: register_social_account
# ===========================================================================

@mcp.tool
async def register_social_account(
    ctx: Context,
    persona_id: str,
    platform: str,
    username: str,
    access_token: Optional[str] = None,
    postiz_integration_id: Optional[str] = None,
) -> dict:
    """Link a social media account to a persona.

    Does NOT create the account on the platform — use browser tools for that.
    This registers it in the DB for posting and tracking.

    Args:
        persona_id: UUID of the persona.
        platform: "x", "reddit", "linkedin", "instagram", "mastodon", etc.
        username: Platform handle/username.
        access_token: Optional API token or access credential.
        postiz_integration_id: Optional Postiz integration ID for scheduling.
    """
    db = _get_db(ctx)
    data = {
        "persona_id": persona_id,
        "platform": platform.lower(),
        "username": username,
        "postiz_integration_id": postiz_integration_id,
    }
    if access_token:
        data["credentials"] = {"access_token": access_token}
    saved = await db.create_social_account(data)
    logger.info("Registered social account: %s on %s", username, platform)
    return saved


# ===========================================================================
# TOOL 46: list_social_accounts
# ===========================================================================

@mcp.tool
async def list_social_accounts(
    ctx: Context,
    persona_id: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List social media accounts.

    Args:
        persona_id: Filter by persona UUID.
        platform: Filter by platform.
        status: Filter by status ("active", "suspended", "burned").
    """
    db = _get_db(ctx)
    accounts = await db.list_social_accounts(persona_id=persona_id, platform=platform, status=status)
    return {"count": len(accounts), "accounts": accounts}


# ===========================================================================
# TOOL 47: update_social_account
# ===========================================================================

@mcp.tool
async def update_social_account(
    ctx: Context,
    account_id: str,
    status: Optional[str] = None,
    username: Optional[str] = None,
    postiz_integration_id: Optional[str] = None,
) -> dict:
    """Update a social account's status or details.

    Args:
        account_id: UUID of the social account.
        status: New status ("active", "suspended", "burned").
        username: Updated username.
        postiz_integration_id: Updated Postiz integration ID.
    """
    db = _get_db(ctx)
    updates = {}
    if status:
        updates["status"] = status
    if username:
        updates["username"] = username
    if postiz_integration_id:
        updates["postiz_integration_id"] = postiz_integration_id
    if not updates:
        return {"error": "No fields to update"}
    result = await db.update_social_account(account_id, updates)
    if not result:
        return {"error": "Account not found"}
    return result


# ===========================================================================
# TOOL 48: get_platform_constraints
# ===========================================================================

@mcp.tool
async def get_platform_constraints(
    platform: str,
) -> dict:
    """Get posting rules and constraints for a social media platform.

    Returns character limits, hashtag rules, media requirements, and best practices.
    Use this to format content correctly before posting.

    Args:
        platform: "x", "reddit", "linkedin", "instagram", "mastodon", "bluesky", "tiktok", "threads", "medium", "pinterest".
    """
    return get_constraints(platform)


# ===========================================================================
# TOOL 49: schedule_post
# ===========================================================================

@mcp.tool
async def schedule_post(
    ctx: Context,
    persona_id: str,
    platform: str,
    content: str,
    scheduled_at: Optional[str] = None,
    subreddit: Optional[str] = None,
    title: Optional[str] = None,
    media_urls: Optional[list[str]] = None,
) -> dict:
    """Schedule a post for a persona on a platform.

    Routes to Postiz (if integration configured), or saves as draft for direct posting.
    For Reddit, provide subreddit and title.

    Args:
        persona_id: UUID of the persona.
        platform: Target platform.
        content: Post text content.
        scheduled_at: ISO timestamp for scheduling. Null = save as draft.
        subreddit: Required for Reddit posts.
        title: Required for Reddit posts.
        media_urls: Optional media URLs to attach.
    """
    db = _get_db(ctx)
    account = await db.get_social_account_for_persona(persona_id, platform.lower())
    if not account:
        return {"error": f"No {platform} account registered for this persona. Use register_social_account first."}

    # Try Postiz if integration configured
    postiz_post_id = None
    if account.get("postiz_integration_id"):
        try:
            result = await postiz_client.schedule_post(
                content=content,
                integration_id=account["postiz_integration_id"],
                scheduled_at=scheduled_at,
                media_urls=media_urls,
            )
            postiz_post_id = result.get("id", "")
        except Exception as e:
            logger.warning("Postiz scheduling failed: %s. Saving as draft.", e)

    # Save to DB
    post_data = {
        "social_account_id": account["id"],
        "platform": platform.lower(),
        "content": content,
        "scheduled_at": scheduled_at,
        "postiz_post_id": postiz_post_id,
        "status": "scheduled" if (scheduled_at or postiz_post_id) else "draft",
    }
    if media_urls:
        post_data["media_urls"] = media_urls

    saved = await db.create_social_post(post_data)
    return saved


# ===========================================================================
# TOOL 50: post_now
# ===========================================================================

@mcp.tool
async def post_now(
    ctx: Context,
    persona_id: str,
    platform: str,
    content: str,
    subreddit: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """Post immediately to a platform using direct client (bypasses scheduler).

    For X/Twitter: uses Twikit (requires persona's X credentials in account).
    For Reddit: uses PRAW (requires persona's Reddit credentials in account).

    Args:
        persona_id: UUID of the persona.
        platform: "x" or "reddit".
        content: Post text.
        subreddit: Required for Reddit.
        title: Required for Reddit.
    """
    db = _get_db(ctx)
    account = await db.get_social_account_for_persona(persona_id, platform.lower())
    if not account:
        return {"error": f"No {platform} account registered for this persona."}

    creds = account.get("credentials", {})

    try:
        if platform.lower() in ("x", "twitter"):
            result = await twikit_client.post_tweet(
                username=account["username"],
                email=creds.get("email", ""),
                password=creds.get("password", ""),
                content=content,
            )
        elif platform.lower() == "reddit":
            if not subreddit or not title:
                return {"error": "Reddit posts require subreddit and title parameters."}
            result = await reddit_client.post_to_subreddit(
                username=account["username"],
                password=creds.get("password", ""),
                subreddit=subreddit,
                title=title,
                content=content,
            )
        else:
            return {"error": f"Direct posting not supported for {platform}. Use schedule_post with Postiz instead."}

        # Save to DB
        from datetime import datetime
        post_data = {
            "social_account_id": account["id"],
            "platform": platform.lower(),
            "content": content,
            "posted_at": datetime.utcnow().isoformat(),
            "status": "posted",
        }
        await db.create_social_post(post_data)
        return result

    except Exception as e:
        return {"error": str(e), "platform": platform}


# ===========================================================================
# TOOL 51: list_posts
# ===========================================================================

@mcp.tool
async def list_posts(
    ctx: Context,
    persona_id: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List posts for a persona or across all accounts.

    Args:
        persona_id: Filter by persona (looks up all their social accounts).
        platform: Filter by platform.
        status: Filter by status ("draft", "scheduled", "posted", "failed").
    """
    db = _get_db(ctx)

    if persona_id:
        accounts = await db.list_social_accounts(persona_id=persona_id, platform=platform)
        all_posts = []
        for acct in accounts:
            posts = await db.list_social_posts(social_account_id=acct["id"], status=status)
            all_posts.extend(posts)
        return {"count": len(all_posts), "posts": all_posts}
    else:
        posts = await db.list_social_posts(platform=platform, status=status)
        return {"count": len(posts), "posts": posts}


# ===========================================================================
# TOOL 52: get_activity_summary
# ===========================================================================

@mcp.tool
async def get_activity_summary(
    ctx: Context,
    persona_id: str,
    days_back: int = 30,
) -> dict:
    """Get posting activity summary for a persona.

    Args:
        persona_id: UUID of the persona.
        days_back: How many days back to analyze (default 30).
    """
    db = _get_db(ctx)
    return await db.get_activity_summary(persona_id, days_back)


# ===========================================================================
# TOOL 53: generate_posting_schedule_tool
# ===========================================================================

@mcp.tool
async def generate_posting_schedule_tool(
    persona_id: Optional[str] = None,
    platform: Optional[str] = None,
    posts_per_week: int = 4,
    days_ahead: int = 7,
) -> dict:
    """Generate a realistic posting schedule with human-like timing jitter.

    Returns time slots that mimic real human posting patterns (peak at lunch/evening,
    random gaps, variable frequency). Use these slots with schedule_post.

    Args:
        persona_id: Optional persona for context (returned in output).
        platform: Optional platform for context.
        posts_per_week: Target posts per week (default 4).
        days_ahead: How many days to schedule ahead (default 7).
    """
    posts_per_week = max(1, min(21, posts_per_week))
    slots = generate_posting_schedule(posts_per_week=posts_per_week, days_ahead=days_ahead)
    return {
        "persona_id": persona_id,
        "platform": platform,
        "posts_per_week": posts_per_week,
        "slot_count": len(slots),
        "slots": slots,
    }


# ===========================================================================
# TOOL 54: record_engagement
# ===========================================================================

@mcp.tool
async def record_engagement(
    ctx: Context,
    post_id: str,
    likes: int = 0,
    shares: int = 0,
    comments: int = 0,
) -> dict:
    """Record engagement metrics on a social post.

    Used to track how posts perform and build realistic activity history.

    Args:
        post_id: UUID of the social post.
        likes: Number of likes/upvotes.
        shares: Number of shares/retweets.
        comments: Number of comments/replies.
    """
    db = _get_db(ctx)
    engagement = {"likes": likes, "shares": shares, "comments": comments}
    result = await db.update_social_post(post_id, {"engagement": engagement})
    if not result:
        return {"error": "Post not found", "post_id": post_id}
    return result


# ===========================================================================
# RESOURCES
# ===========================================================================

@mcp.resource("persona://{identifier}")
async def persona_resource(identifier: str) -> str:
    """Get full persona JSON by ID or codename."""
    db = DatabaseManager()
    await db.init_db()
    try:
        persona = await db.get_persona(persona_id=identifier)
        if not persona:
            persona = await db.get_persona(codename=identifier)
        if not persona:
            return json.dumps({"error": "Persona not found", "identifier": identifier})
        return json.dumps(persona, indent=2, default=str)
    finally:
        await db.close()


@mcp.resource("personas://active")
async def active_personas_resource() -> str:
    """List all active personas (summary view)."""
    db = DatabaseManager()
    await db.init_db()
    try:
        personas = await db.list_personas(status="active", limit=100)
        return json.dumps({"count": len(personas), "personas": personas}, indent=2, default=str)
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
