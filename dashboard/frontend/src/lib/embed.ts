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
// Messages only go to the WordPress site's origin (NEXT_PUBLIC_WP_HOME), the same site the CSP frame-ancestors allows.

import { useEffect, type RefObject } from "react";

/** Origin of the WordPress site, the only page the dashboard sends its height to. */
export const PARENT_ORIGIN = new URL(process.env.NEXT_PUBLIC_WP_HOME || "https://well.mcmaster.ca").origin;

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

/** Whether the parent page is the WordPress site, where the browser says (Chrome, Safari); otherwise assumed. */
function parentIsSite(): boolean {
  const ancestors = window.location.ancestorOrigins;
  return !ancestors || ancestors.length === 0 || ancestors[0] === PARENT_ORIGIN;
}

/**
 * On the embedded page: reports the height of `root` to the WordPress page whenever it changes, and follows the
 * part of the iframe that page says is in view (the --embed-view-top and --embed-view-height CSS variables, and the
 * "embed-sized" class on <html>, set once the first answer arrives).
 */
export function useEmbedFrame(root: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const el = root.current;
    if (!enabled || !el || !inFrame() || !parentIsSite()) return;

    let last = -1;
    const send = () => {
      // The element's own height: the document's would never shrink below the iframe's current height
      const height = Math.ceil(el.getBoundingClientRect().height);
      if (height === last) return;
      last = height;
      window.parent.postMessage({ type: HEIGHT_MESSAGE, height }, PARENT_ORIGIN);
    };
    const observer = new ResizeObserver(send);
    observer.observe(el);
    send();

    const html = document.documentElement;
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== PARENT_ORIGIN || e.source !== window.parent) return;
      const d = e.data as { type?: unknown; top?: unknown; height?: unknown } | null;
      if (!d || d.type !== VIEWPORT_MESSAGE) return;
      const top = Number(d.top);
      const height = Number(d.height);
      if (!Number.isFinite(top) || !Number.isFinite(height) || top < 0 || height <= 0) return;
      html.style.setProperty("--embed-view-top", `${Math.round(top)}px`);
      html.style.setProperty("--embed-view-height", `${Math.round(height)}px`);
      // The first one is also the page's way of asking for the height, in case it wasn't listening yet
      if (!html.classList.contains("embed-sized")) {
        html.classList.add("embed-sized");
        last = -1;
        send();
      }
    };
    window.addEventListener("message", onMessage);

    return () => {
      observer.disconnect();
      window.removeEventListener("message", onMessage);
    };
  }, [root, enabled]);
}
