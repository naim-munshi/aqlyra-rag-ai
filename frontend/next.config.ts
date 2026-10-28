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
        // Browser-side defense in depth; keep camera/mic available for
        // consent-driven uploads and LiveKit voice on this origin.
        { key: "Permissions-Policy", value: "geolocation=(), payment=(), usb=(), serial=(), browsing-topics=()" },
        // Vercel serves production over HTTPS. Do not preload or include
        // subdomains while deployment and custom domains are still changing.
        ...(process.env.NODE_ENV === "production"
          ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]
          : []),
      ],
    }];
  },
};

export default nextConfig;
