import type { MetadataRoute } from "next";

const SITE_URL = "https://aqlyra-ai.vercel.app";

/**
 * Only the public product pages are eligible for discovery. Actual account
 * content is authenticated and inherits noindex metadata.
 *
 * Google must be able to crawl an accessible noindex page to see its tag,
 * so do not blanket-disallow /login or /study-abroad here.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: "/api/",
    },
    sitemap: SITE_URL + "/sitemap.xml",
  };
}
