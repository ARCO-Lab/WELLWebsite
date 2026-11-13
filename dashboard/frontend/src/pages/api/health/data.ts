// This file defines /api/health/data, which passes the Flask backend's /health/data check through unchanged
// (the backend isn't reachable from outside), so an external uptime monitor can watch
// https://welldash.mcmaster.ca/api/health/data: 200 when every live series is fresh, 503 otherwise (502 or 504 when
// the backend can't be reached or doesn't answer). It goes through lib/proxyBackend like the data routes, so it is
// limited per address too: each check reads the newest reading of every series and the open alerts.

import type { NextApiRequest, NextApiResponse } from 'next';
import { proxyToBackend } from '@/lib/proxyBackend';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    res.setHeader('Cache-Control', 'no-store');
    // The backend's status is kept: a 503 with the list of stale series is the answer, not an error here.
    return proxyToBackend(req, res, '/health/data', {}, 'data health check');
}
