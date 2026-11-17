# The WELL Website Editor Handbook

*A guide to editing the WELL site's pages in WordPress — no coding required for most of it.*

This handbook covers how to update the text and images on the WELL website using the WordPress block editor, which ready-made building blocks (**patterns**) were made for this site, and — just as importantly — which parts are intentionally left as code so you never change something that would break.

---

## 1. Getting started

### Logging in

Go to the site's `/wp-admin` address and sign in with your WordPress username and password.

> **Heads up:** if a login box pops up *inside* a page you're editing, that's just your session timing out — not a bug. Sign in again and you'll be dropped back where you were.

### Pages vs. Posts

- **Pages** — Home, About, Dashboard, News, and the Sampling Data Upload Guide. The permanent structure of the site.
- **Posts** — the news items that appear in the News list and the home page's "Latest News" strip. Use these for announcements.

Both use the same block editor.

### The save buttons

| Button | What it does |
|---|---|
| **Save draft** | Saves privately; the public page is untouched until you publish. |
| **Preview** | Opens the page in a new tab exactly as visitors see it — always check this before a big change. |
| **Update** / **Publish** | Makes your changes live immediately. |

---

## 2. Editing text and images

1. Click directly on the text you want to change and type — it behaves like any text box. Select text to make it bold, italic, or a link using the small floating toolbar.
2. To move a block, select it and use the **drag handle (⠿)** or the up/down arrows in its toolbar.
3. **List View** (the ☰ icon, top-left) shows the whole page as an outline — the easiest way to select something that's fiddly to click, like a block inside a card.

> **Preview before you publish**, and remember **Ctrl+Z / Cmd+Z** undoes your last action. Every page also keeps **Revisions** (right-hand sidebar) so you can restore an earlier version.

> **If you ever see "This block contains unexpected or invalid content"** — stop, don't click "Attempt Recovery," and ask a developer. It's usually a two-minute fix, and recovery can sometimes reset custom text.

---

## 3. The WELL pattern library

Patterns are pre-built, pre-styled pieces made for this site. Find them under **Inserter (⊕) → Patterns → WELL**.

| Pattern | What it is |
|---|---|
| **Text + Circular Photo (About section)** | A banded section with a heading and text beside a circular photo — the About page's style. |
| **Hero Banner** | A full-width image banner with a title and one line. |
| **Section Heading** | A heading with the gold underline accent. |
| **Two Column (Text + Image)** | Text on one side, a photo on the other. |
| **Card Grid (3-up)** | A row of three matching cards. |
| **CTA Banner** | A full-width maroon call-to-action banner with a button. |
| **Team Member Card** | A single team-member card (photo, name, role, bio). |
| **Featured Quote** | A pulled-out quote with a maroon side rule. |
| **WELL: Standard Content Page** | A full starter layout for a new page. |

There are also a few patterns that simply **place a developer-owned piece** (see Section 5), so you can drop it onto a page: *Home Hero Carousel*, *Latest News Strip*, *Dashboard Embed*, *Sampling CSV Checker*, and *Team Grid*.

---

## 4. What's editable on each page

| Page | Click-and-edit | Stays as code (ask a developer) |
|---|---|---|
| **Home** | The "About Us" blurb (heading, text, Learn More button) | Hero carousel, the dashboard card, the "Latest News" strip |
| **About** | The four "About WELL / What is WELL measuring? …" text-and-photo sections | The circular photos (kept exact), the "Our Team" cards |
| **Dashboard** | The "Archived Datasets" section (Borealis / SharePoint links) | The live dashboard embed and the banner above it |
| **News** | An optional intro above the list (anything you add renders there) | The news list itself (it shows your posts automatically) |
| **Sampling Data Upload Guide** | The headings and explanatory paragraphs throughout | The reference tables, the diagrams, the screenshots, the step buttons, and the "Check my CSV format" tool |

Within an otherwise-editable page, the "stays as code" pieces appear in the editor as a **Shortcode block** (for example `[well_team]`) or an **HTML block**. You can move or delete those blocks, but don't edit what's inside them — if the content needs to change, ask a developer.

---

## 5. What *not* to edit (and why)

A few pieces are kept as code rather than rebuilt as simple blocks, because they depend on exact markup or live behaviour that a generic block would break. In the editor they look like a **Shortcode** or **HTML** block:

| Piece | Shortcode | Why it's code |
|---|---|---|
| Home hero carousel | `[well_hero_carousel]` | A JavaScript carousel engine tied to exact markup. |
| Home "Latest News" strip | `[well_latest_news]` | Queries the latest posts live; updates itself. |
| Home dashboard card | `[well_dashboard_card]` | A CSS-coupled card (hover states, split image/text). |
| Dashboard embed | `[well_dashboard_embed]` | Embeds the separate dashboard app and talks to it. |
| About team grid | `[well_team]` | Each card is wired to its own contact pop-up by a matching id. |
| Sampling CSV checker | `[well_sampling_checker]` | Sends files to the dashboard's real CSV validator. |
| News list | *(in the News template)* | Loops your posts, with paging. |

You can still **select and move** these blocks to reorder a page — just don't open "Edit as HTML" and change what's inside them. To change their content, ask whoever manages the site's code.

The circular About photos and the Sampling guide's diagrams/tables are kept as **HTML blocks** for the same reason (pixel-exact, or wired to the checker). A developer changes those in the theme files.

---

## 6. For developers

- The pages' editable content is seeded by `home/wp-content/themes/well/tools/migrate-pages-to-blocks.php` (run with wp-cli; it only writes a page's content when that page is still empty, so it's safe to re-run and never overwrites editor changes). The block markup it uses is in `tools/page-blocks.php`.
- The developer-owned pieces live in `home/wp-content/themes/well/sections/*.php` and are exposed as shortcodes in `inc/shortcodes.php`.
- If a page has no content yet, its template falls back to the original hard-coded sections, so nothing goes blank before the migration runs.
- Patterns are in `home/wp-content/themes/well/patterns/`; the brand styling of blocks and patterns is in `css/well-patterns.css` and the editor shim `css/editor.css`.
