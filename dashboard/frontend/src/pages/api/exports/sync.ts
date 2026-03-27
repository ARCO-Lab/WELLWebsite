import type { NextApiRequest, NextApiResponse } from "next";

export const config = {
  api: {
    responseLimit: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const flaskUrl = `${process.env.FLASK_API_URL}/api/exports/sync`;
    const response = await fetch(flaskUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body || {}),
    });

    if (!response.ok) {
      const textBody = await response.text();
      let errorMessage = "Failed to generate sync export";

      try {
        const payload = JSON.parse(textBody);
        errorMessage = payload.error || errorMessage;
      } catch {
        if (textBody && textBody.trim()) {
          errorMessage = textBody.trim().slice(0, 500);
        }
      }

      return res.status(response.status).json({ error: errorMessage });
    }

    const disposition = response.headers.get("content-disposition") || "attachment; filename=well_export.csv";
    const contentType = response.headers.get("content-type") || "text/csv";
    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Disposition", disposition);
    return res.status(200).send(buffer);
  } catch (error) {
    console.error("[ERROR] Export sync proxy failed:", error);
    return res.status(500).json({ error: "Failed to generate sync export" });
  }
}
