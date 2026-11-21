// Public, cross-origin endpoint for the researcher upload guide's "Check my CSV format" tool (the page lives on the
// WordPress site). It proxies the CSV text to the Flask backend's /api/samples/validate, which runs the real import
// validator (utils/sampling_csv) and returns every format problem with its row and column. The backend only checks:
// nothing is stored and no database is touched. CORS is opened to the WordPress origin alone (lib/publicCors).
//
// The body is read and parsed here, with Next's own body parser turned off (see config). Next's parser answers a
// malformed or oversized body with a bare text/HTML error ("Invalid JSON", "Body exceeded ... limit") and no CORS
// header, thrown before this handler runs; the checker calls res.json() on the reply, so that error reads as "the
// checker couldn't read that one" rather than a real result (and Sentry logs an uncaught "Invalid JSON"). Parsing it
// ourselves lets every reply be JSON, for any input.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";
import { handlePublicCors } from "@/lib/publicCors";

export const config = {
  api: {
    // Off: see the note above. We read the body below and always answer JSON. The backend caps the CSV at 2 MB and
    // answers a kind 413 beyond that, so this slightly larger cap lets a normal-sized file reach it first; only a
    // body too large to buffer safely is turned away here.
    bodyParser: false,
  },
};

// The most a request body may be before this route turns it away (a touch above the backend's 2 MB CSV cap, so the
// backend's own kinder 413 handles the 2-3 MB band). A sampling CSV is a few KB to a few hundred KB.
const MAX_BODY_BYTES = 3_000_000;

/** The request body as bytes, or null if it runs past MAX_BODY_BYTES (the rest of the stream is then left unread). */
async function readBody(req: NextApiRequest): Promise<Buffer | null> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = typeof chunk === "string" ? Buffer.from(chunk) : (chunk as Buffer);
    total += buf.length;
    if (total > MAX_BODY_BYTES) return null;
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (handlePublicCors(req, res)) return;
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const raw = await readBody(req);
  if (raw === null) {
    return res.status(413).json({
      error: "That file is too large to check here (the limit is 3000 KB). A sampling CSV is normally far smaller; "
        + "check the columns, or upload it to Borealis, which checks the file in full.",
    });
  }

  let payload: unknown;
  try {
    // An empty body is an empty object, so it falls through to the "paste your CSV" message below, not a parse error.
    payload = JSON.parse(raw.toString("utf-8").trim() || "{}");
  } catch {
    return res.status(400).json({ error: "Send the CSV as JSON {\"csv\": \"<file text>\"}." });
  }

  const csv = typeof (payload as { csv?: unknown })?.csv === "string" ? (payload as { csv: string }).csv : "";
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
