# CoverClarity Florida ACA Subsidy Site

Static Florida ACA subsidy calculator and guide library.

## Local Commands

```powershell
npm run generate
npm run validate
npm run check
npm run ready
```

For production after a domain is assigned:

```powershell
$env:SITE_ORIGIN = "https://your-domain.example"
npm run check:production
npm run ready:production
```

## Deployment Notes

- The site is static HTML/CSS/JS and can be served from the repository root.
- Use `SITE_ORIGIN` and `npm run check:production` to replace `{SITE_ORIGIN}` and fail the build if placeholders remain.
- Do not add manual ad slots; AdSense should use automatic ads only.
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

The GitHub workflow `.github/workflows/gsc-sitemap-submit.yml` also submits automatically on `main` pushes that change sitemap-related artifacts when repository variables `GSC_SITE_URL`, `GSC_SITEMAP_URL` and secrets `GSC_CLIENT_JSON`, `GSC_TOKEN_JSON` are set.

The repository secrets can be prepared before the domain is assigned:

```powershell
Get-Content D:\env\adsense_oauth_client.json -Raw | gh secret set GSC_CLIENT_JSON --repo lsk7209/gungangbohum
Get-Content D:\env\gsc_token.json -Raw | gh secret set GSC_TOKEN_JSON --repo lsk7209/gungangbohum
```

## Quality Gate

Run `npm run check` before publishing. The validator checks generated article counts, metadata, canonical links, schemas, accessibility landmarks, sitemap/feed/search-index parity, public marker leakage, and repeated body sentence risk.

The launch assumptions are tracked in `docs/phase0-verification-report.md`. Keep that report current when rating-area data, SLCSP data, subsidy law status, or Florida coverage-gap handling changes.

Run `npm run ready` to write `reports/production-readiness-report.json`. It reports whether content quality, production origin replacement, GitHub remote state, and GSC configuration are ready for production submission.
