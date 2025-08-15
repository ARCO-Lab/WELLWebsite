import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // This version reads 'type' directly, which can be a single group or an array of groups.
    const { type, subtypes, dashboardTab } = req.query;

    // Validate that 'type' exists. This is the list of active groups.
    if (!type) {
      return res.status(400).json({ error: "No active groups selected. The 'type' parameter is missing." });
    }

    const params = new URLSearchParams();

    // Ensure 'type' is an array, then process each active group.
    const activeTypes = Array.isArray(type) ? type : [type];
    
    if (activeTypes.length === 0) {
        return res.status(400).json({ error: "No active groups selected." });
    }

    activeTypes.forEach(t => {
      // Map 'gauges' to 'logger' for backend consistency, then append.
      const backendType = t === 'gauges' ? 'logger' : t;
      params.append("type", backendType);
    });

    // Handle all selected subtypes, which can also be an array.
    if (subtypes) {
      const subtypeArray = Array.isArray(subtypes) ? subtypes : [subtypes];
      subtypeArray.forEach((sub) => params.append("subtypes", sub));
    }

    // Handle the dashboard tab state.
    if (dashboardTab) {
      params.append("dashboardTab", dashboardTab as string);
    }

    const flaskUrl = `${process.env.FLASK_API_URL}/api/analysis/complete?${params.toString()}`;
    const response = await fetch(flaskUrl);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Flask backend returned status ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    console.error("[ERROR] Failed to fetch complete analysis from Flask backend:", error);
    return res.status(500).json({ error: "Failed to fetch complete analysis from backend" });
  }
}