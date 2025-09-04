// This file defines the Next.js API route for proxying 'recent' analysis requests to the Flask backend.
// It maps frontend group types to backend types and forwards query parameters.

import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { type, subtypes } = req.query;

    // FIX: Map the frontend 'gauges' type to the backend 'logger' type.
    let backendType = type;
    if (type === 'gauges') {
      backendType = 'logger';
    }

    // Now, validate the mapped type.
    if (!backendType || !["weather", "quality", "logger"].includes(backendType as string)) {
      return res.status(400).json({ error: "Missing or invalid 'type' parameter" });
    }

    const params = new URLSearchParams();
    // Use the potentially mapped type when forwarding the request.
    params.append("type", backendType as string);

    if (Array.isArray(subtypes)) {
      subtypes.forEach((sub) => params.append("subtypes", sub));
    } else if (subtypes) {
      params.append("subtypes", subtypes as string);
    }

    const flaskUrl = `${process.env.FLASK_API_URL}/api/analysis/recent?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Flask backend returned status ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch recent analysis from Flask backend:", error);
    return res.status(500).json({ error: "Failed to fetch analysis from backend" });
  }
}