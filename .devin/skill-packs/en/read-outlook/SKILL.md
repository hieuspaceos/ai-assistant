---
name: read-outlook
description: Read Outlook Web (outlook.office.com) in the learner's real browser — list unread mail, read message content, download attachments. NEVER send/reply without asking.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Read Outlook Web via the AI Assistant extension — same API as
`/open-web`, same pattern as `/read-zalo`. The learner is already logged
in on their browser.

## Setup

1. `curl -s http://localhost:7684/api/browser/status` → `connected: true`.
2. `{"action":"tabs"}` → find the `outlook.office.com` /
   `outlook.live.com` tab; `open` the URL if absent.
3. Login page → ask the learner to log in by hand, wait for them.

## List unread mail

1. `snapshot` → find the filter/Unread control (Outlook has a "Filter"
   button above the message list → "Unread"). Text-click if no ref.
2. `query` the message list region (try `div[role=option]`,
   `[class*=mailList]`, `[aria-label*=message]`).
3. Scroll the list region (`scrollables` → left pane) to load more.
4. Report sender + subject + time — do NOT read content unasked.

## Read a message

1. `click` by text (subject/sender) → opens in the reading pane.
2. `query`/`read` the body region (`[aria-label*=message body]` or the
   right pane) → summarize for the learner.
3. Attachments: filename + Download button → `click` so the browser saves
   to Downloads; tell them.

## Compose / reply

Composing is fine: `click` "New mail" or "Reply" → `type` into To/CC/body.
**Hard rule**: before clicking Send, ask: *"I'm about to send this to
<recipient>, OK?"* — click only on agreement.

## Rules

- Don't read mail beyond what was asked; don't delete/move mail without
  asking.
- Outlook renames classes often → if selectors return nothing,
  `screenshot` then probe with broader `scrollables`/`query`; tell them
  "Outlook just changed its layout, I'm re-locating".
- Security mails (password reset, OTP links): summarize only, never
  click links for them.
