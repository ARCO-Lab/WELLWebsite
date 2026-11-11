// This file defines the Next.js API route that reports an export job's status from the Flask backend.
// The backend's status and body (e.g. its 404 for an unknown job) are passed through unchanged.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { jobId } = req.query;
  if (!jobId || typeof jobId !== "string") {
    return res.status(400).json({ error: "Missing jobId" });
  }

  return proxyToBackend(req, res, `/api/exports/jobs/${encodeURIComponent(jobId)}`, {}, "export status");
}
