import { withSentryConfig } from "@sentry/nextjs/config";

// Security headers for every page and API route. headers() is evaluated by next build (and next dev), so the
// policy is fixed in the build, with the NEXT_PUBLIC_* values the Dockerfile passes.
//
// Content-Security-Policy lists where the page may load things from: its own origin; GoatCounter's script and the
// endpoint it counts to (components/VisitorCount.tsx); the host Sentry's DSN reports to (lib/sentry.ts); the map's
// style, tiles and imagery (components/map/Map.tsx); and Google Fonts (pages/_app.tsx). Styles may be inline
// because Highcharts, MUI (Emotion) and MapLibre set them in the page. Scripts may be inline too: the build puts a
// small inline script in every page that loads its chunks, whose content (so its hash) changes with each build, and
// the page is static, so there is no per-request nonce to give it. Scripts from any other site are still refused.
// MapLibre's worker comes from our own origin. frame-ancestors lets only this site and the WordPress site (whose
// dashboard page embeds this one in an iframe, home/wp-content/themes/well/page-dashboard.php) frame it. In next dev,
// localhost may frame it too (a local WordPress), and scripts may use eval (React's development build needs it).
const dev = process.env.NODE_ENV !== "production";

/** The origin of a URL from the environment, or the fallback when it is unset or not a URL. */
function originOf(url: string | undefined, fallback: string): string {
  try {
    return url ? new URL(url).origin : fallback;
  } catch {
    return fallback;
  }
}

const goatCounter = originOf(process.env.NEXT_PUBLIC_GOATCOUNTER_ENDPOINT, "https://*.goatcounter.com");
const sentry = originOf(process.env.NEXT_PUBLIC_SENTRY_DSN, "https://*.ingest.us.sentry.io");
const mapHosts = "https://tiles.openfreemap.org https://server.arcgisonline.com https://tile.openstreetmap.org";
const frameAncestors = ["'self'", "https://well.mcmaster.ca", "https://www.well.mcmaster.ca"]
  .concat(dev ? ["http://localhost:*", "http://127.0.0.1:*"] : []);

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' https://gc.zgo.at${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  `img-src 'self' data: blob: ${mapHosts} ${goatCounter}`,
  `connect-src 'self' ${mapHosts} ${goatCounter} ${sentry}`,
  "worker-src 'self' blob:",
  "frame-src 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  `frame-ancestors ${frameAncestors.join(" ")}`,
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false, // no "X-Powered-By: Next.js"
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [320, 375, 430, 640, 768, 820, 992, 1200, 1440, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 180, 256, 384],
  },
  // Inlines FLASK_API_URL (the backend's internal address) at build time. Only the server-side API routes in
  // src/pages/api read it; no browser code does.
  env: {
    FLASK_API_URL: process.env.FLASK_API_URL,
  },
};

// Sentry error reporting (src/lib/sentry.ts). The build talks to nothing: no source maps are uploaded (that would
// need an auth token), no release is created, and the SDK's build telemetry is off. The code for tracing and
// session replay, which the dashboard doesn't use, is left out of the bundle.
export default withSentryConfig(nextConfig, {
  silent: true,
  telemetry: false,
  sourcemaps: { disable: true },
  release: { create: false, finalize: false },
  bundleSizeOptimizations: {
    excludeDebugStatements: true,
    excludeTracing: true,
    excludeReplayIframe: true,
    excludeReplayShadowDom: true,
    excludeReplayWorker: true,
  },
});
