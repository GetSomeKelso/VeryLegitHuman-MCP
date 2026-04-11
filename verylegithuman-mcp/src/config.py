"""Centralized configuration for VeryLegitHuman MCP server."""

import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _env_int_clamped(name: str, default: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(max_val, _env_int(name, default)))


# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = DATA_DIR / "db"
FACES_DIR = DATA_DIR / "faces"
# --- Identity Generation ---
DEFAULT_LOCALE = _env_str("VLH_DEFAULT_LOCALE", "en_US")
BULK_GENERATE_MAX = _env_int_clamped("VLH_BULK_MAX", 20, 1, 50)

# --- Face Generation ---
TPDNE_URL = "https://thispersondoesnotexist.com"
TPDNE_TIMEOUT = _env_int_clamped("VLH_TPDNE_TIMEOUT", 15, 5, 60)

# --- Username ---
SHERLOCK_TIMEOUT = _env_int_clamped("VLH_SHERLOCK_TIMEOUT", 60, 10, 300)
DEFAULT_PLATFORMS = [
    "twitter", "github", "reddit", "instagram", "linkedin",
    "facebook", "tiktok", "pinterest", "tumblr", "medium",
    "discord", "twitch", "youtube", "snapchat", "telegram",
    "mastodon.social", "hackernews", "stackoverflow", "quora", "flickr",
]

# --- Codename Generation ---
CODENAME_ADJECTIVES = [
    "shadow", "crimson", "silent", "iron", "golden", "frost", "ember",
    "phantom", "azure", "raven", "storm", "midnight", "cobalt", "steel",
    "velvet", "obsidian", "scarlet", "onyx", "jade", "amber",
]
CODENAME_NOUNS = [
    "wolf", "hawk", "viper", "fox", "lynx", "bear", "eagle",
    "tiger", "panther", "falcon", "serpent", "owl", "sphinx",
    "phoenix", "dragon", "mantis", "scorpion", "cobra", "raven", "jaguar",
]

# --- Email Providers ---
MAILTM_BASE_URL = "https://api.mail.tm"
MAILTM_TIMEOUT = _env_int_clamped("VLH_MAILTM_TIMEOUT", 15, 5, 60)

GUERRILLA_BASE_URL = "https://api.guerrillamail.com/ajax.php"
GUERRILLA_TIMEOUT = _env_int_clamped("VLH_GUERRILLA_TIMEOUT", 15, 5, 60)

MAILSLURP_API_KEY = _env_str("MAILSLURP_API_KEY", "")

# --- Phone Providers ---
TWILIO_ACCOUNT_SID = _env_str("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = _env_str("TWILIO_AUTH_TOKEN", "")

FIVESIM_API_KEY = _env_str("FIVESIM_API_KEY", "")
FIVESIM_BASE_URL = "https://5sim.net/v1"
FIVESIM_TIMEOUT = _env_int_clamped("VLH_FIVESIM_TIMEOUT", 30, 10, 120)

# --- Verification Extraction ---
OTP_PATTERNS = [
    r'\b(\d{4,8})\b',
    r'\b([A-Z0-9]{6,8})\b',
]
VERIFICATION_LINK_PATTERNS = [
    r'(https?://\S*(?:verify|confirm|activate|validate|token|code)\S*)',
]

# --- Browser Automation ---
BROWSER_DEFAULT_HEADLESS = True
BROWSER_DEFAULT_VIEWPORT = (1280, 800)
BROWSER_NAVIGATION_TIMEOUT = _env_int_clamped("VLH_NAV_TIMEOUT", 30000, 5000, 120000)
BROWSER_TYPE_DELAY = _env_int_clamped("VLH_TYPE_DELAY", 50, 0, 500)
BROWSER_SCREENSHOT_DIR = DATA_DIR / "screenshots"
BROWSER_MAX_SESSIONS = _env_int_clamped("VLH_MAX_SESSIONS", 5, 1, 20)

# --- Proxy Providers ---
IPROYAL_API_KEY = _env_str("IPROYAL_API_KEY", "")
IPROYAL_PROXY_HOST = "geo.iproyal.com"
IPROYAL_PROXY_PORT = 12321

BRIGHTDATA_CUSTOMER_ID = _env_str("BRIGHTDATA_CUSTOMER_ID", "")
BRIGHTDATA_ZONE_PASSWORD = _env_str("BRIGHTDATA_ZONE_PASSWORD", "")
BRIGHTDATA_PROXY_HOST = "zproxy.lum-superproxy.io"
BRIGHTDATA_PROXY_PORT = 22225

DECODO_USERNAME = _env_str("DECODO_USERNAME", "")
DECODO_PASSWORD = _env_str("DECODO_PASSWORD", "")
DECODO_PROXY_HOST = "gate.smartproxy.com"
DECODO_PROXY_PORT = 10001

# --- Tor ---
TOR_CONTROL_PORT = _env_int_clamped("TOR_CONTROL_PORT", 9051, 1024, 65535)
TOR_SOCKS_PORT = _env_int_clamped("TOR_SOCKS_PORT", 9050, 1024, 65535)
TOR_CONTROL_PASSWORD = _env_str("TOR_CONTROL_PASSWORD", "")

# --- Geolocation ---
IPINFO_TOKEN = _env_str("IPINFO_TOKEN", "")
MAXMIND_LICENSE_KEY = _env_str("MAXMIND_LICENSE_KEY", "")
GEOIP_DB_DIR = DATA_DIR / "geoip"
IP_CHECK_URL = "https://api.ipify.org?format=json"
GEOLOCATION_TIMEOUT = _env_int_clamped("VLH_GEO_TIMEOUT", 10, 5, 30)

# --- Social Providers ---
POSTIZ_API_KEY = _env_str("POSTIZ_API_KEY", "")
POSTIZ_BASE_URL = _env_str("POSTIZ_BASE_URL", "https://app.postiz.com/api/v1")
POSTIZ_TIMEOUT = _env_int_clamped("VLH_POSTIZ_TIMEOUT", 15, 5, 60)

REDDIT_CLIENT_ID = _env_str("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = _env_str("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = _env_str("REDDIT_USER_AGENT", "VeryLegitHuman/1.0")

TWIKIT_ENABLED = _env_str("TWIKIT_ENABLED", "false").lower() == "true"

# --- Security (Phase 6: OWASP MCP/LLM Top 10 Hardening) ---
ALLOWED_URL_SCHEMES = ["http", "https"]
BLOCKED_URL_SCHEMES = ["file", "ftp", "javascript", "data", "vbscript", "about"]
BLOCKED_IP_PREFIXES = [
    "127.", "10.", "0.", "169.254.",  # Loopback, private class A, link-local
    "192.168.",                        # Private class C
]
BLOCKED_IP_RANGES_172 = range(16, 32)  # 172.16.0.0 - 172.31.255.255

MAX_TEXT_OUTPUT_BYTES = _env_int_clamped("VLH_MAX_OUTPUT", 50_000, 1_000, 500_000)
MAX_URL_LENGTH = 2048
MAX_STRING_LENGTH = 10_000
MAX_BIO_LENGTH = 5_000
MAX_CONTENT_LENGTH = 50_000
MAX_EMAIL_ACCOUNTS = _env_int_clamped("VLH_MAX_EMAILS", 50, 1, 500)
MAX_PHONE_NUMBERS = _env_int_clamped("VLH_MAX_PHONES", 20, 1, 100)
MAX_SOCIAL_ACCOUNTS = _env_int_clamped("VLH_MAX_SOCIAL", 100, 1, 500)

AUDIT_LOG_ENABLED = _env_str("VLH_AUDIT_LOG", "true").lower() == "true"
SENSITIVE_FIELDS = {"password", "token", "auth_token", "api_key", "credentials_json", "credentials"}

VALID_PROVIDERS_EMAIL = {"mailtm", "guerrilla", "mailslurp"}
VALID_PROVIDERS_PHONE = {"twilio", "fivesim"}
VALID_PROVIDERS_PROXY = {"iproyal", "brightdata", "decodo", "generic", "tor", "mullvad"}
VALID_ENGINES = {"patchright", "camoufox"}
VALID_STATUSES = {"active", "burned", "retired", "expired", "failed", "released", "suspended"}
VALID_PLATFORMS = {
    "x", "twitter", "reddit", "linkedin", "instagram", "mastodon",
    "bluesky", "tiktok", "threads", "medium", "pinterest", "facebook",
    "youtube", "discord", "slack", "dev.to", "hashnode", "dribbble",
}
