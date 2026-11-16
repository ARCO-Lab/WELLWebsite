# Managing Posts in WordPress

This guide explains how to **add**, **edit**, and **delete** news articles (posts) in WordPress.

---

## Adding a New Post

1. **Log in** to your WordPress admin dashboard (usually at `/wp-admin`).
2. In the left sidebar, click **Posts > Add New**.
3. Enter your **title** and **content**.
4. (Optional) Add a **featured image** by clicking "Set featured image" in the right sidebar.
5. (Optional) Add categories or tags if needed.
6. Click **Publish** to make your post live.

---

## Editing an Existing Post

1. In the WordPress admin, click **Posts > All Posts**.
2. Find the post you want to edit and click its title or the **Edit** link.
3. Make your changes.
4. Click **Update** to save.

---

## Deleting a Post

1. In **Posts > All Posts**, hover over the post you want to delete.
2. Click **Trash**.
3. To permanently delete, go to the **Trash** tab, hover over the post, and click **Delete Permanently**.

---

## Tips

- Posts will automatically appear on the News page and have their own unique URL.
- You do **not** need to edit any code to manage posts.
- Use the **Preview** button to see your changes before publishing.

---

## Editing Pages

To build or edit **pages** (not posts) and use the ready-made WELL building blocks (patterns), see
the **[WELL Website Editor Handbook](../../../../docs/EDITOR-HANDBOOK.md)**.

---

## Sampling data upload guide (link-only page)

The theme includes a page template, **Sampling Data Upload Guide** (`template-sampling-upload.php`), for a
link-only help page that tells researchers how to format and upload their sampling CSV and lets them check a file
before uploading. It is meant to be **shared by its link only**:

- Create a **Page** (Pages > Add New), give it an **unlisted/obscure slug** (Page > URL), leave it **out of every
  menu**, and under **Page Attributes > Template** choose **Sampling Data Upload Guide**.
- The template marks the page **noindex** automatically, so search engines skip it.
- The format rules, reference tables and the "Check my CSV format" box all come from the dashboard
  (`/api/samples/validate` and `/api/samples/format`), so they always match what the weekly import accepts — there
  is no separate copy to keep in step.
- **Screenshots:** the step boxes show dashed placeholders. To add real screenshots, drop images into the page
  content or replace the placeholder markup in `template-sampling-upload.php`. Use your own screenshots only; do not
  paste branded Borealis/McMaster images you don't have the right to publish.
