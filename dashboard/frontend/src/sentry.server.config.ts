// Starts Sentry error reporting in the dashboard's Node.js server: page rendering and the /api routes that proxy
// the backend (settings in src/lib/sentry.ts). Loaded by src/instrumentation.ts.
import * as Sentry from "@sentry/nextjs";
import { sentryOptions } from "@/lib/sentry";

Sentry.init(sentryOptions);
