// Shared helper for the Next.js API routes that proxy the Flask backend.
// It passes the backend's status, body bytes and selected headers through unchanged, so the user sees the
// backend's real answer (e.g. a 400 validation message or a 404) instead of a generic 500. The body is streamed,
// not parsed or buffered: large responses don't sit in the memory of the one Node process serving every visitor,
// and Next's res.send(Buffer) (which JSON-stringifies the whole buffer to make an ETag) is avoided.
// It stops waiting for the backend if the browser goes away, answers 502 only when the backend can't be reached,
// and 504 when the backend hasn't started answering within BACKEND_TIMEOUT_MS.
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

// Headers worth forwarding; Content-Disposition and Content-Length matter for CSV downloads, and Cache-Control
// lets browsers reuse /api/latest and /api/series answers for as long as the backend allows. The body bytes are
// passed on as received, so an encoding the backend applied (it doesn't today) stays valid with its length.
const FORWARDED_HEADERS = ["content-type", "content-disposition", "content-length", "content-encoding", "cache-control"];

// Longer than the backend's own limits (25 s per query, gunicorn's 60 s), so normally the backend answers first
// with its own message. It only covers the wait for the first bytes: a large CSV download may stream for longer.
const BACKEND_TIMEOUT_MS = 65_000;

// Once the body has started, the transfer is dropped if no bytes arrive from the backend for this long. A browser
// that stops reading also counts: with backpressure the proxy stops reading the backend too, so the socket is idle.
const BODY_IDLE_TIMEOUT_MS = 300_000;

// Connections to the backend are kept open and reused. An idle one is closed after 5 s, before gunicorn's
// --keep-alive 10 (dashboard/backend/Dockerfile) would, so Node is the side that closes idle connections and a
// request is not sent on one that gunicorn is closing at that moment (which would fail with a 502).
const backendAgent = new http.Agent({ keepAlive: true, timeout: 5_000 });

const UNREACHABLE = { error: "The data service didn't respond. Please try again." };
const TIMED_OUT = { error: "The data service took too long to answer. Please try again." };

// What the API routes send to the backend: a method, headers and an optional (JSON) string body.
export type BackendInit = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
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
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return res.status(502).json(UNREACHABLE);
  }
  // Errors are handled where the request and the body are awaited below; this listener only keeps a late
  // second error (after the first was handled) from being thrown as an uncaught exception.
  upstream.on("error", () => {});

  // The browser went away before the whole answer was sent (e.g. a chart dropping a superseded request): stop
  // the backend request and stay quiet, as nothing is wrong.
  let clientLeft = false;
  res.on("close", () => {
    if (res.writableFinished) return;
    clientLeft = true;
    upstream.destroy();
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
    // Read the first chunk before sending anything, so a backend that fails this early still gets a clean 502.
    body = response[Symbol.asyncIterator]();
    first = await body.next();
  } catch (error) {
    upstream.destroy();
    if (clientLeft) return; // nothing to answer
    if (timedOut) {
      console.error(`[ERROR] The Flask backend didn't answer within ${BACKEND_TIMEOUT_MS / 1000} s for ${label}`);
      return res.status(504).json(TIMED_OUT);
    }
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return res.status(502).json(UNREACHABLE);
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
    } else if (!clientLeft) {
      console.error(`[ERROR] Backend response for ${label} broke off:`, error);
    }
    upstream.destroy();
    res.destroy();
  }
}
