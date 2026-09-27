/** @type {import('next').NextConfig} */
const withPWA = require("next-pwa")({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
});

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy /api/* to FastAPI so we don't fight CORS in dev.
    const backend = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

module.exports = withPWA(nextConfig);
