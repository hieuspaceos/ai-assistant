---
name: new-page
description: Add a new detail page (blog post, tour, product…) to a cloned site — duplicate the data-cs-template page, fill it with the learner's content, and auto-add its card on the listing page. Use when the learner wants to "write another post", "add a tour", "add a product" to their cloned site.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - write
  - ask_user_question
---

A cloned site (built by `/clone-page`) already carries a detail-page
"mold" — `<div data-cs-page="/blog/<slug>" data-cs-template="post">`.
This skill duplicates that mold into a new page holding the learner's
content. Tell them like this: *"the template is already there — I just
duplicate it and swap in your words"*. All operations are reading/
writing `.html` files — use python via exec for precision.

## Steps

### 1. Ask enough — never guess

Ask (batch it in one go, use ask_user_question when possible):

- **Which site**: scan every `my-course/*.html`, count files having
  `data-cs-template`. Only 1 file → use it, no need to ask. MULTIPLE
  files (learner cloned several sites) → **must ask** "add to which
  site?" with the site names — never guess, wrong site means breaking
  the other site's file. If their request already names the site,
  match by name and skip asking. No file has a template → say so
  plainly, suggest cloning again with `/clone-page` (new standard).
- **Page kind**: open the file first, list existing `data-cs-template`
  values (`post`, `tour`, `product`, `recipe`… — open vocabulary,
  site-dependent). Multiple kinds → ask which they want; the kind they
  need isn't there → say so and suggest cloning a sample page of that
  kind first.
- **Title** of the new page → derive a slug: lowercase, no accents,
  joined with `-` (strip Vietnamese accents, unusual chars → `-`).
  Have them confirm the slug.
- **Main content**: short description (excerpt), body (a few
  paragraphs), image (link or a file in `my-course/` — they can send
  it later, use a placeholder meanwhile).

### 2. Duplicate the template

- Read the clone file. Find `<div data-cs-page="…" data-cs-template="KIND">`.
  Not found → tell the learner this file wasn't cloned to the new
  standard, suggest re-cloning or hand-duplicating the closest page.
- Copy that whole `<div data-cs-page>` block (to its matching
  `</div>` — count nested divs if needed), **remove `data-cs-template`**,
  change `data-cs-page` to `<route-prefix>/<slug>` — the prefix is the
  parent route of the template page (`/about/x` → `/about`).
- Insert the new block right AFTER the template block (before the next
  page starts).

### 3. Fill content into the new block

Inside the NEW block only (never touch the template):

- `data-cs-text` on `h1/h2/h3` → new title; on first `p` → excerpt;
  body `p`s → the body text.
- `data-cs-img` / `.media` caption blocks → new image + caption (no
  image yet → keep the placeholder and remind them to swap it).
- Date (`.tac-card-body .tac-small` or equivalent) → today.
- Any text unmappable via markers → edit the text node directly inside
  the new block, keep classes/styles intact.

### 4. Add the card on the listing page

- Find the `data-cs-page` of the parent route (the prefix). Inside its
  listing grid, copy the first `<a class="card…">` (or
  `tac-card--link`).
- Edit the copy: `href` → `#<new data-cs-page>` (same link format as
  the site: `#/route/slug`), caption/title → the title, date → today,
  excerpt → the short description.
- Insert the card FIRST in the grid (newest on top), unless the learner
  says otherwise.

### 5. Static verification BEFORE delivering

After inserting, check by script right away — don't trust your eyes:

- Count `data-cs-template="<kind>"` in the file → must equal the OLD
  count (the new page must not carry the marker).
- `data-cs-page="<new-route>"` exists exactly once.
- The first card of the parent grid points at the new route (unless
  they asked for a different spot).
- The new route fits the router: inside `<main>`, has `hidden`
  initially if it isn't the default page.

### 6. Deliver

- Open the viewer:
  `http://localhost:8080/web/clone-view.html?src=/my-course/<file>.html`
  → click the new route in the menu (or type the hash `#/route/slug`)
  → see the new page rendered in the right frame.
- Report briefly: *"done — your new post has its own page and a card
  on the News page. Click Edit content to keep tweaking."*

## Limits

- Never touch `data-cs-template` of the template page — lose the mold
  and there's nothing left to duplicate next time.
- Site-specific forms/routes (e.g. a tour-booking form with dates and
  prices) → clone the template's form block as-is and ask the learner
  for the content.
