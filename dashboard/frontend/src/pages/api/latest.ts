// This file defines the Next.js API route for proxying requests to fetch the latest sensor metrics from the Flask backend.
// It forwards the request and passes the backend's status and body through unchanged.

import type { NextApiRequest, NextApiResponse } from 'next';
import { proxyToBackend } from '@/lib/proxyBackend';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    return proxyToBackend(req, res, "/api/latest", {}, "latest data");
}
