// Shared helper for the Next.js API routes that proxy the Flask backend.
// It passes the backend's status, body bytes and selected headers through unchanged, so the user sees the
// backend's real answer (e.g. a 400 validation message or a 404) instead of a generic 500. The body is streamed,
// not parsed or buffered: large CSV exports don't sit in the memory of the one Node process serving every visitor.
// It stops waiting for the backend if the browser goes away, and answers 502 only when the backend can't be reached.

import { Readable } from "stream";
import { pipeline } from "stream/promises";
import type { NextApiRequest, NextApiResponse } from "next";

// Headers worth forwarding; Content-Disposition and Content-Length matter for CSV downloads.
const FORWARDED_HEADERS = ["content-type", "content-disposition", "content-length"];

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
  try {
    response = await fetch(`${process.env.FLASK_API_URL}${path}`, { ...init, signal: upstream.signal });
  } catch (error) {
    if (upstream.signal.aborted) return; // the client left; nothing to answer
    console.error(`[ERROR] Failed to reach the Flask backend for ${label}:`, error);
    return res.status(502).json({ error: "The data service didn't respond. Please try again." });
  }

  res.status(response.status);
  // fetch decompresses encoded bodies, so the backend's length would be wrong for them.
  const encoded = response.headers.has("content-encoding");
  for (const name of FORWARDED_HEADERS) {
    if (name === "content-length" && encoded) continue;
    const value = response.headers.get(name);
    if (value !== null) res.setHeader(name, value);
  }

  if (!response.body) {
    res.end();
    return;
  }
  try {
    await pipeline(Readable.fromWeb(response.body as any), res);
  } catch (error) {
    // The headers are already sent, so the only option is to cut the response short.
    if (!upstream.signal.aborted) console.error(`[ERROR] Backend response for ${label} broke off:`, error);
    upstream.abort();
    res.destroy();
  }
}
