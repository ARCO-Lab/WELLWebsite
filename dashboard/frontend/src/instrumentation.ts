// Next.js calls register() once when the server starts. The dashboard has no middleware, so only the Node.js
// runtime needs Sentry (src/sentry.server.config.ts).
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
}

// Reports errors thrown while the server renders a page or runs an API route.
export const onRequestError = Sentry.captureRequestError;
