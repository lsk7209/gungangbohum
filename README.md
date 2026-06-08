# CoverClarity Florida ACA Subsidy Site

Static Florida ACA subsidy calculator and guide library.

## Local Commands

```powershell
npm run generate
npm run validate
npm run adsense:apply -- --publisher-id pub-3050601904412736 --dry-run
npm run analytics:apply -- --measurement-id G-XXXXXXXXXX --dry-run
npm run audit:seo
npm run audit:performance
npm run check
npm run ready
```

For production after a domain is assigned:

```powershell
$env:SITE_ORIGIN = "https://your-domain.example"
$env:PUBLIC_CONTACT_EMAIL = "contact@your-domain.example"
$env:GA4_MEASUREMENT_ID = "G-XXXXXXXXXX"
$env:ADSENSE_PUBLISHER_ID = "pub-3050601904412736"
npm run contact:apply
npm run analytics:apply
npm run adsense:apply
npm run check:production
npm run ready:production
```

Replace every `your-domain.example` placeholder with the real production domain before running production commands; launch scripts reject placeholder, example, and local domains.

Or run the launch preparation wrapper, which applies the production origin, validates public artifacts, checks local GSC credentials, and writes the readiness report:

```powershell
npm run launch:prepare -- --origin https://your-domain.example --contact-email contact@your-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-3050601904412736
```

Run the same input checks without changing files first:

```powershell
npm run launch:preflight -- --origin https://your-domain.example --contact-email contact@your-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-3050601904412736
```

`launch:prepare` exits successfully only when production readiness passes. For a non-submission preview with known blockers, add `--allow-incomplete-readiness`.

To also set the GitHub repository variables used by the sitemap workflow:

```powershell
npm run launch:prepare -- --origin https://your-domain.example --contact-email contact@your-domain.example --ga4-measurement-id G-XXXXXXXXXX --adsense-publisher-id pub-3050601904412736 --set-github-vars
```

## Deployment Notes

- The site is static HTML/CSS/JS and can be served from the repository root.
- Use `SITE_ORIGIN` and `npm run check:production` to replace `{SITE_ORIGIN}` and fail the build if placeholders remain.
- Do not add manual ad slots; AdSense should use automatic ads only.
- Keep `ads.txt` at the site root with the verified AdSense publisher ID.
- `sitemap.xml`, `robots.txt`, `feed.xml`, `llms.txt`, `opensearch.xml`, and `content/search-index.json` are public artifacts.

## Search Console

After the production domain is assigned and verified in Google Search Console, set:

```powershell
$env:GSC_SITE_URL = "https://your-domain.example/"
$env:GSC_SITEMAP_URL = "https://your-domain.example/sitemap.xml"
$env:GSC_CLIENT_JSON = Get-Content D:\env\adsense_oauth_client.json -Raw
$env:GSC_TOKEN_JSON = Get-Content D:\env\gsc_token.json -Raw
npm run gsc:check
npm run gsc:submit
```

The GitHub workflow `.github/workflows/gsc-sitemap-submit.yml` also submits automatically on `main` pushes that change sitemap-related artifacts when repository variables `GSC_SITE_URL`, `GSC_SITEMAP_URL` and secrets `GSC_CLIENT_JSON`, `GSC_TOKEN_JSON` are set. It can also be run manually with `site_url` and `sitemap_url` inputs, and it retries daily after the repository variables are set. The content quality workflow also writes the production readiness report so CI catches missing readiness-audit wiring.

The repository secrets can be prepared before the domain is assigned:

```powershell
Get-Content D:\env\adsense_oauth_client.json -Raw | gh secret set GSC_CLIENT_JSON --repo lsk7209/gungangbohum
Get-Content D:\env\gsc_token.json -Raw | gh secret set GSC_TOKEN_JSON --repo lsk7209/gungangbohum
```

## Quality Gate

Run `npm run check` before publishing. The validator checks generated article counts, metadata, canonical links, schemas, accessibility landmarks, sitemap/feed/search-index parity, public marker leakage, and repeated body sentence risk.

Run `npm run audit:seo` to write `reports/seo-adsense-audit-report.json`. It maps the SEO and AdSense checklist to machine checks for per-page meta titles and descriptions, canonical URLs, sitemap and robots files, H-tag hierarchy, image alt text, article CTA/internal/external links, readable URLs, and absence of manual ad slots.

Run `npm run audit:performance` to write `reports/performance-budget-report.json`. It checks static HTML size budgets, article average size, inline style/script budgets, public JSON size, and static header configuration.

The launch assumptions are tracked in `docs/phase0-verification-report.md`. Keep that report current when rating-area data, SLCSP data, subsidy law status, or Florida coverage-gap handling changes.

Run `npm run ready` to write `reports/production-readiness-report.json`. It reports whether content quality, SEO/AdSense audit status, static performance budgets, production origin replacement, GitHub remote state, public contact channel, GSC workflow automation, and GSC URL/credential configuration are ready for production submission.
