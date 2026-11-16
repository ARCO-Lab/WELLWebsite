# The WELL Website Editor Handbook

*A guide to editing the WELL website in WordPress — no coding required for most of it.*

This handbook covers how to update the WELL website (well.mcmaster.ca): editing text, adding new
content, reordering things, and using the ready-made building blocks — called **patterns** — that
were built specifically for this site. It also says honestly which parts need a developer, so you
never guess wrong on those.

---

## 1. Getting started

### Logging in

Go to `well.mcmaster.ca/wp-admin` and sign in with your WordPress username and password.

> **Heads up:** if you're editing for a while and a login box suddenly appears, that's just your
> session timing out — not a bug. Sign in again and you'll be back where you were.

### Pages vs. Posts

- **Pages** are the permanent structure of the site. You write and lay them out yourself.
- **Posts** are **News** items — announcements, updates, press. Add these under **Posts**; they
  appear on the News page automatically. (See the theme's own `README.md` for the short posts guide.)

A few pages are special and are **built by the developer, not from blocks** — leave their layout
alone (you can still ask a developer for text changes):

| Page | Why it's developer-built |
|---|---|
| **Home** | Hand-built front page with the banner carousel and the Latest News strip |
| **Dashboard** | Embeds the live data dashboard from welldash.mcmaster.ca |
| **News** | Lists posts automatically with filters and pagination |
| **About** | Custom layout for the team, sensors and watershed sections |

Any **other** page — a new standard content page you create under **Pages > Add New** — is yours to
build with the blocks and WELL patterns described below.

### The three save buttons

| Button | What it does |
|---|---|
| **Save draft** | Saves privately. The public page is untouched until you publish. |
| **Preview** | Opens the page in a new tab exactly as visitors will see it — always check a big change here first. |
| **Publish** / **Update** | Makes your changes live immediately. |

---

## 2. The editor shows the real site styling

When you open a page, you're in the **Block Editor**. Everything — a heading, a paragraph, an image,
a card — is a **block**.

This theme loads the live site's stylesheet into the editor, so **what you see while editing is very
close to what visitors will see**: the maroon brand colour, the gold accents, the Poppins headings,
the card and button styles all show up right in the editing canvas. You rarely need to hit Preview
just to check styling — though it's still worth a final Preview before publishing.

> A few complex, interactive pieces (see Section 6) are kept as raw HTML and will show as a plain
> **HTML/Custom HTML block** in the editor rather than a styled preview. That's expected. All
> ordinary content and all the WELL patterns render styled.

---

## 3. Editing existing text and images

The easiest kind of edit, and it works almost everywhere:

1. Click directly on the text you want to change.
2. Type — it behaves like any text box. Select text to make it bold, italic, or a link using the
   little floating toolbar.
3. For an image, click it, then use the toolbar's **Replace** button to swap in another image from
   the Media Library or an upload.

---

## 4. Moving and reordering content

Every page is a stack of independent blocks, so almost anything can be reordered:

1. Click the block to select it (or find it in **List View** — the ☰ icon, top-left — if it's hard
   to click directly).
2. Either drag it by its **⠿** handle, or use the **↑ / ↓** arrows in its toolbar to nudge it.
3. Update, and check **Preview**.

> **Tip:** rich blocks like cards can be fiddly to click exactly. **List View** always selects the
> right one by name.

---

## 5. The WELL pattern library

Patterns are pre-built, pre-styled pieces made for this site. Find them under
**Inserter (the ⊕ button, top-left) → Patterns → WELL**.

| Pattern | What it is | Use it for |
|---|---|---|
| **Hero Banner** | Full-width photo banner with a page title over it | Starting a new page in the site's style |
| **Section Heading** | A heading with the gold underline accent + intro line | Starting a new section of a page |
| **Card Grid (3-up)** | A row of three photo cards with title, text and a link | A row of features, projects or links |
| **Two Column (Text + Image)** | Text on one side, a photo on the other | An intro, a feature, or a profile block |
| **Featured Quote** | A pulled-out quote with a maroon side rule and attribution | Highlighting a quote in news or features |
| **Team Member Card** | Photo, name, role and short bio in a card | A person; place three across for a team row |
| **CTA Banner** | Full-width maroon banner with a heading and a button | A "call to action" strip |
| **WELL: Standard Content Page** | A whole starter page: hero + heading + cards + CTA | The fastest way to start a brand-new page |

**To insert a pattern:** Inserter → **Patterns** tab → **WELL** → click the one you want. It drops in
at your cursor. Then edit the text and images inside it like normal.

> The patterns use the site's own classes, so they look native. Replace the placeholder photos
> (they default to WELL installation photos) and the placeholder text with your own.

---

## 6. What *not* to edit (and why)

A few pieces depend on precise code or live data and should not be rebuilt as blocks:

| Element | Where | Why |
|---|---|---|
| Banner carousel | Home page | Auto-rotating carousel tied to exact markup |
| Live data dashboard | Dashboard page | Embedded from the dashboard app |
| News list + filters | News page | Generated from posts automatically |
| Team / sensor / watershed sections | About page | Custom developer layout |

You can still select and move these as whole blocks to reorder sections — just don't open **Edit as
HTML** and change their structure. If one needs a content change, ask a developer.

---

## 7. Working safely

- **Preview before you publish.** It takes ten seconds and shows exactly what visitors will see.
- **Undo is your friend.** `Ctrl+Z` (`Cmd+Z` on Mac) undoes your last actions.
- **Revisions let you go back in time.** Each saved page keeps a history — find **Revisions** in the
  right-hand sidebar to compare or restore an earlier version.
- **If you see "This block contains unexpected or invalid content"** — stop, don't click "Attempt
  Recovery," and ask a developer. It's usually a quick fix, and recovery can wipe custom text.

---

## 8. Notes for developers (editors can ignore)

- **On-brand editor:** `theme.json` plus `add_editor_style()` in `functions.php` load the real
  front-end CSS (and a small `css/editor.css` shim) into the block editor, which is why the editor
  canvas looks like the live site. The patterns live in the theme's `patterns/` folder and are
  registered automatically; their shared styles are in `css/well-patterns.css`.
- **Republished news canonicals:** when a News post is republished from another site, its original
  URL is stored in the `_canonical_url` custom field, and the theme automatically points that post's
  `rel="canonical"` at the original. Editors never need to touch this; it's handled in `functions.php`.
