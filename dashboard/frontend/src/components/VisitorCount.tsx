// Counts page views with GoatCounter (https://www.goatcounter.com): no cookies, nothing stored in the browser, and
// GoatCounter keeps only aggregated counts. The dashboard and the WordPress site share one GoatCounter site, so each
// counted path starts with the site's host ("welldash.mcmaster.ca/"), which keeps the two sites' "/" apart.
//
// Counting runs only in a production build, with NEXT_PUBLIC_GOATCOUNTER_ENDPOINT set (the Dockerfile sets it), and
// only on welldash.mcmaster.ca, so local, preview, CI and e2e runs never send counts. Query strings (?from=&to=) are
// left out of the path, and a change of query alone isn't counted as a new page view.

import Script from "next/script";
import { useRouter } from "next/router";
import { useEffect, useSyncExternalStore } from "react";

const ENDPOINT = process.env.NEXT_PUBLIC_GOATCOUNTER_ENDPOINT || "";
const COUNTED_HOST = "welldash.mcmaster.ca";

type GoatCounter = { count?: (vars: { path: string }) => void };

// The path last counted, so that a change of query string alone (same path) isn't counted again.
let lastPath: string | null = null;

// Counts the page at url: "/?from=...#x" is counted as "welldash.mcmaster.ca/".
function count(url: string) {
  const path = window.location.hostname + (url.split(/[?#]/)[0] || "/");
  const gc = (window as unknown as { goatcounter?: GoatCounter }).goatcounter;
  if (path === lastPath || !gc?.count) return;
  lastPath = path;
  gc.count({ path });
}

// Whether this page counts. The host is only known in the browser, so the server render (and hydration) says no.
const shouldCount = () =>
  process.env.NODE_ENV === "production" && ENDPOINT !== "" && window.location.hostname === COUNTED_HOST;
const noSubscription = () => () => {};

export default function VisitorCount() {
  const router = useRouter();
  const enabled = useSyncExternalStore(noSubscription, shouldCount, () => false);

  // Client-side navigation to another page. Before the script has loaded, onLoad below counts the page instead.
  useEffect(() => {
    if (!enabled) return;
    router.events.on("routeChangeComplete", count);
    return () => router.events.off("routeChangeComplete", count);
  }, [enabled, router.events]);

  if (!enabled) return null;
  return (
    <Script
      src="https://gc.zgo.at/count.js"
      strategy="afterInteractive"
      data-goatcounter={ENDPOINT}
      // Count from here rather than count.js's own page-load count, so every count goes through count().
      data-goatcounter-settings='{"no_onload": true}'
      onLoad={() => count(window.location.pathname)}
    />
  );
}
