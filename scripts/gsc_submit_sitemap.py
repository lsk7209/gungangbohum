import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


SCOPES = ["https://www.googleapis.com/auth/webmasters"]
DEFAULT_SITE_URL = ""
DEFAULT_SITEMAP_URL = ""


def is_nonproduction_host(hostname: str) -> bool:
    host = (hostname or "").lower()
    return (
        host in {"localhost", "127.0.0.1", "example.com"}
        or host.endswith(".example")
        or "your-domain" in host
    )


def _json_from_env_or_file(env_name: str, fallback_path: str) -> dict:
    raw = os.getenv(env_name)
    if raw:
        return json.loads(raw)
    path = Path(fallback_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing {env_name} or {fallback_path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_data = _json_from_env_or_file("GSC_TOKEN_JSON", r"D:\env\gsc_token.json")
    client_data = _json_from_env_or_file("GSC_CLIENT_JSON", r"D:\env\adsense_oauth_client.json")
    installed = client_data.get("installed", client_data)

    token_data.setdefault("client_id", installed["client_id"])
    token_data.setdefault("client_secret", installed["client_secret"])
    token_data.setdefault("token_uri", "https://oauth2.googleapis.com/token")
    token_data.setdefault("universe_domain", "googleapis.com")
    if "token" not in token_data and "access_token" in token_data:
        token_data["token"] = token_data["access_token"]

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        raise RuntimeError("Google Search Console credentials are not valid and could not be refreshed.")
    return creds


def normalize_site_url(value: str) -> str:
    site_url = (value or "").strip().rstrip("/")
    if not site_url or "{SITE_ORIGIN}" in site_url:
        raise ValueError("GSC_SITE_URL must be set after the project domain is assigned.")
    if site_url.startswith("sc-domain:"):
        domain = site_url.removeprefix("sc-domain:").strip()
        if not domain or "/" in domain:
            raise ValueError("GSC_SITE_URL sc-domain property must look like sc-domain:your-production-domain.com")
        if is_nonproduction_host(domain):
            raise ValueError("GSC_SITE_URL must be the production property, not a placeholder, example, or local domain.")
        return site_url
    parsed = urlsplit(site_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("GSC_SITE_URL must be an https:// URL-prefix property or sc-domain:example.com")
    if is_nonproduction_host(parsed.hostname or ""):
        raise ValueError("GSC_SITE_URL must be the production property, not a placeholder, example, or local URL.")
    return site_url + "/"


def normalize_sitemap_url(value: str) -> str:
    sitemap_url = (value or "").strip()
    if not sitemap_url or "{SITE_ORIGIN}" in sitemap_url:
        raise ValueError("GSC_SITEMAP_URL must be set after the project domain is assigned.")
    parsed = urlsplit(sitemap_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("GSC_SITEMAP_URL must be an https:// URL.")
    if is_nonproduction_host(parsed.hostname or ""):
        raise ValueError("GSC_SITEMAP_URL must be the production sitemap, not a placeholder, example, or local URL.")
    if not parsed.path.endswith("/sitemap.xml"):
        raise ValueError("GSC_SITEMAP_URL should point to the production /sitemap.xml file.")
    return sitemap_url


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", default=os.getenv("GSC_SITE_URL", DEFAULT_SITE_URL))
    parser.add_argument("--sitemap-url", default=os.getenv("GSC_SITEMAP_URL", DEFAULT_SITEMAP_URL))
    parser.add_argument("--check-config", action="store_true", help="Validate URLs and credential files/env without calling GSC.")
    parser.add_argument("--allow-pending", action="store_true", help="Return success after submit/list even if GSC has not downloaded the sitemap yet.")
    args = parser.parse_args()

    try:
        site_url = normalize_site_url(args.site_url)
        sitemap_url = normalize_sitemap_url(args.sitemap_url)
    except ValueError as exc:
        print(str(exc))
        return 2

    if args.check_config:
        _json_from_env_or_file("GSC_TOKEN_JSON", r"D:\env\gsc_token.json")
        _json_from_env_or_file("GSC_CLIENT_JSON", r"D:\env\adsense_oauth_client.json")
        print(json.dumps({
            "status": "config_ok",
            "siteUrl": site_url,
            "sitemapUrl": sitemap_url,
        }, ensure_ascii=False, indent=2))
        return 0

    from googleapiclient.discovery import build

    service = build("webmasters", "v3", credentials=get_credentials())
    service.sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url).execute()
    sitemaps = service.sitemaps().list(siteUrl=site_url).execute().get("sitemap", [])

    target = next((item for item in sitemaps if item.get("path") == sitemap_url), None)
    if not target:
        print(f"Submitted {sitemap_url}, but it is not listed yet.")
        return 2

    errors = str(target.get("errors", "0"))
    warnings = str(target.get("warnings", "0"))
    downloaded = target.get("lastDownloaded")
    status = "success" if errors == "0" and downloaded else "pending"
    print(json.dumps({
        "status": status,
        "siteUrl": site_url,
        "sitemapUrl": sitemap_url,
        "lastSubmitted": target.get("lastSubmitted"),
        "lastDownloaded": downloaded,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))

    if errors != "0":
        return 1
    if not downloaded and not args.allow_pending:
        print("GSC accepted the sitemap but has not downloaded it yet. Re-run later to prove success.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
