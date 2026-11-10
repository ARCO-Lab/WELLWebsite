// This file defines the Next.js API route for proxying sensor data requests to the Flask backend.
// It translates frontend group toggles to backend group_type filters and forwards date range parameters.
// The backend's status and body are passed through as-is: parsing and re-serializing a large JSON payload here
// blocked the single Node process that serves every visitor, and turned errors like 413 into a generic 500.

import type { NextApiRequest, NextApiResponse } from "next";

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

  // Stop waiting for the backend if the browser goes away (e.g. the user picked another range).
  const upstream = new AbortController();
  res.on("close", () => {
    if (!res.writableEnded) upstream.abort();
  });

  try {
    const flaskUrl = `${process.env.FLASK_API_URL}/api/data?${params.toString()}`;
    const response = await fetch(flaskUrl, { signal: upstream.signal });
    const body = Buffer.from(await response.arrayBuffer());
    res.status(response.status);
    res.setHeader("Content-Type", response.headers.get("content-type") ?? "application/json");
    return res.send(body);
  } catch (error: any) {
    if (upstream.signal.aborted) return; // the client left; nothing to answer
    console.error("[ERROR] Failed to fetch data from Flask backend:", error);
    return res.status(502).json({ error: "The data service didn't respond. Please try again." });
  }
}
