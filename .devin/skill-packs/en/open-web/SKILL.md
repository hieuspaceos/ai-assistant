---
name: open-web
description: Drive the learner's REAL browser through the "AI Assistant" extension — open pages, read content, click, type, take screenshots. Use when the task lives on a website the learner is already logged into (Zalo Web, Outlook web, WordPress admin, or any page).
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

AI Assistant has an "arm" inside the learner's browser: an installed
extension that talks to this machine over `http://localhost:7684`. Use it
whenever the work is on a web page — especially pages the learner is
ALREADY logged into (Zalo, Outlook, wp-admin...), since this browser
keeps their sessions.

## Check before use (mandatory)

```
curl -s http://localhost:7684/api/browser/status
# or PowerShell: Invoke-RestMethod http://localhost:7684/api/browser/status
```

- `{"connected": true}` → good to go.
- `{"connected": false}` → STOP, tell the learner in plain words: *"I
  need the AI Assistant button in your browser to help with this. Open
  Chrome (or Edge) — if you see a green graduation-cap icon in the top
  right, we're set. If not, I'll walk you through installing it — takes
  about 2 minutes."* Then follow "Install the extension" in SETUP.md.
  Never silently skip this and improvise another way.

## Issuing commands

Every command is a JSON POST to `http://localhost:7684/api/browser`:

```
curl -s -X POST http://localhost:7684/api/browser -d '{"action":"<action>", ...}'
# PowerShell:
# Invoke-RestMethod -Method Post http://localhost:7684/api/browser `
#   -Body '{"action":"tabs"}' -ContentType 'application/json'
```

| Action | Params | What it does |
|---|---|---|
| `tabs` | — | List the learner's open tabs (id, title, url) |
| `open` | `url` | Open a new tab, returns `tabId` |
| `activate` | `tabId` | Switch to a tab |
| `close` | `tabId` | Close a tab (ask the learner first if it's theirs) |
| `snapshot` | `tabId?` | Read the "element tree" — every button/field gets a ref `e1`, `e2`... |
| `click` | `tabId?`, `ref` or `text` | Click an element by ref, or by visible text (for div-heavy sites like Zalo/FB) |
| `type` | `tabId?`, `ref`/`sel`, `text` | Type into a field (clears existing text first) |
| `key` | `tabId?`, `ref`/`sel`, `key` | Send Enter/Tab/Escape/Delete/arrows — works on normal inputs; Sheets' canvas grid ignores it |
| `paste` | `tabId?`, `sel?`, `text` | Paste text/TSV like a real paste — only apps accepting synthetic events; Sheets grid does NOT |
| `scroll` | `tabId?`, `dy`, `sel?` | Scroll page by `dy` px; with `sel` scrolls that region (chat pane, table). Negative `dy` scrolls up. Returns `atTop`/`atBottom` |
| `scrollables` | `tabId?` | List scrollable regions → refs `s1`, `s2`... use with `scroll` `sel=sN` |
| `query` | `tabId?`, `sel`, `attr?` | Get text of every element matching a CSS selector; with `attr` get attributes (src, href) |
| `read` | `tabId?`, `sel?` | Get readable page text (or one region), filtered, max ~8000 chars |
| `fetch` | `tabId?`, `url` | Fetch a URL using the tab's logged-in session (same origin) — reads private pages/files, e.g. Google Sheets CSV via `gviz/tq?tqx=out:csv` |
| `screenshot` | `tabId?` | Capture the tab → returns `file` (PNG path to read back) |
| `wait` | `tabId?`, `ms` | Wait for the page (max 5s per call) |
| `reload` | — | Reload the extension after code edits — reconnects itself |
| `tclick` | `tabId?`, `sel`/`ref` or `x`,`y` | **REAL mouse click** (via CDP) — for apps ignoring synthetic clicks (Zalo, FB, picky editors). Brings the tab forward |
| `tright` | same as `tclick` | **REAL right-click** — opens the app's context menu |
| `tmove` | same as `tclick` | **REAL hover** — reveals buttons/menus that only show on hover |
| `ttype` | `tabId?`, `sel`/`ref`, `text` | **REAL typing** — real-clicks the field then inserts text. The only way into Zalo's editor (`#richInput`) |
| `tinsert` | `tabId?`, `text`, `mode?` | Real text at the current caret; `mode=char` fires per-char keys — writes into the Google Sheets grid |
| `tkey` | `tabId?`, `sel`/`ref`?, `key`, `modifiers?` | **REAL key press** (Enter, arrows...); `modifiers` bitmask 4=Cmd/Ctrl |
| `tdetach` | `tabId?` | Dismiss the "debugging" banner after `t*` actions |

Omit `tabId` to act on the tab the learner is looking at.

## Standard rhythm

1. `tabs` to see what's open, or `open` the page you need.
2. Short `wait` → `snapshot` for element refs.
3. `click`/`type` by ref → `wait` → `snapshot` again (refs CHANGE after
   every page change — never reuse refs from an older snapshot).
4. Stuck → `screenshot` and read the image to see what the page looks like.
5. Report back to the learner in plain words — never paste raw JSON.

## Safety rules — do not break

- **Sending** = anything with outside consequences: sending Zalo
  messages, emails, publishing posts, deleting content. BEFORE clicking
  Send/Publish/Delete, ask the learner: *"I'm about to hit Send — this
  will really go out. OK?"* Only click after they agree.
- Never `type` into a `password` field, never read password fields. If
  a page demands login/captcha/2FA: stop, ask the learner to do it by
  hand, wait for them to say it's done.
- The learner shares this browser — don't `close` their tabs without
  asking; open new tabs for your own work.
- System pages (`chrome://`, Web Store) block extensions — if a command
  errors about that, explain it and reroute (open a different page).
