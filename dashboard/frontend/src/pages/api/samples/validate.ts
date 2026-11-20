// Public, cross-origin endpoint for the researcher upload guide's "Check my CSV format" tool (the page lives on the
// WordPress site). It proxies the CSV text to the Flask backend's /api/samples/validate, which runs the real import
// validator (utils/sampling_csv) and returns every format problem with its row and column. The backend only checks:
// nothing is stored and no database is touched. CORS is opened to the WordPress origin alone (lib/publicCors).

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";
import { handlePublicCors } from "@/lib/publicCors";

export const config = {
  api: {
    // A CSV, not a tiny JSON object. The backend caps the text at 2 MB and answers 413 beyond that; this keeps Next
    // from rejecting a normal-sized file first.
    bodyParser: { sizeLimit: "3mb" },
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (handlePublicCors(req, res)) return;
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const body = req.body as { csv?: unknown } | undefined;
  const csv = typeof body?.csv === "string" ? body.csv : "";
  if (!csv.trim()) {
    return res.status(400).json({ error: "Paste your CSV, or choose a file, then press Check." });
  }

  return proxyToBackend(
    req,
    res,
    "/api/samples/validate",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv }) },
    "sampling validate"
  );
}
