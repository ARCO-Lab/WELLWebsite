// This file defines the Next.js API route for proxying sensor data requests to the Flask backend.
// It translates frontend group toggles to backend group_type filters and forwards date range parameters.
// The backend's status and body are passed through as-is (see lib/proxyBackend): parsing and re-serializing a large
// JSON payload here blocked the single Node process that serves every visitor, and turned errors like 413 into a
// generic 500.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export const config = {
  api: {
    // The backend caps responses at DATA_MAX_ROWS (about 50 MB of JSON); don't warn about large bodies below that.
    responseLimit: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { start, end, weather, quality, gauges } = req.query;

  // Translate group toggles to group_type filters
  const groupTypes = [];
  if (weather === "true") groupTypes.push("Weather");
  if (quality === "true") groupTypes.push("Quality");
  if (gauges === "true") groupTypes.push("Logger");

  if (!start || !end || groupTypes.length === 0) {
    return res.status(400).json({ error: "Missing or invalid query parameters" });
  }

  // Construct query string for your Flask API
  const params = new URLSearchParams();
  params.append("start", start as string);
  params.append("end", end as string);
  for (const group of groupTypes) {
    params.append("group_type", group);
  }

  return proxyToBackend(req, res, `/api/data?${params.toString()}`, {}, "sensor data");
}
