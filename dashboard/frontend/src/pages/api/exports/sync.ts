// This file defines the Next.js API route that downloads a small export directly as CSV from the Flask backend.
// The backend's status and body (including its validation messages) are passed through unchanged.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export const config = {
  api: {
    // CSV exports can be large; stream them without the large-body warning.
    responseLimit: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  return proxyToBackend(req, res, "/api/exports/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req.body || {}),
  }, "sync export");
}
