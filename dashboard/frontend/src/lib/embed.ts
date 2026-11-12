// The dashboard shown inside the WordPress site's Dashboard page (an iframe of /?embed=1, from the theme's
// page-dashboard.php and js/dashboard-embed.js).
//
// next.config.ts rewrites /?embed=1 to /embed, a static page rendered without the header and footer, so the server
// HTML has none and nothing flashes. Any other framing of the site (an old link without ?embed=1) is caught before
// first paint by the inline script in _document.tsx, which marks <html> with "in-frame"; globals.css then hides the
// header and footer.
//
// The two pages talk with postMessage, each checking the other's origin:
//   - the dashboard sends its content height ({type: "well-embed:height", height}), and the page sizes the iframe to
//     it, so the iframe never needs a scrollbar of its own;
//   - the page answers with which part of the iframe is in its window ({type: "well-embed:viewport", top, height},
//     in iframe pixels), on scroll and resize. globals.css places the dialogs (an enlarged chart) in that part:
//     a dialog fixed to the middle of a 3000 px tall iframe would otherwise open out of sight. The dashboard
//     answers the first of these with its height again, in case the page wasn't listening yet when it sent it.
//     StickyPanel uses it too (getEmbedView, subscribeEmbedView) to keep the Filters panel in view, since the
//     iframe itself no longer scrolls.
// Messages are only exchanged with the WordPress site (PARENT_ORIGINS), the sites the CSP frame-ancestors allows.

import { useEffect, type RefObject } from "react";

/**
 * Origins of the WordPress site, the only pages the dashboard talks to: well.mcmaster.ca with and without www, and
 * NEXT_PUBLIC_WP_HOME's origin if that is another one (a test site).
 */
export const PARENT_ORIGINS: readonly string[] = [...new Set([
  "https://well.mcmaster.ca",
  "https://www.well.mcmaster.ca",
  new URL(process.env.NEXT_PUBLIC_WP_HOME || "https://well.mcmaster.ca").origin,
])];

export const HEIGHT_MESSAGE = "well-embed:height";
export const VIEWPORT_MESSAGE = "well-embed:viewport";

/** Whether this page is shown inside a frame (a cross-origin parent counts; an error means a frame too). */
export function inFrame(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
}

/** The parent page's origin, where the browser says (Chrome, Safari); null where it doesn't (Firefox). */
function parentOrigin(): string | null {
  const ancestors = window.location.ancestorOrigins;
  return ancestors && ancestors.length > 0 ? ancestors[0] : null;
}

/** The part of the iframe in the WordPress page's window, in iframe pixels (null until the page has said). */
export type EmbedView = { top: number; height: number };
let view: EmbedView | null = null;
const viewListeners = new Set<() => void>();

export const getEmbedView = (): EmbedView | null => view;

/** Calls `listener` whenever the WordPress page reports a new part in view; returns the unsubscribe function. */
export function subscribeEmbedView(listener: () => void): () => void {
  viewListeners.add(listener);
  return () => { viewListeners.delete(listener); };
}

/**
 * On the embedded page: reports the height of `root` to the WordPress page whenever it changes, and follows the
 * part of the iframe that page says is in view (the --embed-view-top and --embed-view-height CSS variables, and the
 * "embed-sized" class on <html>, set once the first answer arrives).
 */
export function useEmbedFrame(root: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const el = root.current;
    if (!enabled || !el || !inFrame()) return;
    const known = parentOrigin();
    if (known !== null && !PARENT_ORIGINS.includes(known)) return;

    // Where messages go: the parent's origin once known (from the browser, or from its first message); until then
    // each trusted origin, of which only the parent's actually receives it.
    let target = known;
    const post = (message: object) => {
      for (const origin of target ? [target] : PARENT_ORIGINS) window.parent.postMessage(message, origin);
    };

    let last = -1;
    const send = () => {
      // The element's own height: the document's would never shrink below the iframe's current height
      const height = Math.ceil(el.getBoundingClientRect().height);
      if (height === last) return;
      last = height;
      post({ type: HEIGHT_MESSAGE, height });
    };
    const observer = new ResizeObserver(send);
    observer.observe(el);
    send();

    const html = document.documentElement;
    const onMessage = (e: MessageEvent) => {
      if (!PARENT_ORIGINS.includes(e.origin) || e.source !== window.parent) return;
      const d = e.data as { type?: unknown; top?: unknown; height?: unknown } | null;
      if (!d || d.type !== VIEWPORT_MESSAGE) return;
      const top = Number(d.top);
      const height = Number(d.height);
      if (!Number.isFinite(top) || !Number.isFinite(height) || top < 0 || height <= 0) return;
      target = e.origin; // reply to the page that wrote
      view = { top, height };
      html.style.setProperty("--embed-view-top", `${Math.round(top)}px`);
      html.style.setProperty("--embed-view-height", `${Math.round(height)}px`);
      // The first one is also the page's way of asking for the height, in case it wasn't listening yet
      if (!html.classList.contains("embed-sized")) {
        html.classList.add("embed-sized");
        last = -1;
        send();
      }
      viewListeners.forEach((listener) => listener());
    };
    window.addEventListener("message", onMessage);

    return () => {
      observer.disconnect();
      window.removeEventListener("message", onMessage);
      view = null;
    };
  }, [root, enabled]);
}
