# VeryLegitHuman MCP

A 54-tool [Model Context Protocol](https://modelcontextprotocol.io/) server for authorized OSINT and red team persona lifecycle management. Built on [FastMCP 3.x](https://gofastmcp.com/) with async SQLite persistence.

> **Authorization Required.** This tool is designed for authorized penetration testing, red team engagements, CTF competitions, security research, and defensive OSINT. Do not use it without explicit written authorization from system owners.

---

## What It Does

VeryLegitHuman manages the full lifecycle of synthetic personas for authorized operations:

1. **Generate** a realistic identity (name, DOB, address, occupation, AI-generated face)
2. **Provision** disposable email addresses and phone numbers for account verification
3. **Browse** the web through anti-detect browsers with unique fingerprints
4. **Route** traffic through residential proxies, Tor, or VPN for geolocation consistency
5. **Build** social media presence with scheduled posting across 18+ platforms
6. **Verify** operational security (OpSec) — exit IP matches persona's claimed location

All 54 tools are exposed via MCP and callable from Claude Desktop, Claude Code, or any MCP-compatible client.

---

## Architecture

```
verylegithuman-mcp/
  server.py                    # FastMCP server (54 tools + 2 resources)
  src/
    config.py                  # Centralized config with env var overrides
    database.py                # Async SQLite (aiosqlite) — 7 tables
    security.py                # OWASP hardening (SSRF, validation, redaction, audit)
    verification.py            # OTP/link extraction from emails/SMS
    models.py                  # Pydantic models
    identity/
      generator.py             # Faker/Mimesis identity generation (37+ locales)
      faces.py                 # ThisPersonDoesNotExist AI face generation
      usernames.py             # Sherlock username availability checking
    email/
      mailtm.py                # Mail.tm REST API (free, no auth)
      guerrilla.py             # Guerrilla Mail API (free, session-based)
      mailslurp.py             # MailSlurp SDK (API key, webhook support)
    phone/
      twilio_client.py         # Twilio SDK (provision numbers, receive SMS)
      fivesim.py               # 5sim.net API (cheap verification numbers)
    browser/
      session_manager.py       # Managed browser sessions with persistence
      patchright_engine.py     # Patchright (stealth Chromium)
      camoufox_engine.py       # Camoufox (stealth Firefox)
    opsec/
      proxy_manager.py         # IPRoyal, Bright Data, Decodo, generic proxies
      tor_manager.py           # Stem (daemon) + Torpy (pure Python) dual backend
      mullvad.py               # Mullvad VPN CLI wrapper (Linux)
      geolocation.py           # IPinfo API + MaxMind GeoLite2
    social/
      postiz_client.py         # Postiz REST API (18+ platform scheduling)
      reddit_client.py         # PRAW (Reddit direct posting)
      twikit_client.py         # Twikit (X/Twitter, no API key)
      content.py               # Platform constraints (char limits, rules)
```

---

## Installation

### Prerequisites

- Python 3.11+
- pip

### Quick Start

```bash
# Clone
git clone https://github.com/GetSomeKelso/VeryLegitHuman-MCP.git
cd VeryLegitHuman-MCP/verylegithuman-mcp

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install browser binaries (for stealth browsing)
patchright install chromium
python -m camoufox fetch

# Optional: install Sherlock for username checking
pip install sherlock-project
```

### Run the Server

```bash
python server.py
```

The server communicates via stdio (MCP protocol). Connect it to Claude Desktop or any MCP client.

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "verylegithuman": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\verylegithuman-mcp\\server.py"]
    }
  }
}
```

Linux/macOS:
```json
{
  "mcpServers": {
    "verylegithuman": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/verylegithuman-mcp/server.py"]
    }
  }
}
```

---

## Tools (54)

### Phase 1: Identity (12 tools)

| Tool | Description |
|------|-------------|
| `create_persona` | Generate and persist a new persona identity |
| `get_persona` | Fetch a persona by ID or codename |
| `update_persona` | Update fields on an existing persona |
| `list_personas` | List all personas with optional filters |
| `preview_identity` | Generate identity data without persisting |
| `generate_backstory` | Generate backstory building blocks for a persona |
| `bulk_generate` | Generate multiple identities at once |
| `generate_face` | Fetch an AI-generated face from ThisPersonDoesNotExist |
| `set_persona_face` | Attach a face image to a persona |
| `generate_usernames` | Generate username candidates for a persona |
| `check_username` | Check username availability across 400+ platforms via Sherlock |
| `assign_username` | Save a chosen username to a persona for a platform |

### Phase 2: Email & Phone (10 tools)

| Tool | Description |
|------|-------------|
| `create_email` | Create a temporary email (Mail.tm, Guerrilla Mail, or MailSlurp) |
| `list_email_accounts` | List all provisioned email accounts |
| `check_inbox` | Fetch new messages for an email account |
| `read_email` | Read full email body with auto-extraction of verification codes |
| `extract_verification` | Parse OTP codes and verification links from a message |
| `delete_email_account` | Delete/burn an email account |
| `provision_phone` | Get a phone number (Twilio or 5sim) |
| `list_phone_numbers` | List provisioned phone numbers |
| `check_sms` | Check for received SMS with auto-verification extraction |
| `release_phone` | Release/dispose of a phone number |

### Phase 3: Browser Automation (10 tools)

| Tool | Description |
|------|-------------|
| `launch_browser` | Launch stealth Chromium (Patchright) or Firefox (Camoufox) session |
| `close_browser` | Close a browser session |
| `list_browser_sessions` | List active sessions with URLs and engines |
| `browser_goto` | Navigate to URL (SSRF-protected) |
| `browser_back` | Go back in browser history |
| `browser_click` | Click element by CSS selector |
| `browser_type` | Type text with human-like keystroke delay |
| `browser_select` | Select dropdown option |
| `browser_screenshot` | Capture page screenshot (JPEG + base64) |
| `browser_get_text` | Extract visible text or HTML from page |

### Phase 4: OpSec Infrastructure (12 tools)

| Tool | Description |
|------|-------------|
| `configure_proxy` | Set up proxy (IPRoyal, Bright Data, Decodo, or generic) |
| `rotate_proxy` | Rotate to new IP (new sticky session) |
| `list_proxy_configs` | List all proxy configurations |
| `remove_proxy` | Remove a proxy configuration |
| `test_proxy` | Test proxy connection, return exit IP + geolocation |
| `start_tor` | Start Tor connection (Stem daemon or Torpy pure Python) |
| `tor_new_identity` | Request new Tor circuit (new exit IP) |
| `tor_status` | Check Tor connection status and circuit info |
| `mullvad_connect` | Control Mullvad VPN (Linux only) |
| `verify_ip` | Look up IP geolocation (IPinfo + MaxMind) |
| `verify_persona_opsec` | Comprehensive OpSec check for a persona |
| `check_ip_reputation` | Check if IP is flagged as VPN/proxy/bot |

### Phase 5: Social History (10 tools)

| Tool | Description |
|------|-------------|
| `register_social_account` | Link a social account to a persona |
| `list_social_accounts` | List social accounts |
| `update_social_account` | Update account status or details |
| `get_platform_constraints` | Get posting rules for 10+ platforms |
| `schedule_post` | Schedule a post via Postiz or save as draft |
| `post_now` | Post immediately (Reddit via PRAW, X via Twikit) |
| `list_posts` | List scheduled and posted content |
| `get_activity_summary` | Get posting activity summary |
| `generate_posting_schedule_tool` | Generate realistic posting schedule with human-like jitter |
| `record_engagement` | Record engagement metrics on a post |

---

## Environment Variables

The server works with zero configuration for basic identity generation and free email providers. API keys unlock additional capabilities:

### Free (No Keys Needed)

| Feature | Provider |
|---------|----------|
| Identity generation | Faker/Mimesis (local) |
| AI face generation | ThisPersonDoesNotExist |
| Temp email | Mail.tm, Guerrilla Mail |
| Username checking | Sherlock (if installed) |
| Tor networking | Torpy (pure Python) |
| IP geolocation | IPinfo (50K free/month, no key) |
| Stealth browsing | Patchright (if installed) |

### Optional API Keys

```bash
# Email (MailSlurp — webhook support, custom domains)
export MAILSLURP_API_KEY="your_key"

# Phone (pick one or both)
export TWILIO_ACCOUNT_SID="your_sid"
export TWILIO_AUTH_TOKEN="your_token"
export FIVESIM_API_KEY="your_key"

# Residential Proxies (pick any)
export IPROYAL_API_KEY="your_key"
export BRIGHTDATA_CUSTOMER_ID="your_id"
export BRIGHTDATA_ZONE_PASSWORD="your_password"
export DECODO_USERNAME="your_username"
export DECODO_PASSWORD="your_password"

# Geolocation
export IPINFO_TOKEN="your_token"             # 50K free/month
export MAXMIND_LICENSE_KEY="your_key"        # GeoLite2 DB download

# Tor (if using Stem with daemon)
export TOR_CONTROL_PASSWORD="your_password"

# Social Media
export POSTIZ_API_KEY="your_key"             # 18+ platform scheduling
export REDDIT_CLIENT_ID="your_id"
export REDDIT_CLIENT_SECRET="your_secret"
export TWIKIT_ENABLED="true"                 # Enable X/Twitter via Twikit
```

### Tuning (All Optional)

```bash
export VLH_MAX_SESSIONS=5         # Max concurrent browser sessions (1-20)
export VLH_NAV_TIMEOUT=30000      # Browser navigation timeout in ms
export VLH_TYPE_DELAY=50          # Keystroke delay in ms
export VLH_MAX_EMAILS=50          # Max email accounts
export VLH_MAX_PHONES=20          # Max phone numbers
export VLH_MAX_OUTPUT=50000       # Max text output bytes
export VLH_AUDIT_LOG=true         # Structured audit logging
```

---

## Security (Phase 6: OWASP Hardening)

The server is hardened against the OWASP MCP Top 10 and OWASP LLM Top 10:

| Protection | Implementation |
|------------|----------------|
| **SSRF Blocking** | `file://`, `javascript:`, `data:` schemes blocked. Internal IPs (127.x, 10.x, 172.16-31.x, 192.168.x) blocked. |
| **Input Validation** | UUID format validation, CSS selector injection prevention, string length limits, enum enforcement |
| **Output Sanitization** | Passwords/tokens masked in responses, `<script>` tags stripped from email HTML, large outputs truncated (50KB) |
| **Audit Logging** | Structured JSON logs for every tool call (call ID, tool name, arg keys only — never values) |
| **Rate Limiting** | Per-provider sliding window: Mail.tm 8/s, Guerrilla 4/s, browser launches 1/5s, Postiz 30/hr |
| **Resource Limits** | Max browser sessions, email accounts, phone numbers all configurable and clamped |

---

## Database

SQLite with WAL mode, 7 tables:

- `personas` — identity records with nested address, usernames, metadata
- `persona_notes` — freeform notes per persona
- `email_accounts` — provisioned email addresses with provider credentials
- `email_messages` — received email messages (cached)
- `phone_numbers` — provisioned phone numbers
- `sms_messages` — received SMS messages
- `social_accounts` — linked social media accounts
- `social_posts` — scheduled/posted content with engagement tracking
- `proxy_configs` — proxy configurations per persona

Data persists in `data/db/verylegithuman.db` across server restarts.

---

## Burp Suite MCP Integration

VeryLegitHuman is designed to work alongside [Burp Suite's MCP server](https://portswigger.net/burp/documentation/desktop/extensions/mcp) when both are connected to the same Claude session. VeryLegitHuman acts, Burp observes — the combination provides full visibility into what happens at the HTTP layer during persona operations.

### What This Enables

| Scenario | VeryLegitHuman Role | Burp Suite Role |
|----------|-------------------|-----------------|
| **Account Registration** | Generates persona, provisions email, drives stealth browser through signup flow | Captures every HTTP request — reveals fingerprinting, bot detection, hidden tracking |
| **Anti-Detect Verification** | Launches Patchright (Chromium) and Camoufox (Firefox) against fingerprint test sites | Inspects outbound headers for TLS/User-Agent inconsistencies between browser-reported and HTTP-level identity |
| **Proxy Chain Validation** | Configures residential proxy or Tor, routes browser through it | Confirms no IP or DNS leaks in actual HTTP traffic, checks for X-Forwarded-For / Via header leakage |
| **Target Recon** | Loads target site in stealth browser, checks for CAPTCHAs and challenge pages | Probes response headers (Server, CSP, Set-Cookie), identifies WAF vendor (Cloudflare, DataDome, Akamai, Kasada) |
| **Verification Interception** | Handles email/SMS OTP flow end-to-end | Captures the OTP submission request for rate limit analysis, saves to Repeater for replay testing |

### Setup

Run both MCP servers in your Claude Desktop config:

```json
{
  "mcpServers": {
    "verylegithuman": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/verylegithuman-mcp/server.py"]
    },
    "burp": {
      "command": "...",
      "args": ["..."]
    }
  }
}
```

When both are active, Claude automatically chains them — VeryLegitHuman tools drive the action, Burp tools (`get_proxy_http_history`, `get_proxy_http_history_regex`, `create_repeater_tab`, `send_http1_request`, `get_scanner_issues`) analyze the resulting traffic. The operational playbooks are defined in `CLAUDE.md` and Claude follows them when tasks match.

### Example: Stealth Registration with Traffic Analysis

```
You: Register azure-falcon-37 on example.com and tell me what they're tracking

Claude: [VLH: create_email, configure_proxy, launch_browser]
        Email provisioned, proxy set to Austin TX, Patchright session started.

        [VLH: browser_goto → example.com/signup]
        [VLH: browser_type, browser_click → fills form, submits]

        [Burp: get_proxy_http_history_regex("signup|register")]
        Captured 4 requests during registration:
        - POST /api/register — sends device_id hash, screen resolution, timezone
        - GET /cdn-cgi/challenge-platform — Cloudflare bot check
        - POST /api/fingerprint — canvas hash, WebGL renderer, audio context

        [VLH: check_inbox, extract_verification]
        OTP received: 847291

        [VLH: browser_type → enters OTP]
        [Burp: get_proxy_http_history_regex("verify|otp")]
        OTP submission POST has no rate limiting header. Token is single-use.

        Summary: Target uses Cloudflare + custom fingerprinting. Registration
        collects device_id, canvas hash, and timezone. No rate limit on OTP endpoint.
```

---

## Example Workflow (Standalone)

```
You: Create a persona for a 28-year-old female software engineer in Austin, TX

Claude: [calls create_persona] Created: Sarah Mitchell (codename: azure-falcon-37)

You: Generate a face and check if "sarahmitchdev" is available on Twitter and GitHub

Claude: [calls generate_face, check_username] Face saved. Username available on both.

You: Set up a temporary email and register this persona on Twitter using the browser

Claude: [calls create_email, launch_browser, browser_goto, browser_type, browser_click...]
        Email: s4r9hmit@sharebot.net | Navigating to twitter.com/signup...

You: Set up a proxy so her traffic looks like it's from Austin

Claude: [calls configure_proxy, verify_persona_opsec]
        IPRoyal proxy configured. OpSec check: 3/4 passed (country match: US)

You: Schedule some tweets for the next week to build history

Claude: [calls generate_posting_schedule_tool, schedule_post x5]
        5 posts scheduled: Mon 12:47pm, Tue 6:22pm, Thu 9:15am, Sat 2:03pm, Sun 7:38pm
```

---

## License

For authorized security testing, defensive security, CTF challenges, and educational use only.

---

## Credits

Built with [Claude Code](https://claude.ai/code) (Opus 4.6).
