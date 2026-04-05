# VeryLegitHuman MCP Server

## Project Structure
- Windows project: `C:\Users\kelso\OneDrive\Desktop\VeryLegitHuman MCP\verylegithuman-mcp\`
- Key files: `server.py`, `src/database.py`, `src/models.py`, `src/config.py`
- Identity: `src/identity/generator.py`, `src/identity/faces.py`, `src/identity/usernames.py`
- Email/Phone: `src/email/mailtm.py`, `src/email/guerrilla.py`, `src/email/mailslurp.py`, `src/phone/twilio_client.py`, `src/phone/fivesim.py`
- Browser: `src/browser/session_manager.py`, `src/browser/patchright_engine.py`, `src/browser/camoufox_engine.py`
- OpSec: `src/opsec/proxy_manager.py`, `src/opsec/tor_manager.py`, `src/opsec/mullvad.py`, `src/opsec/geolocation.py`
- Social: `src/social/postiz_client.py`, `src/social/reddit_client.py`, `src/social/twikit_client.py`, `src/social/content.py`
- Security: `src/security.py`, `src/verification.py`

## Architecture
- FastMCP 3.x server (stdio protocol, local Python)
- 54 tools across 6 phases, OWASP-hardened
- `server.py` → tool definitions (decorated functions) → service modules
- `src/database.py` — async aiosqlite for persona/email/phone/proxy/social persistence
- `src/security.py` — input validation, SSRF blocking, output sanitization, audit logging, rate limiting

## Phases
- Phase 1: Identity generation + persistence (12 tools)
- Phase 2: Email/phone provisioning (10 tools)
- Phase 3: Stealth browser automation — Patchright (Chromium) + Camoufox (Firefox) (10 tools)
- Phase 4: OpSec infrastructure — proxies, Tor, Mullvad VPN, geolocation (12 tools)
- Phase 5: Social history building — Postiz, Reddit/PRAW, X/Twikit (10 tools)
- Phase 6: OWASP MCP Top 10 + LLM Top 10 audit & hardening (0 new tools)

## Common Pitfalls
- Use `python` (not `python3`) on Windows
- Env var prefix is `VLH_` (e.g., `VLH_MAX_SESSIONS`, `VLH_NAV_TIMEOUT`)
- DB file: `data/db/verylegithuman.db`
- Sherlock must be installed separately (`pip install sherlock-project`)
- Patchright needs `patchright install chromium` after pip install
- Camoufox needs `python -m camoufox fetch` after pip install
