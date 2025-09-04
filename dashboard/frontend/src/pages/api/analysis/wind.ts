// This file defines the Next.js API route for proxying wind analysis requests to the Flask backend.
// It forwards subtypes as query parameters and returns the backend response.

import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { subtypes } = req.query;

    const params = new URLSearchParams();
    if (Array.isArray(subtypes)) {
      subtypes.forEach((sub) => params.append("subtypes", sub));
    } else if (subtypes) {
      params.append("subtypes", subtypes as string);
    }

    const flaskUrl = `${process.env.FLASK_API_URL}/api/analysis/wind?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      throw new Error(`Flask backend returned status ${response.status}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch wind analysis from Flask backend:", error);
    return res.status(500).json({ error: "Failed to fetch wind analysis from backend" });
  }
}