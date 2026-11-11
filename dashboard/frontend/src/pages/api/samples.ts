// This file defines the Next.js API route for proxying creek sampling data requests to the Flask backend.
// It forwards all query parameters, disables caching to ensure fresh data, and passes the backend's status and
// body through unchanged.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export const config = {
  api: {
    // Long ranges return several MB of JSON; don't warn about large bodies.
    responseLimit: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Set caching headers to prevent 304 responses
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');

  const { start, end } = req.query;

  if (!start || !end) {
    return res.status(400).json({ error: "Missing start or end date" });
  }

  // Forward all query parameters directly to the Flask backend.
  const params = new URLSearchParams(req.query as Record<string, string>);

  return proxyToBackend(req, res, `/api/samples?${params.toString()}`, {}, "samples");
}
