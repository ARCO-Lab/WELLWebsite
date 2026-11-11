// Starts Sentry error reporting in the browser (settings in src/lib/sentry.ts). Next.js runs this file before the
// app's own code.
import * as Sentry from "@sentry/nextjs";
import { sentryOptions } from "@/lib/sentry";

Sentry.init(sentryOptions);
