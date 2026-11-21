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

### The developer-owned pieces now preview in the editor

Some pieces of the site stay as code (the team cards, the live dashboard, the "Check my CSV format" tool — see Section 5). In the editor these now appear as a **WELL block that shows a live preview of the real content**: you'll see the actual team cards, the dashboard and the checker right in the editing canvas, each labelled with a name like *WELL: Team Grid* in its toolbar and in List View.

- You can **move or delete** one of these blocks to re-arrange a page.
- You **can't type inside it** — there are no text boxes to click. To change what it contains, ask a developer.
- The preview is a still image of the real thing: carousels don't rotate and the checker doesn't take a file *in the editor*. Those come alive on the published page (hit **Preview** to see them working).

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

There are also a few patterns that simply **place a developer-owned piece** (see Section 5), so you can drop it onto a page and see it preview straight away: *Home Hero Carousel*, *Latest News Strip*, *News Listing*, *Dashboard Embed*, *Sampling CSV Checker*, and *Team Grid*.

---

## 4. What's editable on each page

| Page | Click-and-edit | Stays as code (ask a developer) |
|---|---|---|
| **Home** | The "About Us" blurb (heading, text, Learn More button) | Hero carousel, the dashboard card, the "Latest News" strip |
| **About** | The four "About WELL / What is WELL measuring? …" text-and-photo sections | The circular photos (kept exact), the "Our Team" cards |
| **Dashboard** | The "Archived Datasets" section (Borealis / SharePoint links) | The live dashboard embed and the banner above it |
| **News** | An optional intro above the list (anything you add renders there) | The news list itself — a *WELL: News Listing* preview block that builds from your posts automatically (see the note below) |
| **Sampling Data Upload Guide** | The headings and explanatory paragraphs throughout | The reference tables, the diagrams, the screenshots, the step buttons, and the "Check my CSV format" tool |

Within an otherwise-editable page, each "stays as code" piece appears as a **WELL block with a live preview** of the real content (for example *WELL: Team Grid*). You can move or delete those blocks, but there's nothing to type inside them — if the content needs to change, ask a developer.

### The News page previews the list, but you don't edit the articles there

The News page shows a **WELL: News Listing** preview block — the same grid of article cards your visitors see. It is **dynamic**: the list is built automatically from your **Posts**, so there is nothing to lay out inside it and nothing to type. **That's expected — the block is not broken.** To add or change a news item, add or edit a **Post**, not this page.

If you want a short intro line above the list (for example "Keep up with the latest from WELL"), you *can* type it on the News page, **above** the News Listing block: anything you add there renders above the automatic list. Leaving it empty simply shows the list on its own.

---

## 5. What *not* to edit (and why)

A few pieces are kept as code rather than rebuilt as simple blocks, because they depend on exact markup or live behaviour that a generic block would break. In the editor they appear as a **WELL preview block** (and, under the hood, each also has a matching shortcode a developer can place by hand):

| Piece | WELL block / shortcode | Why it's code |
|---|---|---|
| Home hero carousel | *WELL: Home Hero Carousel* (`[well_hero_carousel]`) | A JavaScript carousel engine tied to exact markup. |
| Home "Latest News" strip | *WELL: Latest News Strip* (`[well_latest_news]`) | Queries the latest posts live; updates itself. |
| Home dashboard card | *WELL: Dashboard Card* (`[well_dashboard_card]`) | A CSS-coupled card (hover states, split image/text). |
| Dashboard embed | *WELL: Dashboard Embed* (`[well_dashboard_embed]`) | Embeds the separate dashboard app and talks to it. |
| About team grid | *WELL: Team Grid* (`[well_team]`) | Each card is wired to its own contact pop-up by a matching id. |
| Sampling CSV checker | *WELL: Sampling CSV Checker* (`[well_sampling_checker]`) | Sends files to the dashboard's real CSV validator. |
| News page list | *WELL: News Listing* (`[well_news_list]`) | A live, paginated query of your posts; updates itself. |

You can still **select and move** these blocks to reorder a page — just don't open "Edit as HTML" and change what's inside them. To change their content, ask whoever manages the site's code.

The circular About photos and the Sampling guide's diagrams/tables are kept as **HTML blocks** for the same reason (pixel-exact, or wired to the checker). A developer changes those in the theme files.

---

## 6. For developers

- The pages' editable content is seeded by `home/wp-content/themes/well/tools/migrate-pages-to-blocks.php` (run with wp-cli; it only writes a page's content when that page is still empty, so it's safe to re-run and never overwrites editor changes). The block markup it uses is in `tools/page-blocks.php`.
- The developer-owned pieces live in `home/wp-content/themes/well/sections/*.php`. They are registered two ways, both rendering the *same* section partial so the front end is identical:
  - as **dynamic blocks** (`inc/blocks.php`, with the editor definitions in `js/blocks.js`) — e.g. `well/team` — so the block editor previews the real content with a `ServerSideRender` instead of a bare "Shortcode" placeholder. `tools/page-blocks.php` emits these block comments (`<!-- wp:well/team /-->`).
  - as **shortcodes** (`inc/shortcodes.php`) — e.g. `[well_team]` — kept registered for backward compatibility with any content that still uses them.
- The editor preview is static HTML (the block's `ServerSideRender` fetches the server-rendered markup). JavaScript-driven behaviour — the Flickity carousels, the checker's file handling, the team modals — only runs on the published page, not in the editor canvas.
- If a page has no content yet, its template falls back to the original hard-coded sections, so nothing goes blank before the migration runs.
- Patterns are in `home/wp-content/themes/well/patterns/`; the brand styling of blocks and patterns is in `css/well-patterns.css` and the editor shim `css/editor.css`.
