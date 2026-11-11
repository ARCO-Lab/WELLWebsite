// This file defines the Next.js API route that downloads a finished export job's CSV from the Flask backend.
// The backend's status, body and download headers are passed through unchanged; the CSV is streamed.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export const config = {
  api: {
    // Export files can be hundreds of MB; stream them without the large-body warning.
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

  return proxyToBackend(req, res, `/api/exports/jobs/${encodeURIComponent(jobId)}/download`, {}, "export download");
}
