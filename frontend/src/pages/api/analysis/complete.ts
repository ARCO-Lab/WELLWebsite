import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const sampleAnalysis = {
    analysis: "**SAMPLE:**\n- **Complete:** Sample complete sample complete sample complete"
  };

  return res.status(200).json(sampleAnalysis);
}
