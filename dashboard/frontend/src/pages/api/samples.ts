import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Set caching headers to prevent 304 responses
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');

    const { start, end } = req.query;

    if (!start || !end) {
      return res.status(400).json({ error: "Missing start or end date" });
    }

    // Forward all query parameters directly to the Flask backend.
    // This is the same pattern used in data.ts.
    const params = new URLSearchParams(req.query as Record<string, string>);

    const flaskUrl = `${process.env.FLASK_API_URL}/api/samples?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(`Flask backend returned status ${response.status}: ${errorBody}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch samples from Flask backend:", error.message);
    return res.status(500).json({ error: "Failed to fetch samples from backend", details: error.message });
  }
}