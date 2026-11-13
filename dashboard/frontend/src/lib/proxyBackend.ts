// Shared helper for the Next.js API routes that proxy the Flask backend.
// It passes the backend's status, body bytes and selected headers through unchanged, so the user sees the
// backend's real answer (e.g. a 400 validation message or a 404) instead of a generic 500. The body is streamed,
// not parsed or buffered: large responses don't sit in the memory of the one Node process serving every visitor,
// and Next's res.send(Buffer) (which JSON-stringifies the whole buffer to make an ETag) is avoided.
// It answers 502 only when the backend can't be reached, and 504 when the backend hasn't started answering within
// BACKEND_TIMEOUT_MS. A visitor over the per-address limits of lib/rateLimit.ts gets a 429 with Retry-After, and the
// backend isn't called.
//
// A request counts against those limits until the backend is done with it, not until the browser goes away: Flask
// can't tell that the browser left while it is still working out an answer, so a visitor who sent slow requests and
// dropped them at once would otherwise keep every backend thread busy while counting as having none in flight. So a
// browser that leaves before the answer has started doesn't end the backend request; the answer is dropped when it
// arrives (or at BACKEND_TIMEOUT_MS). Once the answer is being sent, leaving ends the transfer at once, which the
// backend does notice. No transfer may last longer than BODY_MAX_MS, so a browser reading a download a few bytes at a
// time can't hold a backend thread indefinitely.
//
// The backend is called with node:http, not fetch. The fetch built into Node 22 and 24 (undici 6 and 7) throws an
// uncatchable AssertionError (`assert(!this.paused)`), which ends the whole server, when the backend closes the
// connection while a slow browser has made the proxy pause reading (e.g. a gunicorn worker restarting, or an idle
// connection reaching gunicorn's keep-alive limit). See https://github.com/nodejs/undici/issues/5360. node:http
// pauses and resumes the socket itself, on any Node version.

import http from "http";
import type { ClientRequest, IncomingMessage } from "http";
import { pipeline } from "stream/promises";
import type { NextApiRequest, NextApiResponse } from "next";
import { clientIp, logClientIpSample } from "./clientIp.ts";
import { ClientCounter, RateLimiter, requestKind } from "./rateLimit.ts";

// Headers worth forwarding; Content-Disposition and Content-Length matter for CSV downloads, and Cache-Control
// lets browsers reuse /api/latest and /api/series answers for as long as the backend allows. The body bytes are
// passed on as received, so an encoding the backend applied (it doesn't today) stays valid with its length.
const FORWARDED_HEADERS = [
  "content-type", "content-disposition", "content-length", "content-encoding", "cache-control", "retry-after",
];

// Longer than the backend's own limits (25 s per query, gunicorn's 60 s), so normally the backend answers first
// with its own message. It only covers the wait for the first bytes: a large CSV download may stream for longer.
const BACKEND_TIMEOUT_MS = 65_000;

// Once the body has started, the transfer is dropped if no bytes arrive from the backend for this long. A browser
// that stops reading also counts: with backpressure the proxy stops reading the backend too, so the socket is idle.
const BODY_IDLE_TIMEOUT_MS = 300_000;

// The longest a body may take to send, however steadily it trickles: half an hour is enough for the largest export
// on a slow connection. PROXY_BODY_MAX_MS overrides it (tests use a short one).
function bodyMaxMs(): number {
  const ms = Number(process.env.PROXY_BODY_MAX_MS);
  return Number.isFinite(ms) && ms > 0 ? ms : 30 * 60_000;
}

// Connections to the backend are kept open and reused. An idle one is closed after 5 s, before gunicorn's
// --keep-alive 10 (dashboard/backend/Dockerfile) would, so Node is the side that closes idle connections and a
// request is not sent on one that gunicorn is closing at that moment (which would fail with a 502).
const backendAgent = new http.Agent({ keepAlive: true, timeout: 5_000 });

const UNREACHABLE = { error: "The data service didn't respond. Please try again." };
const TIMED_OUT = { error: "The data service took too long to answer. Please try again." };
const TOO_MANY = { error: "Too many requests from your address. Please wait a moment and try again." };

// One limiter and one address counter for the process, made on first use so the limiter reads the RATE_LIMIT_*
// variables at run time. Kept on globalThis: the build may give each API route its own copy of this module, and the
// limits must be per address across all routes.
type Shared = { limiter: RateLimiter | null; counter: ClientCounter | null };
const shared: Shared = ((globalThis as { __wellProxy?: Shared }).__wellProxy ??= { limiter: null, counter: null });

/** Replaces the process's limiter (tests use it to start from fresh counts or other limits). */
export function setRateLimiter(next: RateLimiter | null): void {
  shared.limiter = next;
}

// What the API routes send to the backend: a method, headers and an optional (JSON) string body.
export type BackendInit = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  // The answer when the backend can't be reached or doesn't answer in time, instead of the usual 502 and 504 (for
  // a route whose callers expect another one, such as /api/health/data's uptime monitor)
  failure?: { status: number; body: unknown };
};

export async function proxyToBackend(
  req: NextApiRequest,
  res: NextApiResponse,
  path: string,
  init: BackendInit = {},
  label = "data"
) {
  // The backend has no public port, so this header (one entry, replacing any the browser sent) is the only
  // client address it sees. See lib/clientIp.ts for which address that is.
  const headers: Record<string, string> = { ...init.headers };
  const ip = clientIp(req);
  logClientIpSample(req, ip);
  shared.counter ??= new ClientCounter(Date.now());
  const counted = shared.counter.record(ip, Date.now());
  if (counted) console.info(counted);

  shared.limiter ??= new RateLimiter();
  const verdict = shared.limiter.check(ip, requestKind(path, init.method));
  if (!verdict.ok) {
    res.setHeader("Retry-After", String(verdict.retryAfterS));
    return res.status(429).json(TOO_MANY);
  }

  if (ip) headers["X-Forwarded-For"] = ip;
  if (init.body !== undefined) headers["Content-Length"] = String(Buffer.byteLength(init.body));

  let upstream: ClientRequest;
  try {
    upstream = http.request(`${process.env.FLASK_API_URL}${path}`, {
      method: init.method || "GET",
      headers,
      agent: backendAgent,
    });
  } catch (error) {
    // An invalid FLASK_API_URL throws here, before any connection is made.
    verdict.release();
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return init.failure ? res.status(init.failure.status).json(init.failure.body) : res.status(502).json(UNREACHABLE);
  }
  // Errors are handled where the request and the body are awaited below; this listener only keeps a late
  // second error (after the first was handled) from being thrown as an uncaught exception.
  upstream.on("error", () => {});
  // The request stops counting as in flight once the backend is done with it: its answer has been read, or the
  // connection to it is closed (see the top of this file)
  upstream.once("close", verdict.release);

  // The browser went away before the whole answer was sent (e.g. a chart dropping a superseded request): stay quiet,
  // as nothing is wrong. While the backend is still working out the answer, it can't notice, so the request is left
  // to finish and its answer dropped when it arrives; once the answer is being sent, the transfer is stopped now.
  let clientLeft = false;
  let answering = false;
  res.on("close", () => {
    if (res.writableFinished) return;
    clientLeft = true;
    if (answering) upstream.destroy();
  });

  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    upstream.destroy();
  }, BACKEND_TIMEOUT_MS);

  let response: IncomingMessage;
  let body: AsyncIterator<Buffer>;
  let first: IteratorResult<Buffer>;
  try {
    response = await new Promise<IncomingMessage>((resolve, reject) => {
      upstream.once("response", resolve);
      upstream.once("error", reject);
      upstream.end(init.body);
    });
    answering = true;
    if (clientLeft) {
      upstream.destroy(); // the backend has done its work; nobody is waiting for the answer
      return;
    }
    // Read the first chunk before sending anything, so a backend that fails this early still gets a clean 502.
    body = response[Symbol.asyncIterator]();
    first = await body.next();
  } catch (error) {
    upstream.destroy();
    if (clientLeft) return; // nothing to answer
    if (timedOut) {
      console.error(`[ERROR] The Flask backend didn't answer within ${BACKEND_TIMEOUT_MS / 1000} s for ${label}`);
      return init.failure ? res.status(init.failure.status).json(init.failure.body) : res.status(504).json(TIMED_OUT);
    }
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return init.failure ? res.status(init.failure.status).json(init.failure.body) : res.status(502).json(UNREACHABLE);
  } finally {
    clearTimeout(timer); // from here on, only the client leaving stops the transfer
  }

  res.status(response.statusCode || 502);
  for (const name of FORWARDED_HEADERS) {
    const value = response.headers[name];
    if (value !== undefined) res.setHeader(name, value);
  }

  if (first.done) {
    res.end();
    return;
  }

  let idle = false;
  upstream.setTimeout(BODY_IDLE_TIMEOUT_MS, () => {
    idle = true;
    upstream.destroy(new Error("backend idle"));
  });
  let tooLong = false;
  const bodyTimer = setTimeout(() => {
    tooLong = true;
    upstream.destroy(new Error("transfer too long"));
  }, bodyMaxMs());

  const firstChunk = first.value;
  const rest = body;
  async function* chunks() {
    yield firstChunk;
    for (;;) {
      const next = await rest.next();
      if (next.done) return;
      yield next.value;
    }
  }

  try {
    // pipeline waits for the browser to take each chunk before reading the next, and stops the backend
    // response (via the generator's return) if the browser goes away.
    await pipeline(chunks, res);
  } catch (error) {
    // Part of the body is already out, so the response can only be cut short.
    if (idle) {
      console.error(`[ERROR] Backend response for ${label} broke off: no data for ${BODY_IDLE_TIMEOUT_MS / 1000} s`);
    } else if (tooLong) {
      console.warn(`[WARN] Response for ${label} stopped: still sending after ${bodyMaxMs() / 1000} s`);
    } else if (!clientLeft) {
      console.error(`[ERROR] Backend response for ${label} broke off:`, error);
    }
    upstream.destroy();
    res.destroy();
  } finally {
    clearTimeout(bodyTimer);
  }
}
