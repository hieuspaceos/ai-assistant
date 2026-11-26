---
name: clone-page
description: Rebuild a web page EXACTLY like the reference page — layout, colors, fonts, spacing, icons — measured live on the real page running in the learner's browser, never eyeballed from a screenshot. Content (text, images, brand logo) is replaced with the learner's own. Output is a single .html file they can open right away.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - write
  - webfetch
  - ask_user_question
---

A learner who does NOT code sees a beautiful website and wants "one just
like it but mine". The essence of a good clone: **measure on the live
page** — DOM, computed styles, fonts, assets — not guess from a
screenshot. The learner's real browser (the AI Assistant extension, see
`/open-web`) is the best measuring tool: the page is fully rendered and
already logged in when needed.

## Copyright rules — say them plainly, don't dodge

- DO clone faithfully: layout, colors, fonts, spacing, corner radius,
  shadows, section structure, icon style, visible effects.
- DO NOT carry over: verbatim copy, images, logos, brand names. Result
  text and images are the learner's (or newly written / placeholders).
  Temporary exception: keeping source text FOR TECHNICAL COMPARISON
  during the diff phase (step 4) is fine — but before delivery, replace
  it with the learner's content or placeholders, and clearly say which
  parts are still sample text.
- Technical icons (arrows, checks, cart, social) → reusing inline SVG
  extracted from the source page is OK (system icons), except icons
  carrying a brand logo.
- In plain words: *"I'll rebuild the page so it looks exactly the same
  in frame and style — but the words, photos, and shop name will all be
  yours, nothing of theirs comes over."*

## Pipeline — measure → survey → tokens → build → diff → deliver; never skip measuring

### 0. Prepare

- Ask if missing: the reference URL + the learner's own content (product
  name, one-line intro, benefits, price/offer, button labels). Use
  ask_user_question when needed.
- Multi-language site (e.g. `/en/`, `/it/`, an EN|FR menu) → ask which
  language version to clone. Default: the one at the URL they gave.
- Ask the placeholder-image style: **labeled image blocks** (works
  offline, no network — default) or **images the learner provides**.
  Avoid random images from outside services: off-topic and they break
  offline.

**The learner does NOT know the web** — principles throughout the pipeline:

- Do everything you can yourself (measure, click, select) before asking
  anything.
- When you must ask, ask in terms of what they SEE on screen — menu
  item names, buttons — never hand them a list of URLs/selectors to
  pick from.
- Never make them do technical key/button steps (Ctrl+S, devtools,
  opening a file in the browser). If the extension can do it, do it
  yourself; only ask for their hands when truly needed, with
  click-by-click instructions naming exactly what's on their screen.
- Create a working folder `clone-work/<site-slug>/` under `workspace/`
  — ONE FOLDER PER SITE (e.g. `clone-work/mekongtouch/`). Using a
  shared `clone-work/` makes the second site's measurements overwrite
  the first's. The folder holds: `ref-dom.html`, `ref-styles.json`,
  `ref-assets.json`, `ref-shot.png`, `ref-css/`, `ref-states.md`,
  `tokens.md`, then the final clone.

### 1. Measure on the live page (via the extension — /open-web)

Check `{"connected": true}` first. `open` the reference page → `wait`
→ scroll the whole page (`scroll` to `atBottom`) so lazy-load finishes
→ scroll back to top. Then extract (save everything into `clone-work/`):

| POST /api/browser call | Yields | Save as |
|---|---|---|
| `{"action":"dom","tabId":T}` | live HTML of the whole rendered page | `ref-dom.html` |
| `{"action":"dom","tabId":T,"sel":"header"}` + each main section | per-block DOM | same file/notes |
| `{"action":"styles","tabId":T,"sel":"body","deep":true,"depth":3}` | computed style + box of first ~120 elements | `ref-styles.json` |
| `{"action":"styles","tabId":T,"sel":"h1"}` `h2,.btn,a,nav,...` | per-element-type styles | same file |
| `{"action":"assets","tabId":T}` | images, inline SVG icons, fonts, CSS links, background-images | `ref-assets.json` |
| `{"action":"css","tabId":T}` | stylesheet contents (full rules) | `ref-css/*.css` |
| `{"action":"screenshot","tabId":T}` | reference image for comparison | `ref-shot.png` |

`styles` returns **real computed values** (rgb colors, px, font stacks)
— the ONLY data source for the clone. Never guess from a screenshot.
When `css` reports a sheet as `blocked` → take its `href` and `fetch`
or `curl` the contents directly.

Note `styles sel=body depth=3` only returns the first ~120 elements —
long pages won't reach the last sections. After the whole-page pass,
measure ADDITIONAL `styles` per main section (`sel` = `#id` or a class,
without `deep`) and merge into `ref-styles.json` — every section needs
at least one record for step 4 to compare against.

Verify the DOM you got is the real page, not an anti-bot page
(Cloudflare "checking your browser", `cf-`, a nearly empty body on a
content-rich site). Handle it in stages:

1. `wait` 8-10s → `dom` again — challenges usually clear by themselves
   in the learner's real browser.
2. A captcha checkbox → click it yourself via the extension
   (`click`/`tclick`) — a real browser with cookies/history often
   passes.
3. Still stuck → ask the learner with click-by-click instructions
   describing what they see: *"open that page, you'll see a checkbox
   saying 'I'm not a robot' — click it, and once the page loads, tell
   me"*. Wait for them → measure again.
4. They can't or it's hard-blocked → suggest picking an equivalent
   different site. NEVER clone a challenge page as the "copy".

For single-page sites with many anchors (`#id` menus): capture extra
`ref-shot-<anchor>.png` at EACH main anchor during measurement —
`open` the URL with `#id`, `screenshot`, wait if rate-limited. Don't
come back to the source at step 4 for shots you missed.

If the extension can't connect → fallback: `webfetch`/`curl` for HTML
+ CSS links, and ask the learner for a screenshot. Less accurate —
tell them installing the extension gives a better clone.

### 1a. Measure interaction states — content only visible after clicking

Static DOM does NOT contain content of closed panels (accordions,
tabs, dropdowns, modals, filters) — many sites only render the open
panel. Measure statically and you see 1 answer when there are 9.
Mandatory:

1. From `snapshot`/`ref-dom.html`, list interactive controls:
   accordion triggers, tabs, dropdown buttons, filter chips, toggles,
   mobile (burger) menus, sliders with next/prev.
2. Click EACH control on the live page (`click` by snapshot ref;
   `scroll` to it first if off-screen) → read `dom`/`snapshot` of the
   newly revealed region → record hidden content into `ref-states.md`.
3. Result: every control has its content in every state — the clone
   won't be missing answers/tabs/panels.

### 1b. Survey the architecture — ONE page or MANY pages

This step exists because of a real past failure: measure one screen,
build the whole site as one page → menu clicks go nowhere, tons of
content missing. The reference may be a landing, but it may also be a
**multi-route SPA** or a **real multi-page site** — each menu item a
different page. Know which kind you're facing BEFORE building.

1. From `ref-dom.html`, gather EVERY internal link (menu, buttons,
   cards, footer). Menus with dropdowns/submenus → expand them first
   (state measurement in 1a) to catch child routes — important routes
   often hide in submenus, and reading only top-level links misses
   them. Classify:
   - `href="#/..."` (hash with a `/`) → **SPA hash-route**: each
     `#/path` is a page. One physical page, JS swaps content per hash.
   - `href="/..."` or same domain → **multi-page site (MPA)**: each
     path is a real page.
   - `href="#id"` (plain hash) → in-page anchor — not a route, keep
     as a scroll link.
   - Other domain / `mailto:` / `tel:` → external link, leave as is.
2. For SPA/MPA: list **every route in the menu** (and clear secondary
   routes like `/services#HomeCare` — that's a section inside a
   route page, not a new route). Open each route on a real tab
   (`open` the full URL; for SPAs open `https://site/#/route`), `wait`
   for render, scroll fully, then extract `dom` + `screenshot` for
   EACH route → save `ref-dom-<route>.html`, `ref-shot-<route>.png`
   in clone-work. Every route needs its own refs — never guess a
   subpage's content from the home page. Measuring cost scales with
   route count: menu routes first; if screenshots hit
   `MAX_CAPTURE_..._PER_SECOND`, wait a few seconds and retry — don't
   drop shots, they're the step-4 reference. Many-route site: default
   to cloning the home page + routes shown in the MENU — that's what
   the learner expects since they see them on the page. Menu too long
   (>~10 items) → prioritize the first ~7 and say plainly: *"this
   site has many sections, I'll do the main ones first — tell me if
   any section is missing and I'll add it"*. NEVER hand them a list
   of paths to pick from — they can't read those. If you truly must
   ask, ask by MENU ITEM NAME via `ask_user_question`.
3. Detail pages under a route (post detail, product detail — links
   like `#/blog/<slug>`): do NOT clone each one. Keep the link
   pattern; the clone's router falls back to the parent page when
   clicked (step 3). A card linking to a cloned page (template, new
   page) points at the right child route; a card to an un-cloned
   page keeps its real link — don't replace with `href="#"` (viewers
   will think the button is dead).
4. Decide the clone's architecture from the source's:
   - One page (only `#id` anchors) → single file as before.
   - SPA/MPA → **one `.html` file with a hash router** (see the
     skeleton in step 3): each route is a `<div data-cs-page="/route">`
     holding that page's sections; shared header/footer stays outside.
     Menu links point to `#/route` EXACTLY like the source.

### 2. Extract the "design system" (design tokens)

From `ref-styles.json` + `ref-css`, lock these before coding:

- **Palette**: main background, text color, accent (buttons),
  secondary — take the exact measured rgb/hex values, grouped by
  frequency.
- **Type scale**: font-family (including web fonts — see `fonts` in
  assets), size per heading level/body/small, weight, line-height.
- **Spacing**: the most repeated padding/margin/gap → base unit.
- **Other**: border-radius, box-shadow, container width, hover/
  transition effects if the CSSOM has them.

Write them into `tokens.md` in clone-work — one compact table. This is
the page's "DNA": keep it absolutely intact in the clone.

### 3. Build the clone — section by section, to the MARKED STANDARD

- ONE self-running `.html` file (embedded CSS), in the exact section
  order of `ref-dom.html`. Build each section from the source DOM:
  same nesting, same column count, same element order.
- Every number (px, color, font-size, radius, shadow) comes from
  `ref-styles.json`/tokens — NO estimated values.
- Icons: re-insert inline SVG extracted from `ref-assets.json`
  (except logos); if missing, draw a simple equivalent SVG.
- Web fonts: `<link>` Google Fonts if in assets; paid fonts → nearest
  available + tell the learner.
- Images: `placeholder` blocks (colored block / matching-topic
  unsplash) at the exact measured `w×h` — remind them to swap in real
  photos later.
- JS: recreate VISIBLE effects (menu open/close, sliders, hover,
  scroll-reveal, counters) with small self-written JS — never copy
  the source's scripts (dirty and often has tracking).
- `<title>` = the learner's page name (never keep the source title —
  a browser tab showing someone else's brand looks sloppy). Favicon:
  drop it or use a neutral icon. Meta description = the learner's.
- Content: ALL text is the learner's, from what you asked.

**STANDARD SKELETON — mandatory on every clone** (whether the source
is a landing, blog, or complex site). Goal: outside it looks identical
to the reference, inside every clone shares the same familiar
structure — next time you edit or clone another page, AI and viewer
recognize it the same way.

```
<section data-cs="Display name" data-cs-type="TYPE">
  <div class="cs-wrap">    <!-- measured max-width + padding -->
    ...content matching the source DOM, same columns/order...
  </div>
</section>
```

**`data-cs-type`** — map each source block to the nearest TYPE. This
is an **OPEN vocabulary**: prefer common types from the table; for an
unusual block make a short English slug describing it (`slider`,
`team`, `steps`, `stats`, `map`, `countdown`, `partners`, `timeline`,
`tabs`, `video`, `newsletter`, `comparison`, `404`…). Since `data-cs`
always holds the HUMAN-READABLE name, unusual types still display
right in the viewer — don't force a strange block into `misc` when it
has its own name.

| Type | Common blocks |
|---|---|
| `nav` | header, menu bar |
| `hero` | top-of-page block, big banner |
| `features` | benefits/services/cards grid |
| `content` | intro paragraph, text + image |
| `gallery` | image grid |
| `pricing` | price table |
| `faq` | questions, accordion |
| `testimonial` | customer reviews |
| `cta` | call to action |
| `form` | contact/signup form |
| `blog` | post list |
| `post` | one article's content |
| `footer` | page footer |
| `misc` | only when truly unnameable |

**Design tokens must be CSS variables on `:root`** — every repeated
measured value goes through a variable, no scattered literals:

```css
:root{
  --cs-font:'Instrument Sans',sans-serif;
  --cs-primary:#2f6f5e; --cs-accent:#e8a87c;
  --cs-bg:#fdf8f2;      --cs-text:#1d2b26;
  --cs-radius:16px;     --cs-gap:24px;
}
```

**Mark editable elements** inside each section:

| Attribute | Put on | Meaning when editing |
|---|---|---|
| `data-cs` | each `<section>` | Block name shown on hover |
| `data-cs-text` | `h1`/`h2`/`p`/`li`/`span`… | Click → type new text in place |
| `data-cs-img` | `<img>` | Click → swap image (link/local file) + alt |
| `data-cs-link` | `<a>`/buttons | Click → edit label + URL |
| `data-cs-bg` | blocks with color/image bg | Click → change bg color / image |
| `data-cs-ref` | sections + big elements | Matching source selector (`el` in `ref-styles.json`, e.g. `section#nous.about`) — lets `clone-compare.py harvest` match elements during diff |

The clone file does NOT embed the editing script — the app's viewer
handles that.

**Multi-route sites** (per survey 1b): still ONE `.html` file,
recreating the source's navigation with a small self-written hash
router — do NOT scroll to sections pretending they're pages, do NOT
split into multiple files (the viewer edits one file):

```html
<header data-cs="Top menu" data-cs-type="nav"> …menu links → #/route… </header>
<main id="main">
  <div data-cs-page="/">          <!-- home sections -->   </div>
  <div data-cs-page="/about">     <!-- about sections -->  </div>
  …
</main>
<footer data-cs="Footer" data-cs-type="footer"> … </footer>
```

- `data-cs-page` holds `<section data-cs data-cs-type>` as usual —
  the viewer can edit the currently shown page.
- Small router JS (~20 lines, self-written): read `location.hash`,
  show the matching `data-cs-page` (`#/a` → `/a`, default `/`), hide
  the rest (`hidden` + `display:none`), mark the matching menu item
  `is-active`, scroll to top — or to an `id` element when the hash
  looks like `#/route#id` (cross-links like `#/contact#book`).
- Un-cloned child routes (`#/blog/<slug>`) → router matches the
  nearest parent (`/blog`) → viewer still lands on the list page.
- Un-cloned TOP-LEVEL menu routes (too many routes, see 1b) → point
  links at the real source URL (`https://site.com/route`). Falling
  back to home makes "Contact" show the home page and viewers think
  it's broken; opening the real page is more honest.
- Real external links (mailto/tel/other domains) keep their `href` —
  the router doesn't touch them.

**Detail-page templates (second level)** — clone at most the first 3
pages of each kind (article, tour, product, recipe, property…). The
FIRST page of each kind also carries `data-cs-template="<kind-slug>"`:
marks it as the "mold" `/new-page` clones when the learner writes
more. The slug is an **open vocabulary** — name the true nature of
the detail page (`post`, `article`, `tour`, `product`, `recipe`,
`property`, `course`…), don't force a fixed list. Only ONE template
per kind — the copies it spawns don't carry this marker.

### 4. Diff and fix — max 4 rounds, PER ROUTE/ANCHOR

**Don't stop once the first page matches.** The worst mismatches are
usually mid/late sections — it really happened: hero identical but
the next 4 sections used light backgrounds where the source was dark,
and nobody saw it until comparing block by block.

- **Background audit first (cheap, catches big errors):** extract
  `background` + `color` of EACH section/large block from `ref-css`
  (or `styles` on the source) into a table — which sections are dark
  (`forest`, image bg + overlay), which light (`paper`, `white`).
  Compare the clone section by section: same background tone? Cards
  inside the right style (frosted glass `rgba(...,.3)` / solid white
  / transparent)? The "dark became light" mistake is the most common
  because DOM never says it — only CSS does.
- Multi-route sites: `open` the clone with `#/route` → `screenshot`
  → place beside the `ref-shot-<route>.png` of THAT SAME route.
  Compare each route against its own shot — never use the home shot
  for everything.
- One-page-many-anchor sites: `open` the clone with each nav `#id`
  → `screenshot`, compare to the source shot at the same anchor. At
  minimum: top + every block with its own bg/layout + the last block.
- Re-measure `styles` on the CLONE vs `ref-styles.json`: matching
  elements must have near-equal font-size/color/padding (off ≤ 2px,
  color off by a few rgb units). Watch text in light cards on dark
  sections: inheriting the dark section's `color` makes text
  "disappear" on white cards — set the ink color inside cards.
- **Diff automatically, not just by eye** — `tools/clone-compare.py`:
  `harvest <clone-file> <tabId>` measures styles of every
  `data-cs-ref` element on the clone tab → `styles <ref-styles.json>
  <clone-styles.json>` reports each px/rgb mismatch, matching elements
  by `data-cs-ref` so differing class names don't confuse it;
  `shot <ref.png> <clone.png>` reports % pixel difference — only for
  low-image blocks, since a placeholder-image section differing from
  the real photo naturally scores high.
- **Static file check** before diffing: file parses without errors,
  count of `data-cs` ≥ number of big sections, every section has
  `data-cs-type`, each detail-page kind has exactly ONE
  `data-cs-template`.
- Per-section height is a signal too: a clone section off by hundreds
  of px vs source usually means a missing block or doubled padding
  (e.g. `section-pad` stacking on `min-height:100svh`).
- Nesting must match the source, not just "look similar": e.g. a
  gallery INSIDE a text card vs below both columns — read
  `ref-dom.html` to confirm position, don't guess from screenshots.
- Check the interaction states measured in 1a: open each accordion/
  tab/menu in the CLONE and confirm content matches `ref-states.md`.
- Check mobile: scan `ref-css` for the source's breakpoints (e.g.
  ≤767px) — the clone needs matching media queries (burger menu,
  columns → rows, sticky-cta…). If the extension can measure in a
  narrow window, shoot more; otherwise statically check media queries
  in the clone file.
- Per-item checklist: layout · colors · fonts · spacing · icons ·
  radius/shadows · basic responsiveness.
- Fix what's wrong and reshoot. Stop when the naked eye sees
  "identical frame" on EVERY route, or after 4 rounds → record what's
  still off in the report.

### 5. Deliver to the learner

- Open the result in the **app's viewer** (not a bare file): `open`
  or lead them to
  `http://localhost:8080/web/clone-view.html?src=/workspace/<file>.html`
  — the page shows FULL-SCREEN inside the app with a toolbar:
  **Edit content** → click straight on text/images/buttons/blocks to
  change in place → **Save page** (writes back to the file) or
  **Download**, and the **✕** button to close.
- Report in human words: *"done — your page is open, click Edit
  content on top then click anything you want to change. It matches
  the reference ~95% in frame; the parts that don't: [list plainly]."*
- Hint: *"next time you see a nice page, just type `/clone-page` with
  the link."*
- Keep the `clone-work/` folder — the measurements are ready for the
  next round of edits.

## Limits to state plainly when hit

- A page needing login the extension can't open → ask the learner to
  Ctrl+S save the page locally, then clone from that file.
- Backend-powered parts (cart, login, data-saving forms) → you can
  build the VISIBLE frame + UI JS only, no backend: *"this button is
  for show — making it really work is the next step"*.
- Complex animation (WebGL, canvas, multi-layer scroll-timelines) →
  approximate as close as possible, say clearly what was simplified.
