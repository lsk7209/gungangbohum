# Content quality checks

This project generates the ACA article library from `scripts/generate_aca_articles.py`.

Run the generator:

```powershell
python scripts\generate_aca_articles.py
```

Run the quality validator and write the report:

```powershell
python scripts\validate_content_quality.py --write-report
```

Run the SEO and AdSense checklist audit:

```powershell
python scripts\audit_seo_adsense.py --write-report
```

Run the static performance budget audit:

```powershell
python scripts\audit_performance_budget.py --write-report
```

Preview optional GA4 injection before launch:

```powershell
python scripts\apply_ga4_measurement.py --measurement-id G-XXXXXXXXXX --dry-run
```

Preview or write AdSense `ads.txt`:

```powershell
python scripts\apply_ads_txt.py --publisher-id pub-3050601904412736 --dry-run
```

The validator checks:

- project operation files: `package.json`, `vercel.json`, `README.md`, the GitHub content-quality workflow, the scheduled publishing workflow, and launch CI status check
- Phase 0 launch-assumption report at `docs/phase0-verification-report.md`
- optional production gate: `--require-site-origin` fails if `{SITE_ORIGIN}` remains in public artifacts
- 200 queued articles and 200 article HTML files
- 5 guide hub pages, with empty guide hubs kept `noindex,follow`
- RSS feed items match currently published articles
- sitemap URL counts, including exclusion of empty guide hubs and scheduled articles
- `404.html` exists, is `noindex,follow`, links to recovery paths, and is excluded from sitemap
- `opensearch.xml` exists, points site search to `/blog.html`, is linked from every HTML page, and is excluded from sitemap
- internal link targets, URL fragments, one H1, and main landmark checks across generated HTML
- H1/H2/H3 heading hierarchy jumps across generated HTML
- image alt text on every HTML image when images are present
- unique title, slug, and main keyword values
- readable article slug structure and maximum slug length
- title cleanup patterns, lowercase title starts, and meta title/description length limits
- unique meta title and meta description values across the 200 generated articles
- meta titles do not end on truncation periods or weak dangling words such as `a`, `an`, `for`, or `read`
- meta titles stay at 30-58 characters so SERP titles are specific but not chopped
- meta titles use compact percent formatting without stray spaces before `%`
- meta descriptions do not end on weak truncated connector words such as `and`, `with`, `before`, or `plus`
- repeated title phrase checks for generated long-tail article patterns
- 5-hour publishing interval
- content-quality CI pins `PUBLICATION_NOW` to the latest committed published article, while scheduled publishing checks hourly with real time and only publishes due 5-hour-scheduled articles
- article meta, canonical, OG/Twitter, RSS alternate, OpenSearch discovery, table of contents, source list, related path, and editorial block
- article CTA blocks, at least two internal links, and at least one external link
- article source boxes with at least two official citation entries in Article schema
- visible article byline/review signal and Article schema `reviewedBy` entity reference
- Article, BreadcrumbList, and FAQPage JSON-LD counts
- representative Organization and WebSite/SearchAction entity schema on home, blog, guide hubs, and generated articles
- guide hub CollectionPage, ItemList, and BreadcrumbList JSON-LD
- guide hub sitemap/search-index parity: populated hubs are indexable, empty hubs are not
- blog page weight and representative BlogPosting schema count
- skip links and visible keyboard focus styles on every HTML page
- public HTML does not expose internal content quality scores
- public HTML, RSS, `llms.txt`, and search index do not expose internal production labels such as pSEO, quality scores, or generation flags
- trust page links
- generated article body sentences are checked for excessive repetition across the 200-article library
- `llms.txt` non-empty guide sections and `content/search-index.json`
- public `content/article-queue.json` excludes internal generation flags, quality scores, and production-only labels
- stale domains, manual ad slot markers, and mojibake markers

The SEO and AdSense audit writes `reports/seo-adsense-audit-report.json` and summarizes:

- per-page meta title, meta description, and canonical URL presence
- meta title and description search-snippet length ranges, plus duplicate title/description detection
- sitemap URL, canonical URL, and noindex/indexability consistency
- target keyword front-signal checks in title and description text
- `sitemap.xml` and `robots.txt` presence
- valid root `ads.txt`
- H1/H2/H3 hierarchy checks
- image alt text coverage
- article CTA, two-or-more internal links, and one-or-more external links
- readable URL slugs
- AdSense auto-ads-only policy by checking for manual ad slot markers

The performance budget audit writes `reports/performance-budget-report.json` and summarizes:

- largest HTML files and page-size budgets
- article page maximum and average byte budgets
- inline style and script byte budgets
- public JSON size budgets for the article queue and search index
- required static cache, content-type, security, and referrer-policy headers in `vercel.json`

Optional GA4 injection uses `scripts/apply_ga4_measurement.py` and only runs when a production `GA4_MEASUREMENT_ID` is supplied.

AdSense `ads.txt` uses `scripts/apply_ads_txt.py` and writes only the verified Google AdSense DIRECT record.

The latest generated report is written to `reports/content-quality-report.json`.

Run:

```powershell
python scripts\production_readiness_audit.py --write-report
```

The readiness audit writes `reports/production-readiness-report.json` and checks whether the project has a passing content-quality report, production origin replacement, a Git repository with remote, and Google Search Console configuration.
