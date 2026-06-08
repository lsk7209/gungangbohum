import argparse
from urllib.parse import urlsplit

from apply_ads_txt import normalize_publisher_id
from apply_contact_channel import contact_block, normalize_email, normalize_url
from apply_ga4_measurement import normalize_measurement_id
from apply_site_origin import normalize_origin
from launch_prepare import ensure_sitemap_url, validate_launch_urls


def ps_quote(value):
    return '"' + value.replace("`", "``").replace('"', '`"') + '"'


def main():
    parser = argparse.ArgumentParser(description="Print validated local launch commands without changing files.")
    parser.add_argument("--origin", required=True, help="Production origin, for example https://example.com")
    parser.add_argument("--site-url", default="", help="GSC property URL. Defaults to origin URL-prefix.")
    parser.add_argument("--sitemap-url", default="", help="Production sitemap URL. Defaults to origin/sitemap.xml.")
    parser.add_argument("--contact-email", default="", help="Public contact email.")
    parser.add_argument("--contact-url", default="", help="Public https contact form URL.")
    parser.add_argument("--ga4-measurement-id", default="", help="GA4 measurement ID, for example G-XXXXXXXXXX.")
    parser.add_argument("--adsense-publisher-id", default="", help="AdSense publisher ID, for example pub-0000000000000000.")
    args = parser.parse_args()

    try:
        origin = normalize_origin(args.origin)
        site_url = args.site_url.strip() or f"{origin}/"
        sitemap_url = args.sitemap_url.strip() or ensure_sitemap_url(origin)
        site_url, sitemap_url = validate_launch_urls(origin, site_url, sitemap_url)

        contact_email = normalize_email(args.contact_email)
        contact_url = normalize_url(args.contact_url)
        contact_block(contact_email, contact_url)
        ga4_measurement_id = normalize_measurement_id(args.ga4_measurement_id)
        adsense_publisher_id = normalize_publisher_id(args.adsense_publisher_id)
    except (SystemExit, ValueError) as exc:
        message = exc.code if isinstance(exc, SystemExit) else str(exc)
        raise SystemExit(message)

    origin_host = urlsplit(origin).hostname or ""
    print("# Validated launch commands. Review values before running.")
    print(f"# Production host: {origin_host}")
    print(f"$env:SITE_ORIGIN = {ps_quote(origin)}")
    print(f"$env:PUBLIC_CONTACT_EMAIL = {ps_quote(contact_email)}")
    print(f"$env:PUBLIC_CONTACT_URL = {ps_quote(contact_url)}")
    print(f"$env:GA4_MEASUREMENT_ID = {ps_quote(ga4_measurement_id)}")
    print(f"$env:ADSENSE_PUBLISHER_ID = {ps_quote(adsense_publisher_id)}")
    print(f"$env:GSC_SITE_URL = {ps_quote(site_url)}")
    print(f"$env:GSC_SITEMAP_URL = {ps_quote(sitemap_url)}")
    print("$env:GSC_CLIENT_JSON = Get-Content D:\\env\\adsense_oauth_client.json -Raw")
    print("$env:GSC_TOKEN_JSON = Get-Content D:\\env\\gsc_token.json -Raw")
    print("")
    print("# Prepare GitHub Actions GSC configuration. These commands do not print secret values.")
    print("Get-Content D:\\env\\adsense_oauth_client.json -Raw | gh secret set GSC_CLIENT_JSON --repo lsk7209/gungangbohum")
    print("Get-Content D:\\env\\gsc_token.json -Raw | gh secret set GSC_TOKEN_JSON --repo lsk7209/gungangbohum")
    print("gh variable set GSC_SITE_URL --repo lsk7209/gungangbohum --body $env:GSC_SITE_URL")
    print("gh variable set GSC_SITEMAP_URL --repo lsk7209/gungangbohum --body $env:GSC_SITEMAP_URL")
    print("")
    print("npm run launch:check-env")
    print("npm run launch:preflight -- --origin $env:SITE_ORIGIN --site-url $env:GSC_SITE_URL --sitemap-url $env:GSC_SITEMAP_URL --contact-email $env:PUBLIC_CONTACT_EMAIL --contact-url $env:PUBLIC_CONTACT_URL --ga4-measurement-id $env:GA4_MEASUREMENT_ID --adsense-publisher-id $env:ADSENSE_PUBLISHER_ID")
    print("npm run launch:prepare -- --origin $env:SITE_ORIGIN --site-url $env:GSC_SITE_URL --sitemap-url $env:GSC_SITEMAP_URL --contact-email $env:PUBLIC_CONTACT_EMAIL --contact-url $env:PUBLIC_CONTACT_URL --ga4-measurement-id $env:GA4_MEASUREMENT_ID --adsense-publisher-id $env:ADSENSE_PUBLISHER_ID --set-github-vars")
    print("npm run ready:production")


if __name__ == "__main__":
    raise SystemExit(main())
