import type { MetadataRoute } from "next";

const SITE_URL = "https://aqlyra-ai.vercel.app";

/** Never publish routes that render private, account-scoped content. */
export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", "/about", "/demo", "/help"].map((route) => ({
    url: SITE_URL + route,
    changeFrequency: "monthly" as const,
  }));
}
