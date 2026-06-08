# Copy this file locally, replace every placeholder with production values, then run launch commands.
# Do not commit the copied file if it contains real credentials.

$env:SITE_ORIGIN = "https://your-production-domain.example"
$env:PUBLIC_CONTACT_EMAIL = "contact@your-production-domain.example"
$env:PUBLIC_CONTACT_URL = ""
$env:GA4_MEASUREMENT_ID = "G-XXXXXXXXXX"
$env:ADSENSE_PUBLISHER_ID = "pub-3050601904412736"

$env:GSC_SITE_URL = "https://your-production-domain.example/"
$env:GSC_SITEMAP_URL = "https://your-production-domain.example/sitemap.xml"

# SITE_ORIGIN and GSC_SITEMAP_URL must use the same production host.
# GSC_SITE_URL must be the same URL-prefix property or a covering sc-domain property.

# Prefer GitHub repository secrets for CI. These local values are for manual verification only.
# launch:check-env also verifies GitHub GSC secrets and variables without printing secret values.
$env:GSC_CLIENT_JSON = Get-Content D:\env\adsense_oauth_client.json -Raw
$env:GSC_TOKEN_JSON = Get-Content D:\env\gsc_token.json -Raw

Get-Content D:\env\adsense_oauth_client.json -Raw | gh secret set GSC_CLIENT_JSON --repo lsk7209/gungangbohum
Get-Content D:\env\gsc_token.json -Raw | gh secret set GSC_TOKEN_JSON --repo lsk7209/gungangbohum
gh variable set GSC_SITE_URL --repo lsk7209/gungangbohum --body $env:GSC_SITE_URL
gh variable set GSC_SITEMAP_URL --repo lsk7209/gungangbohum --body $env:GSC_SITEMAP_URL

# Optional: print validated commands from the final production values without changing files.
npm run launch:commands -- --origin $env:SITE_ORIGIN --site-url $env:GSC_SITE_URL --sitemap-url $env:GSC_SITEMAP_URL --contact-email $env:PUBLIC_CONTACT_EMAIL --contact-url $env:PUBLIC_CONTACT_URL --ga4-measurement-id $env:GA4_MEASUREMENT_ID --adsense-publisher-id $env:ADSENSE_PUBLISHER_ID

npm run launch:check-env
npm run launch:preflight -- --origin $env:SITE_ORIGIN --contact-email $env:PUBLIC_CONTACT_EMAIL --contact-url $env:PUBLIC_CONTACT_URL --ga4-measurement-id $env:GA4_MEASUREMENT_ID --adsense-publisher-id $env:ADSENSE_PUBLISHER_ID
npm run launch:prepare -- --origin $env:SITE_ORIGIN --contact-email $env:PUBLIC_CONTACT_EMAIL --contact-url $env:PUBLIC_CONTACT_URL --ga4-measurement-id $env:GA4_MEASUREMENT_ID --adsense-publisher-id $env:ADSENSE_PUBLISHER_ID --set-github-vars
npm run ready:production
