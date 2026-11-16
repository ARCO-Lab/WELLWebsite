// CORS for the only cross-origin endpoints the dashboard exposes: the sampling format checker that the WordPress
// site's "Sampling data upload" guide calls (/api/samples/validate and /api/samples/format). Every other API route
// is called same-origin by the dashboard's own pages and needs no CORS header at all.
//
// This opens those two routes to the WELL WordPress origin only (https://well.mcmaster.ca, and its www form),
// nothing else, and answers the browser's preflight. Set WORDPRESS_ORIGIN (comma-separated) to override the allowed
// origins, e.g. for a staging site. The endpoints validate text and read fixed lists; they store nothing and touch
// no database, so opening them to the WordPress page is safe.

import type { NextApiRequest, NextApiResponse } from "next";

const DEFAULT_ORIGINS = ["https://well.mcmaster.ca", "https://www.well.mcmaster.ca"];

export function allowedOrigins(): string[] {
  const configured = process.env.WORDPRESS_ORIGIN;
  if (!configured) return DEFAULT_ORIGINS;
  return configured
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

/**
 * Sets the CORS headers when the request's Origin is one we allow, and answers an OPTIONS preflight.
 * Returns true when it has already ended the response (the caller must then return), false when the caller should
 * carry on and serve the request. A request from a disallowed origin gets no Access-Control-Allow-Origin header, so
 * the browser blocks the page from reading the answer; a same-origin or server-to-server caller (no Origin header)
 * is unaffected.
 */
export function handlePublicCors(
  req: NextApiRequest,
  res: NextApiResponse,
  methods = "POST, OPTIONS"
): boolean {
  const origin = req.headers.origin;
  // The answer varies by Origin, so a shared cache must not reuse one origin's response for another.
  res.setHeader("Vary", "Origin");
  if (typeof origin === "string" && allowedOrigins().includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Access-Control-Allow-Methods", methods);
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    res.setHeader("Access-Control-Max-Age", "86400");
  }
  if (req.method === "OPTIONS") {
    // Preflight. An allowed origin gets 204 with the headers above; any other origin gets 204 with none, so the
    // real request the browser would send next never leaves the browser.
    res.status(204).end();
    return true;
  }
  return false;
}
