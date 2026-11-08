# Aqlyra: Google Search, Search Console and AI discovery runbook

**Date:** 2026-11-09. **Official canonical:** https://aqlyra-ai.vercel.app/

## Verified technical baseline (live checks, read-only)

- `GET /robots.txt` returned **200**, allows general public crawling, disallows `/api/` and references the canonical sitemap.
- `GET /sitemap.xml` returned **200**; the previous release listed only `/`, `/about`, `/demo`, `/help`.
- `GET /about` and `GET /` returned **200** with server-rendered crawlable text and `index, follow` metadata, canonical and description. The page also returned Google site verification **meta tag** and JSON-LD software info.
- Other, account-scoped pages inherit **noindex**; preview deployments explicitly return **X-Robots-Tag: noindex**.
- **Not verified**: Search Console property ownership, actual Googlebot indexing, page impressions, keyword rankings, Google AI Overviews/AI Mode citations or an active Google brand knowledge panel. A visible verification tag does **not** prove that Search Console ownership is active.

## This change

- Publish genuinely useful, publicly rendered and self-contained `/how-it-works` page: what Aqlyra is, real RAG retrieval/citations, model/retrieval limitations, privacy boundary, web research, and common user questions.
- Add the URL to the sitemap and link it from the public home, About and Help pages.
- Use consistent `WebApplication` structured data with `BusinessApplication` category and an accurate software project GitHub link, rather than unsupported `ProductivityApplication` category.
- Preserve private documents, personal conversations, API and authentication pages as **non-indexable**. No keyword stuffing, fake ratings, fabricated pricing, doorway pages, indexing of users' uploads, or misleading marketing results.

## Google Search Console — owner action required

1. Open https://search.google.com/search-console with the Google account that controls Aqlyra.
2. Add **URL-prefix property** `https://aqlyra-ai.vercel.app/`, or open the existing property. Use Google's verification workflow; the frontend already includes a Google verification meta tag, but active ownership has not been confirmed.
3. Under **Sitemaps**, submit `https://aqlyra-ai.vercel.app/sitemap.xml`. Do this once after the new route is live; repeated same-day resubmission is unnecessary.
4. Use **URL Inspection** for `/`, `/about`, and `/how-it-works`. Confirm `200`, indexed/eligible status, Google-selected canonical URL, and screenshot/rendered text; select **Request Indexing** if needed.
5. Review **Page indexing** for blocked/duplicate/crawled-not-indexed statuses; check **Performance → Search results** for actual queries, CTR, clicks and impressions. If available, use Google's **Search generative AI** reports to measure exposure in AI features. Keep a dated baseline and monitor changes over subsequent weeks.
6. If the final custom domain changes later, migrate with canonical redirects and Google's site-move guidance, rather than changing this canonical until the domain is confirmed.

## Content and authority — truthful, long-term work

- Produce a technical blog or portfolio case study showing real Aqlyra RAG evaluation methodology, private-document citations, retrieval coverage and known failure modes. Link it to the public app and public GitHub repository.
- Maintain clear, consistent name/description/link on the real GitHub README and relevant professional profiles. A legitimate technical article, tutorial, demo video with transcript or relevant independent review is more useful than purchased backlinks or generated link farms.
- Improve performance, mobile usability, real user documentation, and accessibility. Keep concise, helpful page text as HTML visible to anonymous visitors.
- Prioritize branded queries first (e.g. `Aqlyra AI`, `Aqlyra RAG`, `How does Aqlyra AI work`) and accurately descriptive intent phrases (e.g. `private document RAG with citations`), not promises of winning high-competition search terms immediately.
- Do not manufacture testimonials, aggregate ratings, download counts or false comparisons. Do not add `llms.txt` or AI markup solely to chase Google AI; Google says no special file or schema is required for AI Overviews/AI Mode.

## Limits

Search indexation, ranking and Google AI use of Aqlyra's content are determined by Google; neither a sitemap nor schema guarantees inclusion, rich results or top positions. AI features require an indexed page that can appear with a Google Search snippet, and Google describes the usual SEO fundamentals as sufficient eligibility work. Public, crawlable text improves the chance Google can understand Aqlyra; it does not force an AI model to use or quote it.

## Authoritative documentation

- https://developers.google.com/search/docs/appearance/ai-features
- https://developers.google.com/search/docs/appearance/structured-data/software-app
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- https://developers.google.com/search/docs/monitor-debug/search-console-start
