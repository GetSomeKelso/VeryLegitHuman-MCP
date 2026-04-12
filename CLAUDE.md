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
- 60 tools across 6 phases, OWASP-hardened
- `server.py` → SecurityMiddleware (intercepts ALL tool calls) → tool definitions → service modules
- `src/database.py` — async aiosqlite for persona/email/phone/proxy/social persistence (9 tables)
- `src/security.py` — SecurityMiddleware + input validation, SSRF blocking, output sanitization, audit logging, rate limiting
- All sync SDKs (Twilio, PRAW, MailSlurp, Stem) wrapped in `asyncio.to_thread()` to prevent event loop blocking

## Phases
- Phase 1: Identity generation + persistence (12 tools)
- Phase 2: Email/phone provisioning (10 tools)
- Phase 3: Stealth browser automation — Patchright (Chromium) + Camoufox (Firefox) (13 tools, incl. execute_js, cookies, wait_for)
- Phase 4: OpSec infrastructure — proxies, Tor, Mullvad VPN, geolocation (12 tools)
- Phase 5: Social history building — Postiz, Reddit/PRAW, X/Twikit (10 tools)
- Phase 6: OWASP MCP Top 10 + LLM Top 10 audit & hardening (+3 utility tools: delete_persona, add_persona_note, cancel_post)

## Common Pitfalls
- Use `python` (not `python3`) on Windows
- Env var prefix is `VLH_` (e.g., `VLH_MAX_SESSIONS`, `VLH_NAV_TIMEOUT`)
- DB file: `data/db/verylegithuman.db`
- Sherlock must be installed separately (`pip install sherlock-project`)
- Patchright needs `patchright install chromium` after pip install
- Camoufox needs `python -m camoufox fetch` after pip install

---

## Combined Operations Playbooks (VeryLegitHuman + Burp Suite MCP)

When Burp Suite MCP tools (`mcp__burp__*`) are available in the same session, use these playbooks to chain both toolsets for maximum operational insight. **Always follow these playbooks when the user's task matches the trigger.**

### Playbook 1: Stealth Registration Audit
**Trigger:** User asks to register a persona on a website, create an account, or sign up anywhere.

**Steps:**
1. **VLH:** `create_persona` → generate identity
2. **VLH:** `create_email` → provision verification email
3. **VLH:** `configure_proxy` → set up geo-appropriate proxy
4. **Burp:** `set_proxy_intercept_state(intercepting=false)` → ensure Burp proxy is passing traffic (not blocking)
5. **VLH:** `launch_browser` → start stealth browser (route through Burp if configured as upstream proxy)
6. **VLH:** `browser_goto` → navigate to registration page
7. **Burp:** `get_proxy_http_history_regex(regex="signup|register|create.*account", count=20, offset=0)` → capture registration-related requests as they happen
8. **VLH:** `browser_type`, `browser_click` → fill and submit registration form
9. **VLH:** `check_inbox` → get verification email
10. **VLH:** `extract_verification` → parse OTP/link
11. **Burp:** `get_proxy_http_history_regex(regex="verify|confirm|token|otp", count=10, offset=0)` → capture the verification POST to check for hidden fingerprinting
12. **Report:** Summarize what the target site collects during registration (headers, cookies, fingerprint data, bot detection signals)

### Playbook 2: Anti-Detect Effectiveness Test
**Trigger:** User asks to test if the stealth browser is actually undetectable, check browser fingerprint, or verify anti-detect is working.

**Steps:**
1. **VLH:** `launch_browser(engine="patchright")` → start Chromium stealth session
2. **VLH:** `browser_goto(url="https://browserleaks.com/canvas")` or similar fingerprint test site
3. **VLH:** `browser_screenshot` → capture visual fingerprint results
4. **VLH:** `browser_get_text` → extract fingerprint data from page
5. **Burp:** `get_proxy_http_history(count=20, offset=0)` → inspect outbound headers (User-Agent, Accept-Language, TLS fingerprint)
6. **Burp:** `get_proxy_http_history_regex(regex="fingerprint|canvas|webgl|audio", count=10, offset=0)` → look for fingerprint collection endpoints
7. **Compare:** Check if browser-reported fingerprint matches HTTP-level headers. Flag inconsistencies (e.g., User-Agent says Chrome but TLS fingerprint says Firefox).
8. **Repeat** with `engine="camoufox"` for Firefox comparison.

### Playbook 3: Proxy Chain Validation
**Trigger:** User asks to verify proxy is working, check for IP leaks, or validate the proxy chain.

**Steps:**
1. **VLH:** `configure_proxy` → set up proxy for persona
2. **VLH:** `test_proxy` → verify exit IP + geolocation
3. **VLH:** `launch_browser` with the proxy → start browsing session
4. **VLH:** `browser_goto(url="https://httpbin.org/ip")` → check IP from browser's perspective
5. **Burp:** `get_proxy_http_history_regex(regex="httpbin", count=5, offset=0)` → inspect the actual HTTP request to confirm proxy was used (check X-Forwarded-For, Via headers)
6. **Burp:** `get_proxy_http_history_regex(regex="dns|leak", count=10, offset=0)` → check for DNS leak indicators
7. **VLH:** `verify_ip` on the exit IP → confirm geolocation matches persona's claimed location
8. **VLH:** `verify_persona_opsec` → run full OpSec checklist
9. **Report:** Pass/fail on: correct exit IP, no DNS leaks, no header leaks, geo matches persona

### Playbook 4: Target Reconnaissance Before Engagement
**Trigger:** User asks to register on a specific site, or wants to understand what protections a target has before engaging.

**Steps:**
1. **Burp:** `send_http1_request` → send a bare GET to the target site, inspect response headers (Server, X-Powered-By, CSP, Set-Cookie flags)
2. **Burp:** `get_scanner_issues(count=20, offset=0)` → check if Burp has scanned the target for known vulnerabilities
3. **VLH:** `launch_browser` → load the site in stealth browser
4. **VLH:** `browser_get_text` → extract page content, look for CAPTCHA, bot detection scripts
5. **VLH:** `browser_screenshot` → visual inspection of any challenges (hCaptcha, reCAPTCHA, Cloudflare interstitial)
6. **Burp:** `get_proxy_http_history_regex(regex="captcha|challenge|cloudflare|datadome|kasada|akamai", count=20, offset=0)` → identify which bot detection vendor is active
7. **Decision:** Based on findings, choose:
   - Cloudflare → Patchright (Chromium) is best
   - DataDome → Camoufox (Firefox) may work better
   - hCaptcha → may need manual intervention
   - No detection → either engine works

### Playbook 5: Verification Flow Interception
**Trigger:** User is doing email/SMS verification as part of account creation.

**Steps:**
1. **VLH:** `create_email` or `provision_phone` → get verification channel
2. **VLH:** Browser submits the form requesting verification
3. **Burp:** `get_proxy_http_history_regex(regex="verify|otp|sms|code|confirm", count=10, offset=0)` → capture the verification request
4. **Burp:** `create_repeater_tab` with the verification request → save for replay testing
5. **VLH:** `check_inbox` or `check_sms` → receive the code
6. **VLH:** `extract_verification` → parse the OTP
7. **VLH:** Browser submits the OTP
8. **Burp:** `get_proxy_http_history(count=5, offset=0)` → capture the OTP submission request
9. **Analyze:** Check if OTP endpoint has rate limiting, if tokens are reusable, if there's timing-based detection

### General Rules for Combined Operations
- **Burp as observer, VLH as actor.** VLH tools create personas, provision resources, and drive the browser. Burp tools inspect, capture, and analyze the HTTP traffic that results.
- **Always check Burp history after browser actions.** Every `browser_goto`, `browser_click`, or `browser_type` that triggers a network request should be followed by a `get_proxy_http_history` or `get_proxy_http_history_regex` call if the user wants traffic analysis.
- **Use Burp Repeater for replay.** When an interesting request is found (registration POST, OTP submission, etc.), use `create_repeater_tab` to save it for manual replay and parameter manipulation.
- **Never log sensitive data from Burp.** Burp captures raw credentials, tokens, cookies. Do NOT echo these back to the user in full. Summarize findings (e.g., "The registration POST sends 12 headers including a device fingerprint hash") without reproducing sensitive values.
