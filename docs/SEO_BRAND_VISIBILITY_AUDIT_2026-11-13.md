# Aqlyra AI — Brand Search and AI Discovery Audit
**Date:** 2026-11-13 (JST)  
**Production canonical:** https://aqlyra-ai.vercel.app/  
**Scope:** public search discovery and genuine engineering content; no account/user data, paid SEO services, hidden redirects or marketing promises.

## Problem and actual evidence

- The owner's 13 November **DuckDuckGo** screenshot for the query `aqlyra ai` shows an unrelated `aqlyra.com` trading product, another company, and the Aqlyra GitHub repository, while the official `aqlyra-ai.vercel.app` website is not visible in the captured top results. **This is not a measured Google ranking**, nor proof the official URL is excluded from any index.
- Public search returns `aqlyra.com`, an unrelated trading-automation website that uses the same *Aqlyra* name. Avoid suggesting ownership or affiliation. Independent brand/domain and trademark checks are necessary before a commercial name/domain decision.
- Production pages at `/`, `/about`, `/how-it-works`, `/demo`, `/help` had public HTML, canonical, robot indexing signals, Open Graph metadata, search verification token and internal links. `robots.txt` and `sitemap.xml` were reachable and included existing public URLs. Logged-in and API pages must not become indexable.
- The primary WebSite structured data used `name: Aqlyra`, but product copy often used `Aqlyra AI`. Current search competition makes an accurate, consistent product name more valuable than adding redundant schema or keyword repetition.
- Google Search Console ownership/indexation/impressions and Bing Webmaster search data were **not accessible** in this audit. The verification meta tag and earlier sitemap submission do not prove Google chose the page for indexing or top rank.

## Targeted changes made to existing Vercel frontend release branch

1. **Brand disambiguation:** one existing homepage `WebSite` node, with `name: Aqlyra AI`, an exact canonical home URL and non-misleading alternate names. Reuse existing `WebApplication` node; do **not** create duplicate `WebSite` or fake reviews. Align homepage titles, descriptions, OG and application name.
2. **Useful original evidence:** publish an accessible HTML `/rag-evaluation` page with a clear product explanation, RAG stages, source-linked real experimental figures *only as limited synthetic benchmark results*, private-data boundaries and the actual remaining limitations. Add `TechArticle` structured data and cite the public repository/CI run.
3. **Discoverability without duplication:** link this page from the public home, About and How It Works, and list it in the sitemap as one canonical URL. Existing `/how-it-works` answers actual questions; do not spam duplicate FAQ pages.
4. **Security:** retain private workspace `noindex`, previews `X-Robots-Tag: noindex`, `/api/` robots exclusion, authentication requirements and original Google verification tag.
5. **Regression gates:** test for one and only one homepage Website/WebApplication node, exact brand/URL, public report source links, no private content and consistent sitemap.

## Owner/Search Console steps (one-time verification, not repetitive submissions)

- In the already-used Search Console URL-prefix property `https://aqlyra-ai.vercel.app/`, inspect the homepage and new `/rag-evaluation`. For each, inspect **Page indexing** and **Google-selected canonical**. Use Live Test and Request Indexing if a newly deployed page is not indexed; avoid repeatedly submitting the same unchanged sitemap.
- Check **Pages** for “Crawled – currently not indexed”, “Discovered – currently not indexed”, canonical mismatch, soft 404 or robots problems. **Performance → Search results**: record branded queries `aqlyra ai`, `aqlyra rag ai`, `aqlyra knowledge assistant`, clicks, impressions, CTR, country, device and average position for 28 days.
- Validate `/rag-evaluation` with Google's Rich Results Test and Schema Markup Validator. `TechArticle` and `WebSite` markup do not guarantee a rich result or first rank.
- Use Bing Webmaster Tools to verify the site and submit or import its sitemap if the property is not already present. Search-engine availability and AI mentions must be monitored separately.
- Public ownership/authority: link the official canonical website from the project's GitHub repository (already linked), relevant personal/project profiles, a genuine engineering post with source code/results, and product documentation. Avoid bought backlinks, fabricated claims and doorway pages.
- **Domain strategy:** a dedicated, legally reviewed domain is preferable to an unrelated `vercel.app` address long term, but never migrate, redirect or rename without an agreed new name and verified access. Preserve 301 redirects, canonical consistency and Search Console migration when moving.

## AI assistants: honest expectations

Google AI Overviews/AI Mode, ChatGPT search, Claude web integrations, Bing/Copilot and other assistants do **not** provide a way to force recognition of any new company or rank a URL. Useful publicly readable HTML, clear consistent identity, source links and independent references help their search or retrieval systems find and distinguish Aqlyra, but each system has its own retrieval and indexing controls. No `llms.txt` magic file, fake review schema or training-data injection is required; no one can guarantee an AI answer will cite Aqlyra. The site should not open private documents or discussions to AI crawlers.

## Release and success criteria

- Verify exact GitHub frontend commit and that Vercel production deploy points to it.
- Live anonymous `/`, `/rag-evaluation` and `/sitemap.xml` return success, consistent canonical, indexable status and visible HTML; private routes remain noindex.
- No duplicate JSON-LD WebSite nodes or conflicting canonical links.
- Search Console data is the **ground truth** for Google indexation/rank; DuckDuckGo/Bing are measured separately.
- Target sustained branded-query visibility and correct official-site identification, but **never promise position #1/#2** or AI mention without observations.

## Sources

- [Google: SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)
- [Google: Site Names](https://developers.google.com/search/docs/appearance/site-names)
- [Google: Canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Google: Software app structured data](https://developers.google.com/search/docs/appearance/structured-data/software-app)
- [Aqlyra engineering repository](https://github.com/naim-munshi/aqlyra-rag-ai)
- [Earlier Aqlyra search discovery audit](SEARCH_DISCOVERY_2026-11-09.md)
