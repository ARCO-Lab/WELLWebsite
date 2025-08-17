/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Add this section to expose basePath to the client
  env: {
    FLASK_API_URL: process.env.FLASK_API_URL,
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