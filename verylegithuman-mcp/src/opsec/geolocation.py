"""IP geolocation verification via IPinfo API and MaxMind GeoLite2.

IPinfo (primary): API-based, 50K free requests/month.
MaxMind (fallback): Local .mmdb database, instant lookups.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from ..config import (
    GEOLOCATION_TIMEOUT,
    GEOIP_DB_DIR,
    IP_CHECK_URL,
    IPINFO_TOKEN,
    MAXMIND_LICENSE_KEY,
)

logger = logging.getLogger(__name__)

# Check MaxMind availability
_GEOIP2_AVAILABLE = False
try:
    import geoip2.database
    _GEOIP2_AVAILABLE = True
except ImportError:
    logger.info("geoip2 not installed — MaxMind fallback unavailable")


async def get_current_ip(proxy_url: Optional[str] = None) -> Optional[str]:
    """Get current public IP, optionally through a proxy."""
    try:
        client_kwargs = {"timeout": GEOLOCATION_TIMEOUT}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(IP_CHECK_URL)
            data = resp.json()
            return data.get("ip", resp.text.strip())
    except Exception:
        return None


async def lookup_ip(ip: str) -> dict:
    """Look up geolocation for an IP address.

    Tries IPinfo API first, falls back to MaxMind GeoLite2 local DB.
    Returns: country, city, region, timezone, org, is_vpn, is_proxy, is_tor.
    """
    # Try IPinfo first
    if IPINFO_TOKEN:
        try:
            result = await _ipinfo_lookup(ip)
            if result:
                return result
        except Exception as e:
            logger.warning("IPinfo lookup failed for %s: %s", ip, e)

    # Try IPinfo without token (limited free tier)
    try:
        result = await _ipinfo_lookup(ip)
        if result:
            return result
    except Exception as e:
        logger.debug("IPinfo tokenless lookup failed: %s", e)

    # Fallback to MaxMind local DB
    if _GEOIP2_AVAILABLE:
        result = _maxmind_lookup(ip)
        if result:
            return result

    return {
        "ip": ip,
        "country": None,
        "city": None,
        "error": "No geolocation provider available. Set IPINFO_TOKEN or install geoip2 with GeoLite2 DB.",
    }


async def _ipinfo_lookup(ip: str) -> Optional[dict]:
    """Look up IP via IPinfo API."""
    headers = {}
    if IPINFO_TOKEN:
        headers["Authorization"] = f"Bearer {IPINFO_TOKEN}"

    async with httpx.AsyncClient(timeout=GEOLOCATION_TIMEOUT) as client:
        resp = await client.get(f"https://ipinfo.io/{ip}/json", headers=headers)
        if resp.status_code == 429:
            logger.warning("IPinfo rate limited")
            return None
        resp.raise_for_status()
        data = resp.json()

    # Parse privacy/anonymity fields (available in paid tiers)
    privacy = data.get("privacy", {})

    return {
        "ip": ip,
        "country": data.get("country", ""),
        "city": data.get("city", ""),
        "region": data.get("region", ""),
        "postal": data.get("postal", ""),
        "timezone": data.get("timezone", ""),
        "org": data.get("org", ""),
        "loc": data.get("loc", ""),  # lat,lng
        "is_vpn": privacy.get("vpn", None),
        "is_proxy": privacy.get("proxy", None),
        "is_tor": privacy.get("tor", None),
        "is_hosting": privacy.get("hosting", None),
        "source": "ipinfo",
    }


def _maxmind_lookup(ip: str) -> Optional[dict]:
    """Look up IP via MaxMind GeoLite2 local database."""
    if not _GEOIP2_AVAILABLE:
        return None

    GEOIP_DB_DIR.mkdir(parents=True, exist_ok=True)
    db_path = GEOIP_DB_DIR / "GeoLite2-City.mmdb"
    if not db_path.exists():
        logger.warning("MaxMind GeoLite2-City.mmdb not found at %s", db_path)
        return None

    try:
        with geoip2.database.Reader(str(db_path)) as reader:
            resp = reader.city(ip)
            return {
                "ip": ip,
                "country": resp.country.iso_code,
                "city": resp.city.name,
                "region": resp.subdivisions.most_specific.name if resp.subdivisions else None,
                "postal": resp.postal.code,
                "timezone": resp.location.time_zone,
                "org": None,  # Not in GeoLite2-City
                "loc": f"{resp.location.latitude},{resp.location.longitude}" if resp.location.latitude else None,
                "is_vpn": None,  # Requires paid Anonymous IP DB
                "is_proxy": None,
                "is_tor": None,
                "is_hosting": None,
                "source": "maxmind",
            }
    except Exception as e:
        logger.warning("MaxMind lookup failed for %s: %s", ip, e)
        return None


async def check_ip_reputation(ip: str) -> dict:
    """Check if an IP is flagged as VPN/proxy/bot.

    Uses available providers to cross-reference anonymity data.
    """
    geo = await lookup_ip(ip)

    risk_flags = []
    if geo.get("is_vpn"):
        risk_flags.append("VPN detected")
    if geo.get("is_proxy"):
        risk_flags.append("Proxy detected")
    if geo.get("is_tor"):
        risk_flags.append("Tor exit node")
    if geo.get("is_hosting"):
        risk_flags.append("Hosting/datacenter IP")

    risk_level = "low"
    if len(risk_flags) >= 2:
        risk_level = "high"
    elif len(risk_flags) == 1:
        risk_level = "medium"

    return {
        "ip": ip,
        "country": geo.get("country"),
        "city": geo.get("city"),
        "org": geo.get("org"),
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "details": geo,
    }


async def verify_persona_opsec(persona: dict, proxy_config: Optional[dict] = None) -> dict:
    """Run comprehensive OpSec verification for a persona.

    Checks: proxy configured, exit IP matches claimed country, anonymity flags.
    """
    checks = []

    # Check 1: Proxy configured?
    if proxy_config:
        checks.append({"check": "proxy_configured", "status": "pass", "detail": f"{proxy_config['provider']} proxy active"})

        # Check 2: Exit IP verification
        proxy_url = proxy_config.get("proxy_url")
        if proxy_url:
            exit_ip = await get_current_ip(proxy_url=proxy_url)
            if exit_ip:
                geo = await lookup_ip(exit_ip)
                checks.append({"check": "exit_ip_resolved", "status": "pass", "detail": f"Exit IP: {exit_ip}"})

                # Check 3: Country match
                persona_country = persona.get("address", {}).get("country", "").upper()
                exit_country = (geo.get("country") or "").upper()
                if persona_country and exit_country:
                    if persona_country == exit_country or exit_country in persona_country:
                        checks.append({"check": "country_match", "status": "pass", "detail": f"Persona: {persona_country}, Exit: {exit_country}"})
                    else:
                        checks.append({"check": "country_match", "status": "fail", "detail": f"MISMATCH — Persona: {persona_country}, Exit: {exit_country}"})
                else:
                    checks.append({"check": "country_match", "status": "skip", "detail": "Country data unavailable"})

                # Check 4: Anonymity detection
                if geo.get("is_vpn") or geo.get("is_proxy") or geo.get("is_tor"):
                    flags = [k for k in ["is_vpn", "is_proxy", "is_tor"] if geo.get(k)]
                    checks.append({"check": "anonymity_detected", "status": "warn", "detail": f"Detected: {', '.join(flags)}"})
                else:
                    checks.append({"check": "anonymity_detected", "status": "pass", "detail": "No anonymity flags"})
            else:
                checks.append({"check": "exit_ip_resolved", "status": "fail", "detail": "Could not resolve exit IP"})
    else:
        checks.append({"check": "proxy_configured", "status": "fail", "detail": "No proxy configured for this persona"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    total = len(checks)
    return {
        "persona_id": persona.get("id"),
        "persona_name": persona.get("full_name"),
        "score": f"{passed}/{total}",
        "checks": checks,
    }
