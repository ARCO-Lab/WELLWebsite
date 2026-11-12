// This file defines the Next.js API route for /api/series: chart-ready sensor series, aggregated by the Flask
// backend (see dashboard/backend/app/api/routes/series.py). It translates the frontend's group toggles to
// group_type filters, forwards a chart's own bucket and series filters, and passes the backend's status and body
// through unchanged (see lib/proxyBackend).

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

const list = (v: string | string[] | undefined) => (v === undefined ? [] : Array.isArray(v) ? v : [v]);

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { start, end, weather, quality, gauges, bucket } = req.query;

  const params = new URLSearchParams();
  if (typeof start === "string") params.append("start", start);
  if (typeof end === "string") params.append("end", end);
  if (weather === "true") params.append("group_type", "Weather");
  if (quality === "true") params.append("group_type", "Quality");
  if (gauges === "true") params.append("group_type", "Logger");
  if (typeof bucket === "string") params.append("bucket", bucket);
  for (const name of ["series", "station_id", "measurement_type"]) {
    for (const value of list(req.query[name])) params.append(name, value);
  }

  // The backend checks the values; here only that there is something to ask for
  if (!params.get("start") || !params.get("end") || !(params.has("group_type") || params.has("series"))) {
    return res.status(400).json({ error: "Missing or invalid query parameters" });
  }

  return proxyToBackend(req, res, `/api/series?${params.toString()}`, {}, "chart series");
}
