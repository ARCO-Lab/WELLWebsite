// Shared helper for the Next.js API routes that proxy the Flask backend.
// It passes the backend's status, body bytes and selected headers through unchanged, so the user sees the
// backend's real answer (e.g. a 400 validation message or a 404) instead of a generic 500. The body is streamed,
// not parsed or buffered: large responses don't sit in the memory of the one Node process serving every visitor,
// and Next's res.send(Buffer) (which JSON-stringifies the whole buffer to make an ETag) is avoided.
// It stops waiting for the backend if the browser goes away, and answers 502 only when the backend can't be reached.

import { Readable } from "stream";
import { pipeline } from "stream/promises";
import type { NextApiRequest, NextApiResponse } from "next";

// Headers worth forwarding; Content-Disposition and Content-Length matter for CSV downloads.
const FORWARDED_HEADERS = ["content-type", "content-disposition", "content-length"];

const UNREACHABLE = { error: "The data service didn't respond. Please try again." };

// The visitor's IP address, for the backend's per-visitor limits (queued exports). The site's reverse proxy
// appends the address it saw to X-Forwarded-For, so its last entry is the real one; earlier entries are whatever
// the browser sent. Without the header (a direct request, as in development) it's the address of the connection.
export function clientIp(req: NextApiRequest): string {
  const header = req.headers["x-forwarded-for"];
  const hops = (Array.isArray(header) ? header.join(",") : header || "")
    .split(",")
    .map((hop) => hop.trim())
    .filter(Boolean);
  return hops[hops.length - 1] || req.socket?.remoteAddress || "";
}

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

  let response: Response;
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let first: ReadableStreamReadResult<Uint8Array> | undefined;
  try {
    // The backend has no public port, so this header (one entry, replacing any the browser sent) is the only
    // client address it sees.
    const headers = new Headers(init.headers);
    const ip = clientIp(req);
    if (ip) headers.set("X-Forwarded-For", ip);
    response = await fetch(`${process.env.FLASK_API_URL}${path}`, { ...init, headers, signal: upstream.signal });
    // Read the first chunk before sending anything, so a backend that fails this early still gets a clean 502.
    reader = response.body?.getReader();
    first = reader ? await reader.read() : undefined;
  } catch (error) {
    if (upstream.signal.aborted) return; // the client left; nothing to answer
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    upstream.abort();
    return res.status(502).json(UNREACHABLE);
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
