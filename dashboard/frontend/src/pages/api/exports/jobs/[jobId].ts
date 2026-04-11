import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { jobId } = req.query;
  if (!jobId || typeof jobId !== "string") {
    return res.status(400).json({ error: "Missing jobId" });
  }

  try {
    const flaskUrl = `${process.env.FLASK_API_URL}/api/exports/jobs/${encodeURIComponent(jobId)}`;
    const response = await fetch(flaskUrl);
    const payload = await response.json();
    return res.status(response.status).json(payload);
  } catch (error) {
    console.error("[ERROR] Export status proxy failed:", error);
    return res.status(500).json({ error: "Failed to fetch export status" });
  }
}
