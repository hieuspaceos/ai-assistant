---
name: seo-meta
description: Edit SEO meta (title, description, image alt) of WordPress posts via REST API — supports Yoast and RankMath. Single post or bulk via a list.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Edit SEO meta of WordPress posts via REST — work that normally means
opening each post in wp-admin by hand. Connection check is the same as
`/publish-post` (app `wordpress` in `connections.json`, credentials in
`.devin/secrets.local.json`).

## Detect the SEO plugin first

| Plugin | Meta keys |
|---|---|
| Yoast | `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` |
| RankMath | `rank_math_title`, `rank_math_description` |

Detect via `GET {base}/wp-json/wp/v2/posts/{id}` → check which key exists
in `meta`. **Note**: meta fields are REST-accessible only when the plugin
registered them with `show_in_rest: true` — Yoast/RankMath do by default.
If `meta` comes back empty → tell the learner the site needs REST meta
enabled (newer plugin / config), don't guess.

## Edit one post

1. Ask: which post (id/slug/link), which fields (title/description/both/
   image alt), what's the new text — or should you draft suggestions from
   the post content.
2. `GET {base}/wp-json/wp/v2/posts/{id}` → read current title + meta.
3. Show the proposed edits first (new title, new description) — write
   only after agreement.
4. `POST {base}/wp-json/wp/v2/posts/{id}` —
   `{"meta": {"_yoast_wpseo_title": "...", "_yoast_wpseo_metadesc": "..."}}`.
5. Re-read the post to confirm meta was written → report.

## Bulk edit

1. List posts: `GET {base}/wp-json/wp/v2/posts?per_page=100&page=N`
   until done (header `X-WP-TotalPages`).
2. Show a SUMMARY table: id, title, meta present/empty — not full content.
3. Ask the rule: "fill missing descriptions from the first 160 chars" /
   "edit per my list (file)".
4. Run post by post, report progress tersely (e.g. "12/47 done"),
   collect errors at the end.
5. **Image alt**: `POST /wp-json/wp/v2/media/{id}` `{"alt_text": "..."}`
   — for featured/in-content images.

## Safety rules

- Editing meta changes real site content — always show the edit list +
  new values first; bulk write only on agreement.
- Don't touch fields outside SEO meta (content, slug, publish date)
  unless explicitly asked.
