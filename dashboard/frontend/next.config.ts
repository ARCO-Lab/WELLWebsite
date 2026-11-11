/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [320, 375, 430, 640, 768, 820, 992, 1200, 1440, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 180, 256, 384],
  },
  // Add this section to expose basePath to the client
  env: {
    FLASK_API_URL: process.env.FLASK_API_URL,
  },
};

export default nextConfig;