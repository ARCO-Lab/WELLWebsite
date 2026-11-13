// Starts Sentry error reporting in the browser (settings in src/lib/sentry.ts). Next.js runs this file before the
// app's own code.
//
// The SDK (about 95 KB compressed) is loaded once the page has drawn and the browser is idle, in a chunk of its own,
// so it doesn't hold up the first paint. Errors thrown before then are kept (up to 10, lib/earlyErrors.ts) and
// reported once it has started. Without a DSN (next dev, CI) it isn't loaded at all.
import { sentryOptions } from "@/lib/sentry";
import { bufferEarlyErrors } from "@/lib/earlyErrors";

if (sentryOptions.dsn && typeof window !== "undefined") {
  const early = bufferEarlyErrors(window, 10);

  const startSentry = () => {
    import("@sentry/nextjs")
      .then((Sentry) => {
        Sentry.init(sentryOptions);
        early.flush((error) => Sentry.captureException(error));
      })
      .catch(() => {
        // The chunk failed to load (offline, blocked): the dashboard works without error reporting.
        early.flush(() => {});
      });
  };

  const whenIdle = () => {
    if ("requestIdleCallback" in window) window.requestIdleCallback(startSentry, { timeout: 5000 });
    else setTimeout(startSentry, 2000);
  };
  if (document.readyState === "complete") whenIdle();
  else window.addEventListener("load", whenIdle, { once: true });
}
