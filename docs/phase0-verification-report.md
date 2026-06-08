# Phase 0 Verification Report

Project: CoverClarity Florida ACA Subsidy Estimator

Last reviewed: 2026-06-08

This report records the launch assumptions that must stay visible for a YMYL ACA subsidy calculator. The current implementation is a static v1 site: client-side estimator, static guide library, public sitemap/feed/search index, and no lead capture.

## G0-1 County And Rating Area Scope

Status: documented v1 limitation.

The v1 calculator uses five Florida metro presets as planning shortcuts. It does not claim county-level precision and does not map every Florida county to a filed rating area. County/rating-area expansion remains a v2 data task.

Public handling:

- The methodology page states that the current prototype uses illustrative Florida rating data.
- Generated articles point readers back to methodology and official Marketplace confirmation.
- The calculator labels the location selector as resolving to a Florida rating area, but final prices must be confirmed through HealthCare.gov.

Required before county-level launch:

- Add a source-controlled Florida county to rating-area table.
- Add source year and source URL.
- Add validator coverage for one-to-one county mapping.

## G0-2 SLCSP Calculation Scope

Status: documented v1 limitation.

The current v1 does not ingest Exchange PUF files into Turso and does not compute the second-lowest-cost Silver plan from filed plan data. It uses illustrative metro benchmark values in the browser calculator to support reader education and content structure.

Public handling:

- The methodology page states production launch should replace static figures with filed CMS Exchange PUF data.
- Result UI labels numbers as estimates, not quotes.
- Articles include source links and official confirmation paths.

Required before filed-rate launch:

- Load CMS Exchange PUF rate data.
- Derive SLCSP by Florida rating area, age, plan year, and tobacco handling.
- Compare sample outputs against CMS/KFF benchmark references.

## G0-3 Subsidy Regime Status

Status: implemented as two visible comparison columns.

The calculator compares an enhanced-credit scenario against current-law pre-2021 rules. Current public copy says the enhanced premium tax credits expired on December 31, 2025, and that users must confirm final eligibility and prices through HealthCare.gov.

Source basis:

- CMS Marketplace training materials described enhanced premium tax credit eligibility as ending December 31, 2025.
- KFF's January 2026 update states the premium tax credit enhancements expired at the end of 2025 and had not been renewed by Congress.
- HealthCare.gov explains that Marketplace savings and Medicaid/CHIP eligibility use federal poverty level thresholds and final official Marketplace determinations.

Operational rule:

- If Congress changes the enhanced-credit status, update the calculator copy, methodology page, and generated article source notes before publication.

## G0-4 Florida Coverage Gap Handling

Status: implemented.

Florida did not expand Medicaid for the standard ACA adult expansion group. For income below about 100% FPL, the calculator returns a coverage-gap explanation rather than a normal subsidy result.

Public handling:

- Calculator shows a coverage-gap result state.
- Articles include coverage-gap topics and official verification paths.
- Methodology explains the below-100% FPL handling.

## SEO, GEO, AEO, And AdSense Readiness

Implemented:

- Page-level title, description, canonical, OG/Twitter metadata.
- `sitemap.xml`, `robots.txt`, `feed.xml`, `llms.txt`, OpenSearch, and public search index.
- One H1 per HTML page and ordered heading validation.
- Article table of contents, internal links, official external source links, CTA blocks, FAQ schema where appropriate, and trust/editorial blocks.
- No manual ad slots and no lead capture forms.
- Static cache headers in `vercel.json`.
- Production origin gate through `SITE_ORIGIN` and `npm run check:production`.

Known blocker:

- Production domain is not assigned. Until `SITE_ORIGIN` is set to an HTTPS domain, canonical URLs and GSC sitemap submission cannot be proven successful.
- Google Search Console automatic sitemap submission is wired through `.github/workflows/gsc-sitemap-submit.yml`, but it requires repository variables `GSC_SITE_URL`, `GSC_SITEMAP_URL` and secrets `GSC_CLIENT_JSON`, `GSC_TOKEN_JSON`. The workflow also supports manual `site_url` and `sitemap_url` inputs, and retries daily after the repository variables are set.
- GitHub repository secrets `GSC_CLIENT_JSON` and `GSC_TOKEN_JSON` can be set before launch; repository variables `GSC_SITE_URL` and `GSC_SITEMAP_URL` require the final production domain.

## Validation Evidence

Run:

```powershell
npm run check
```

Expected:

- 200 generated ACA article pages.
- 5 guide hub files; empty guide hubs remain `noindex,follow` until at least one article in that cluster is published.
- 11 sitemap URLs in the current dry-run state: core/trust pages, the evergreen subsidy explainer, and currently published articles only.
- 2 RSS feed items while scheduled articles remain `noindex,follow`.
- 0 guide hub sitemap URLs and 0 guide hub search-index documents until a guide cluster has published articles.
- 0 validator errors.

Production-only gate:

```powershell
$env:SITE_ORIGIN = "https://your-production-domain.example"
$env:PUBLIC_CONTACT_EMAIL = "contact@your-production-domain.example"
$env:GA4_MEASUREMENT_ID = "G-XXXXXXXXXX"
$env:ADSENSE_PUBLISHER_ID = "pub-3050601904412736"
npm run contact:apply
npm run analytics:apply
npm run adsense:apply
npm run check:production
```

Replace every `your-production-domain.example` placeholder with the real production domain before running production commands; launch scripts reject placeholder, example, and local domains.
Use `docs/launch-env.example.ps1` as the complete no-secret launch environment checklist.
Run `npm run launch:check-env` after filling local environment values to validate them without changing files or calling Google APIs. It also confirms `SITE_ORIGIN`, `GSC_SITE_URL`, and `GSC_SITEMAP_URL` point to the same production host or a covering `sc-domain` property.
Run `npm run launch:commands -- --origin https://your-production-domain.example --contact-email contact@your-production-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-0000000000000000` to print validated PowerShell launch commands without changing files.

Launch wrapper:

```powershell
npm run launch:preflight -- --origin https://your-production-domain.example --contact-email contact@your-production-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-3050601904412736
npm run launch:prepare -- --origin https://your-production-domain.example --contact-email contact@your-production-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-3050601904412736
```

`launch:preflight` validates launch inputs and local GSC configuration without changing files or GitHub variables. `launch:prepare` requires a clean git worktree before it changes files or repository variables, then exits successfully only when the production readiness audit passes. Use `--allow-dirty-worktree` only for an intentional local preview, and use `--allow-incomplete-readiness` only for a non-submission preview with known blockers.

Expected:

- No `{SITE_ORIGIN}` placeholder in public artifacts.
- `sitemap.xml`, `robots.txt`, canonical URLs, feed, OpenSearch, and JSON search index all use the production origin.
- `contact.html` exposes a public email or HTTPS contact form instead of the prelaunch notice.
- GA4 is applied only when a production `GA4_MEASUREMENT_ID` is available.
- Root `ads.txt` contains the verified AdSense publisher record.
- Local GSC credential and URL validation passes when `D:\env\adsense_oauth_client.json` and `D:\env\gsc_token.json` are available.

Search Console gate:

```powershell
npm run gsc:check
npm run gsc:submit
```

Expected:

- `gsc:check` returns `config_ok`.
- `gsc:submit` returns `status: "success"` after Google has downloaded the sitemap and reports zero errors.

Production readiness audit:

```powershell
npm run ready
npm run ready:production
```

Expected:

- `ready` writes `reports/production-readiness-report.json`.
- `ready:production` exits successfully only after content quality, SEO/AdSense audit, performance budget audit, production origin replacement, public contact channel, GitHub remote state, GSC workflow automation, and GSC URL/credential configuration are all proven.
