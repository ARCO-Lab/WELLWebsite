import { withSentryConfig } from "@sentry/nextjs/config";

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
  // temporarily ignore errors during builds
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
};

// Sentry error reporting (src/lib/sentry.ts). The build talks to nothing: no source maps are uploaded (that would
// need an auth token), no release is created, and the SDK's build telemetry is off. The code for tracing and
// session replay, which the dashboard doesn't use, is left out of the bundle.
export default withSentryConfig(nextConfig, {
  silent: true,
  telemetry: false,
  sourcemaps: { disable: true },
  release: { create: false, finalize: false },
  bundleSizeOptimizations: {
    excludeDebugStatements: true,
    excludeTracing: true,
    excludeReplayIframe: true,
    excludeReplayShadowDom: true,
    excludeReplayWorker: true,
  },
});
