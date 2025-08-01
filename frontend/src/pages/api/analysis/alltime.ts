// pages/api/analysis.ts
import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { type, subtypes } = req.query;

    if (!type || !["weather", "quality", "logger"].includes(type as string)) {
      return res.status(400).json({ error: "Missing or invalid 'type' parameter" });
    }

    const params = new URLSearchParams();
    params.append("type", type as string);

    if (Array.isArray(subtypes)) {
      subtypes.forEach((sub) => params.append("subtypes", sub));
    } else if (subtypes) {
      params.append("subtypes", subtypes as string);
    }

    const flaskUrl = `${process.env.FLASK_API_URL}/api/analysis/alltime?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      throw new Error(`Flask backend returned status ${response.status}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch analysis from Flask backend:", error);
    return res.status(500).json({ error: "Failed to fetch analysis from backend" });
  }
}
