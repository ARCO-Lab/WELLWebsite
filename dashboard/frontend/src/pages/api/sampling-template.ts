// Proxies the sampling CSV template (the backend's /api/samples/template.csv) for the link on the Ancaster
// Watershed tab. The file and its format (docs/sampling-csv-format.md) live with the backend's validator.

import type { NextApiRequest, NextApiResponse } from "next";
import { proxyToBackend } from "@/lib/proxyBackend";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  return proxyToBackend(req, res, "/api/samples/template.csv", {}, "sampling template");
}
