/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Add this section to expose basePath to the client
  env: {
    FLASK_API_URL: process.env.FLASK_API_URL,
  },
  // Disable API response size limit
  api: {
    responseLimit: false,
  },
  // temporarily ignore errors during builds
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;