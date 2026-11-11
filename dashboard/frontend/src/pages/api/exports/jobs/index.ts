// This file defines the Next.js API route that queues a large export job on the Flask backend.
// The backend's status and body (including its validation messages) are passed through unchanged.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  return proxyToBackend(req, res, "/api/exports/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req.body || {}),
  }, "export job creation");
}
