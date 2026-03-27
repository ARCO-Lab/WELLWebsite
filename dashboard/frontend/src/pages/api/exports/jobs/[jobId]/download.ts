import type { NextApiRequest, NextApiResponse } from "next";

export const config = {
  api: {
    responseLimit: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { jobId } = req.query;
  if (!jobId || typeof jobId !== "string") {
    return res.status(400).json({ error: "Missing jobId" });
  }

  try {
    const flaskUrl = `${process.env.FLASK_API_URL}/api/exports/jobs/${encodeURIComponent(jobId)}/download`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      const payload = await response.json();
      return res.status(response.status).json(payload);
    }

    const disposition = response.headers.get("content-disposition") || "attachment; filename=well_export.csv";
    const contentType = response.headers.get("content-type") || "text/csv";
    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Disposition", disposition);
    return res.status(200).send(buffer);
  } catch (error) {
    console.error("[ERROR] Export download proxy failed:", error);
    return res.status(500).json({ error: "Failed to download export artifact" });
  }
}
