// This file defines the Next.js API route for proxying requests to fetch the latest sensor metrics from the Flask backend.
// It simply forwards the request and returns the backend response.

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        // Forward the request to the Flask backend's /api/latest endpoint
        const flaskUrl = `${process.env.FLASK_API_URL}/api/latest`;
        const response = await fetch(flaskUrl);

        if (!response.ok) {
            throw new Error(`Flask backend returned status ${response.status}`);
        }

        const data = await response.json();
        return res.status(200).json(data);
      } catch (error: any) {
        console.error("[ERROR] Failed to fetch latest data from Flask backend:", error);
        return res.status(500).json({ error: "Failed to fetch latest data from backend" });
    }
}