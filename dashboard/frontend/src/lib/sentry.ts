// Shared Sentry settings for the dashboard's browser and server code (src/instrumentation-client.ts and
// src/sentry.server.config.ts). Errors only, nothing that identifies a visitor: no performance tracing, no
// session replay, no cookies, headers, query strings or IP addresses.
//
// NEXT_PUBLIC_SENTRY_DSN turns it on. It is set as a build arg in the Dockerfile and inlined into the bundle
// at build time (a browser DSN is public by design: it can only send events). Unset, e.g. in `next dev` or CI,
// nothing is sent.
import type { ErrorEvent } from "@sentry/nextjs";

// The query string of a URL or a path (/api/data?...); the dashboard passes station, date and filter choices there.
const QUERY = /((?:https?:\/\/|\/)[^\s?#'"<>]*)\?[^\s#'"<>]*/g;

function scrubUrls<T>(value: T): T {
  if (typeof value === "string") return value.replace(QUERY, "$1?[Filtered]") as T;
  if (Array.isArray(value)) return value.map(scrubUrls) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, scrubUrls(v)])) as T;
  }
  return value;
}

// Strip what could identify a visitor before an event leaves the browser or the server.
export function beforeSend(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    // Keep only the method and the page or API path that failed.
    const { method, url } = event.request;
    event.request = { method, url: url?.split("?")[0] };
  }
  if (event.user) {
    delete event.user.ip_address;
  }
  return scrubUrls(event);
}

export const sentryOptions = {
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "production",
  sendDefaultPii: false,
  tracesSampleRate: 0, // errors only
  replaysSessionSampleRate: 0, // no session replay (the replay integration isn't added either)
  replaysOnErrorSampleRate: 0,
  beforeSend,
  // Breadcrumbs of fetches and page changes carry full URLs; drop their query strings too.
  beforeBreadcrumb: scrubUrls,
};
