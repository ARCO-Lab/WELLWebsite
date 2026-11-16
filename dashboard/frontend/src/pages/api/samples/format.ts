// Public, cross-origin endpoint that returns the canonical sampling columns, sites and parameters (the Flask
// backend's /api/samples/format, read straight from utils/sampling_csv). The researcher upload guide on the
// WordPress site renders its reference tables from this, so those tables come from the same lists the import checks
// against and can never drift. CORS is opened to the WordPress origin alone (lib/publicCors).

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";
import { handlePublicCors } from "@/lib/publicCors";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (handlePublicCors(req, res, "GET, OPTIONS")) return;
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET, OPTIONS");
    return res.status(405).json({ error: "Method not allowed" });
  }
  return proxyToBackend(req, res, "/api/samples/format", {}, "sampling format");
}
