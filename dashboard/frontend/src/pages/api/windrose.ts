// This file defines the Next.js API route for /api/windrose: wind direction × speed counts for the wind rose,
// counted by the Flask backend (see dashboard/backend/app/api/routes/windrose.py). It passes the backend's status
// and body through unchanged (see lib/proxyBackend).

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

const SPEEDS = new Set(["Wind Speed", "Gust Speed"]);

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { start, end, speed } = req.query;

  const params = new URLSearchParams();
  if (typeof start === "string") params.append("start", start);
  if (typeof end === "string") params.append("end", end);
  const speeds = ([] as string[]).concat(speed ?? []);
  for (const s of speeds) params.append("speed", s);

  if (!params.get("start") || !params.get("end") || speeds.some((s) => !SPEEDS.has(s))) {
    return res.status(400).json({ error: "Missing or invalid query parameters" });
  }

  return proxyToBackend(req, res, `/api/windrose?${params.toString()}`, {}, "wind rose");
}
