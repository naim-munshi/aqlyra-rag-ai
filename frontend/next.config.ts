import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: process.cwd(),
  },
  // These directives work with the existing Next.js hydration/Google sign-in
  // flow; script-src/style-src restrictions require a separately tested nonce
  // strategy and must not be claimed as complete XSS protection.
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        {
          key: "Content-Security-Policy",
          value: "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'",
        },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};

export default nextConfig;
