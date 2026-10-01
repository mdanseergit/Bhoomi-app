/** @type {import('next').NextConfig} */
const API_PROXY_TARGET = process.env.NEXT_PUBLIC_API_URL || process.env.BHOOMI_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  images: {
    // Allow Next.js Image to serve the local logo
    unoptimized: false,
  },
  webpack: (config, { dev }) => {
    if (dev) {
      config.cache = false;
    }
    return config;
  },
  async rewrites() {
    // The browser only ever talks to same-origin `/api/*` paths; Next.js
    // proxies them server-side to the FastAPI backend. This keeps API
    // secrets/base URLs out of client bundles and works correctly behind
    // the sandboxed preview proxy (no client-side calls to localhost).
    return [
      {
        source: "/api/:path*",
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
