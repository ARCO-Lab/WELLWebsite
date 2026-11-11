// Shared helper for the Next.js API routes that proxy the Flask backend.
// It passes the backend's status, body bytes and selected headers through unchanged, so the user sees the
// backend's real answer (e.g. a 400 validation message or a 404) instead of a generic 500. The body is streamed,
// not parsed or buffered: large responses don't sit in the memory of the one Node process serving every visitor,
// and Next's res.send(Buffer) (which JSON-stringifies the whole buffer to make an ETag) is avoided.
// It stops waiting for the backend if the browser goes away, answers 502 only when the backend can't be reached,
// and 504 when the backend hasn't started answering within BACKEND_TIMEOUT_MS.

import { Readable } from "stream";
import { pipeline } from "stream/promises";
import type { NextApiRequest, NextApiResponse } from "next";
import { clientIp, logClientIpSample } from "./clientIp";

// Headers worth forwarding; Content-Disposition and Content-Length matter for CSV downloads, and Cache-Control
// lets browsers reuse /api/latest and /api/series answers for as long as the backend allows.
const FORWARDED_HEADERS = ["content-type", "content-disposition", "content-length", "cache-control"];

// Longer than the backend's own limits (25 s per query, gunicorn's 60 s), so normally the backend answers first
// with its own message. It only covers the wait for the first bytes: a large CSV download may stream for longer.
const BACKEND_TIMEOUT_MS = 65_000;

const UNREACHABLE = { error: "The data service didn't respond. Please try again." };
const TIMED_OUT = { error: "The data service took too long to answer. Please try again." };

export async function proxyToBackend(
  req: NextApiRequest,
  res: NextApiResponse,
  path: string,
  init: RequestInit = {},
  label = "data"
) {
  const upstream = new AbortController();
  res.on("close", () => {
    if (!res.writableEnded) upstream.abort();
  });

  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), BACKEND_TIMEOUT_MS);

  let response: Response;
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let first: ReadableStreamReadResult<Uint8Array> | undefined;
  try {
    // The backend has no public port, so this header (one entry, replacing any the browser sent) is the only
    // client address it sees. See lib/clientIp.ts for which address that is.
    const headers = new Headers(init.headers);
    const ip = clientIp(req);
    logClientIpSample(req, ip);
    if (ip) headers.set("X-Forwarded-For", ip);
    response = await fetch(`${process.env.FLASK_API_URL}${path}`, {
      ...init,
      headers,
      signal: AbortSignal.any([upstream.signal, deadline.signal]),
    });
    // Read the first chunk before sending anything, so a backend that fails this early still gets a clean 502.
    reader = response.body?.getReader();
    first = reader ? await reader.read() : undefined;
  } catch (error) {
    if (upstream.signal.aborted) return; // the client left; nothing to answer
    upstream.abort();
    if (deadline.signal.aborted) {
      console.error(`[ERROR] The Flask backend didn't answer within ${BACKEND_TIMEOUT_MS / 1000} s for ${label}`);
      return res.status(504).json(TIMED_OUT);
    }
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return res.status(502).json(UNREACHABLE);
  } finally {
    clearTimeout(timer); // from here on, only the client leaving stops the transfer
  }

  res.status(response.status);
  // fetch decompresses encoded bodies, so the backend's length would be wrong for them.
  const encoded = response.headers.has("content-encoding");
  for (const name of FORWARDED_HEADERS) {
    if (name === "content-length" && encoded) continue;
    const value = response.headers.get(name);
    if (value !== null) res.setHeader(name, value);
  }

  if (!reader || !first || first.done) {
    res.end();
    return;
  }

  const bodyReader = reader;
  const firstChunk = first.value;
  async function* chunks() {
    try {
      yield firstChunk;
      for (;;) {
        const { done, value } = await bodyReader.read();
        if (done) return;
        yield value;
      }
    } catch (error) {
      if (!upstream.signal.aborted) console.error(`[ERROR] Backend response for ${label} broke off:`, error);
      throw error;
    } finally {
      bodyReader.cancel().catch(() => {}); // stop reading the backend if the client went away
    }
  }

  try {
    await pipeline(Readable.from(chunks()), res);
  } catch {
    // The backend or the client went away mid-body; part of it is already out, so the response can only be cut
    // short (pipeline closes it).
    upstream.abort();
    res.destroy();
  }
}
