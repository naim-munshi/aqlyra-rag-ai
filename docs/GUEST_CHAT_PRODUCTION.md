# Aqlyra Guest Chat — Production Rollout and Privacy

**Status:** code ready for release validation; **feature OFF by default** until signed edge-to-backend routing, quotas, and public-host deployment acceptance are complete. Do not confuse a Vercel frontend deployment with an active Render guest backend.

## User experience

- At `/login`, **Continue without login · Limited AI chat** opens `/guest` on the *same original Aqlyra app*.
- Guest can ask general AI questions, use at most 4 short local conversational turns as context, and receives a non-streaming response.
- Guest cannot upload any file, use authenticated private RAG/retrieval, projects, database history, memory, voice, artifact workspace, or private Study Abroad cases. Clicking the paperclip directs to `/register`.
- No account is created, no chat is persisted in Aqlyra/PostgreSQL, and no browser localStorage persistence exists. The upstream model provider may process the message under its own data handling terms.
- Guest session limit: **5 questions/IP/hour, 20/IP/day and 1,000 global/day** (all Redis-enforced, configurable). Message ≤800 characters, max 4 history messages (user ≤800 characters; AI reply ≤2,000 characters), and no persistence.
- The guest UI prominently discloses: public IP and request count visible only to authorized admins for a fixed maximum 24-hour lifetime per record; no guest message text stored in the IP audit.

## Architecture and security boundary

1. Browser → Vercel same-origin `POST /api/guest/chat` or `POST /api/guest/visit`.
2. Vercel overwrites `x-forwarded-for` at ingress (see https://vercel.com/docs/headers/request-headers). Node.js API accepts a valid normalized IP only when `VERCEL=1`; a browser-supplied `X-Aqlyra-Guest-IP` is never trusted.
3. Vercel signs timestamp, exact body SHA-256 and IP using a shared 32+ character secret `GUEST_PROXY_SECRET`. It forwards the request to the existing **Render** backend `/api/v1/guest/{chat,visit}`.
4. Render verifies signature and ±60s timestamp *before* consuming an LLM quota or logging visitor IP. Direct calls to Render lacking the secret fail 403. The secret never goes to browser JavaScript.
5. Existing Redis Lua `INCR/EXPIRE` limiter enforces per-IP hourly/daily and global cost ceilings and **fails closed** when Redis is down. The guest endpoint never accepts a JWT substitute to access authenticated private functions.
6. Anonymous chat calls `create_configured_llm_provider()` with a restricted guest-only instruction and the supplied short public context. No database session and no document retrieval function is imported into this public endpoint.
7. Redis stores the public IP, last access and separate visit/chat-request counters under an HMAC-keyed record. A conditional `EXPIRE NX` sets a fixed TTL of 86,400s when the record is first created, never extended by new traffic. No prompts, emails, documents, auth tokens or user records are saved. Only `/api/v1/admin/guest-traffic` under the existing **verified UUID allowlisted admin** gate returns at most 100 most-recent records. Anonymous visitors cannot access it. In-product monitoring lets admin inspect the list on demand. The UI states this visibility and expiry.

## Production gates

- Keep **GUEST_CHAT_ENABLED=false** until the existing Render service is updated to the **Full Release branch** and tested with real Redis + LLM provider.
- Frontend **NEXT_PUBLIC_AQLYRA_GUEST_ENABLED=false** by default: hides the login CTA and redirects direct /guest visits to /login. Change this to `true` only after real backend Guest API is accepted, and redeploy the existing Vercel production project. This prevents a visible dead-end guest experience when Render is still core-only.
- Add identical, randomly generated private **GUEST_PROXY_SECRET** in existing Render and Vercel project secrets; never write it to GitHub, never put `NEXT_PUBLIC_` on it. The backend must have `RATE_LIMIT_ENABLED=true`. Deploy *the same signed release* to both services.
- Verify public guest requests cannot bypass the original Vercel Authentication protection. **Vercel currently has SSO protection on all deployments**, so guest browsing will require changing deployment protection to cover only previews, not disabling security on every deployment; verify authenticated private routes still require JWT and admin remains inaccessible. This is a separate manual product launch decision. See https://vercel.com/docs/deployment-protection.
- QA: normal guest chat, timeouts, simulated provider errors, 429/503, XFF spoof attempts, direct Render calls, no authenticated files accessible, admin 401/403, 24h IP expiry, multi-instance Redis quota, and iPhone mobile layout.
- Public-launch privacy notice must reflect 24h IP retention and third-party model processing. Do not claim IP is a verified identity or unique human: NAT/VPN and shared networks may share an IP.
- The existing PR remains draft and main unchanged until cutover/acceptance. No production migrations are required for this feature.
