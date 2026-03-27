import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const flaskUrl = `${process.env.FLASK_API_URL}/api/exports/jobs`;
    const response = await fetch(flaskUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body || {}),
    });

    const payload = await response.json();
    return res.status(response.status).json(payload);
  } catch (error) {
    console.error("[ERROR] Export create job proxy failed:", error);
    return res.status(500).json({ error: "Failed to create export job" });
  }
}
