import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const response = await fetch("http://localhost:5000/api/weather");
  const data = await response.json();
  res.status(200).json(data);
}
