// This file defines /api/health/data, which passes the Flask backend's /health/data check through unchanged
// (the backend isn't reachable from outside), so an external uptime monitor can watch
// https://welldash.mcmaster.ca/api/health/data: 200 when every live series is fresh, 503 otherwise.

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    res.setHeader('Cache-Control', 'no-store');
    try {
        const response = await fetch(`${process.env.FLASK_API_URL}/health/data`, {
            signal: AbortSignal.timeout(15000),
        });
        const body = await response.json();
        // Keep the backend's status: 503 with the list of stale series is the answer, not an error here.
        return res.status(response.status).json(body);
    } catch (error) {
        console.error('[ERROR] /api/health/data could not reach the backend:', error);
        return res.status(503).json({ status: 'error', error: 'backend unreachable' });
    }
}
