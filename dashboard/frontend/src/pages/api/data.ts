// This file defines the Next.js API route for proxying sensor data requests to the Flask backend.
// It translates frontend group toggles to backend group_type filters and forwards date range parameters.

import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
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

    const flaskUrl = `${process.env.FLASK_API_URL}/api/data?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      throw new Error(`Flask backend returned status ${response.status}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch data from Flask backend:", error);
    return res.status(500).json({ error: "Failed to fetch data from backend" });
  }
}
