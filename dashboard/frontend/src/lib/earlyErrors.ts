// Holds on to errors thrown before the Sentry SDK has loaded (src/instrumentation-client.ts loads it once the page is
// idle), so they are still reported once it has: uncaught errors and unhandled promise rejections, at most `max` of
// them. No Sentry or React here, so scripts/earlyErrors.test.mjs can test it with Node.

type Target = Pick<EventTarget, "addEventListener" | "removeEventListener">;

export interface EarlyErrors {
  /** Stops listening and hands each error kept so far to `capture`, oldest first. Later calls do nothing. */
  flush(capture: (error: unknown) => void): void;
}

export function bufferEarlyErrors(target: Target, max = 10): EarlyErrors {
  const kept: unknown[] = [];
  const keep = (error: unknown) => {
    if (kept.length < max && error != null) kept.push(error);
  };
  // An ErrorEvent's error is the thrown value; a cross-origin script error has only a message.
  const onError = (e: Event) => {
    const ev = e as Event & { error?: unknown; message?: string };
    keep(ev.error ?? ev.message);
  };
  const onRejection = (e: Event) => keep((e as Event & { reason?: unknown }).reason);
  target.addEventListener("error", onError);
  target.addEventListener("unhandledrejection", onRejection);

  let flushed = false;
  return {
    flush(capture) {
      if (flushed) return;
      flushed = true;
      target.removeEventListener("error", onError);
      target.removeEventListener("unhandledrejection", onRejection);
      for (const error of kept.splice(0)) capture(error);
    },
  };
}
