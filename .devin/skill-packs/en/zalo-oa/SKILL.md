---
name: zalo-oa
description: Send messages via Zalo Official Account (OA) official API — broadcasts to followers, customer-service messages. Requires the OA access token; NEVER send without confirmation.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Zalo OA (`openapi.zalo.me`) is the official API for business accounts —
more durable than Zalo Web automation. Requires an **access token**.

## Setup (once, assistant guides)

1. Quick path for learners: open ⚙ **Settings** → the **Set up** button
   next to Zalo OA → paste the access token → **Save & check** (writes to
   `.devin/secrets.local.json`). If full `oa_id`/`refresh_token` is needed
   for auto-renewal, write the file by hand as below.
2. Learner logs into `oa.zalo.me` → picks the OA → **Settings → OA info**
   → get `oa_id`; **Developer tools / API** → create an access token (or
   the OAuth flow at `oauth.zaloapp.com`).
3. Write into `.devin/secrets.local.json` (gitignored):
   `{"zalo-oa": {"oa_id": "...", "access_token": "...", "refresh_token": "..."}}`
   — OA tokens expire (~1 day access / 3 months refresh) → keep the
   refresh_token for auto-renewal.
4. **Never** paste the token into chat/manifest/terminal.

## Check the token is alive

`GET https://openapi.zalo.me/v2.0/oa/getoa` with header `access_token` →
`error: 0`. Expired → `POST /v4/oa/access_token` with refresh_token +
app_id/secret (if present) → write the new token back to
secrets.local.json.

## Sending

1. **Follower list**: `GET /v2.0/oa/getfollowers` (paged `offset`/`count`).
2. **1-1 CS message**: `POST /v3.0/oa/message/cs` —
   `{"recipient":{"user_id":"<uid>"},"message":{"text":"..."}}`.
3. **Broadcast**: `POST /v2.0/oa/message` (quota depends on the OA plan —
   tell them the limit first).

## Safety rules — stricter than usual

- **Sending to other people = public action.** Always show content +
  recipient list + count first, and ask: *"I'm about to send this to N
  OA followers — OK?"*
- Broadcasts are quota-limited and policy-bound — no test-spamming the
  company's real OA.
- Leaked token → revoke in oa.zalo.me immediately and mint a new one.
