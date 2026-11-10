// This file defines the Next.js API route for /api/series: chart-ready sensor series, aggregated by the Flask
// backend (see dashboard/backend/app/api/routes/series.py). It translates the frontend's group toggles to
// group_type filters and passes the backend's status and body through unchanged.

import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { start, end, weather, quality, gauges } = req.query;

  const params = new URLSearchParams();
  if (typeof start === "string") params.append("start", start);
  if (typeof end === "string") params.append("end", end);
  if (weather === "true") params.append("group_type", "Weather");
  if (quality === "true") params.append("group_type", "Quality");
  if (gauges === "true") params.append("group_type", "Logger");

  if (!params.get("start") || !params.get("end") || !params.has("group_type")) {
    return res.status(400).json({ error: "Missing or invalid query parameters" });
  }

  // Stop waiting for the backend if the browser goes away (e.g. the user zoomed again).
  const upstream = new AbortController();
  res.on("close", () => {
    if (!res.writableEnded) upstream.abort();
  });

  try {
    const response = await fetch(`${process.env.FLASK_API_URL}/api/series?${params.toString()}`, { signal: upstream.signal });
    const body = Buffer.from(await response.arrayBuffer());
    res.status(response.status);
    res.setHeader("Content-Type", response.headers.get("content-type") ?? "application/json");
    return res.send(body);
  } catch (error: any) {
    if (upstream.signal.aborted) return;
    console.error("[ERROR] Failed to fetch series from Flask backend:", error);
    return res.status(502).json({ error: "The data service didn't respond. Please try again." });
  }
}
