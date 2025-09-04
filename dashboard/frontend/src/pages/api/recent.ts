import type { NextApiRequest, NextApiResponse } from 'next';

// This file defines the Next.js API route for proxying requests to fetch the most recent sampling data from the Flask backend.
// It simply forwards the request and returns the backend response.

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        // Forward the request to the Flask backend's /api/recent endpoint
        const flaskUrl = `${process.env.FLASK_API_URL}/api/recent`;
        const response = await fetch(flaskUrl);

        if (!response.ok) {
            throw new Error(`Flask backend returned status ${response.status}`);
        }

        const data = await response.json();
        return res.status(200).json(data);
    } catch (error: any) {
        console.error("[ERROR] Failed to fetch recent sampling data from Flask backend:", error);
        return res.status(500).json({ error: "Failed to fetch recent sampling data from backend" });
    }
}
