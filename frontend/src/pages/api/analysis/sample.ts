import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const sampleAnalysis = {
    analysis: "**SAMPLE:**\n- **Sample Points:** No analysis available at this time"
  };

  return res.status(200).json(sampleAnalysis);
}
