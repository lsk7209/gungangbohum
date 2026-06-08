import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from apply_ads_txt import normalize_publisher_id
from apply_contact_channel import contact_block, normalize_email, normalize_url
from apply_ga4_measurement import normalize_measurement_id
from apply_site_origin import normalize_origin


ROOT = Path(__file__).resolve().parents[1]


def run_step(label, args, env):
    print(f"\n== {label} ==")
    result = subprocess.run(args, cwd=ROOT, env=env, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_capture(args, env):
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, check=False)


def github_repo(env):
    result = run_capture(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], env)
    if result.returncode != 0:
        raise SystemExit("Could not resolve GitHub repository with gh repo view.")
    return result.stdout.strip()


def ensure_sitemap_url(origin):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("Origin must be an https:// production origin.")
    return f"{origin}/sitemap.xml"


def set_github_variable(repo, name, value, env):
    result = subprocess.run(
        ["gh", "variable", "set", name, "--repo", repo, "--body", value],
        cwd=ROOT,
        env=env,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def preflight(args, origin, site_url, sitemap_url, env):
    print("Launch preflight")
    print(f"SITE_ORIGIN={origin}")
    print(f"GSC_SITE_URL={site_url}")
    print(f"GSC_SITEMAP_URL={sitemap_url}")

    email = normalize_email(args.contact_email)
    contact_url = normalize_url(args.contact_url)
    contact_block(email, contact_url)
    print("Public contact channel: ok")

    if args.ga4_measurement_id:
        normalize_measurement_id(args.ga4_measurement_id)
        print("GA4 measurement ID: ok")
    else:
        print("GA4 measurement ID: not provided")

    if args.adsense_publisher_id:
        publisher_id = normalize_publisher_id(args.adsense_publisher_id)
        print(f"AdSense publisher ID: {publisher_id}")
    else:
        print("AdSense publisher ID: not provided")

    if args.set_github_vars:
        repo = github_repo(env)
        print(f"GitHub repository access: {repo}")
        print("GitHub variables: not changed during preflight")

    if not args.skip_gsc_check:
        run_step(
            "Validate GSC sitemap configuration",
            [
                sys.executable,
                "scripts/gsc_submit_sitemap.py",
                "--check-config",
                "--site-url",
                site_url,
                "--sitemap-url",
                sitemap_url,
            ],
            env,
        )
    else:
        print("GSC configuration check: skipped")

    print("Launch preflight completed without file changes.")


def main():
    parser = argparse.ArgumentParser(description="Prepare the static site for production after a domain is assigned.")
    parser.add_argument("--origin", default=os.getenv("SITE_ORIGIN", ""), help="Production origin, for example https://example.com")
    parser.add_argument("--site-url", default=os.getenv("GSC_SITE_URL", ""), help="GSC property URL or sc-domain property. Defaults to origin URL-prefix.")
    parser.add_argument("--sitemap-url", default=os.getenv("GSC_SITEMAP_URL", ""), help="Production sitemap URL. Defaults to origin/sitemap.xml.")
    parser.add_argument("--contact-email", default=os.getenv("PUBLIC_CONTACT_EMAIL", ""), help="Public contact email to apply to contact.html.")
    parser.add_argument("--contact-url", default=os.getenv("PUBLIC_CONTACT_URL", ""), help="Public https contact form URL to apply to contact.html.")
    parser.add_argument("--ga4-measurement-id", default=os.getenv("GA4_MEASUREMENT_ID", ""), help="Optional GA4 measurement ID, for example G-XXXXXXXXXX.")
    parser.add_argument("--adsense-publisher-id", default=os.getenv("ADSENSE_PUBLISHER_ID", ""), help="Optional AdSense publisher ID, for example pub-0000000000000000.")
    parser.add_argument("--skip-gsc-check", action="store_true", help="Skip local GSC credential and URL validation.")
    parser.add_argument("--set-github-vars", action="store_true", help="Set GitHub repo variables GSC_SITE_URL and GSC_SITEMAP_URL.")
    parser.add_argument("--allow-incomplete-readiness", action="store_true", help="Write the readiness report without failing when launch blockers remain.")
    parser.add_argument("--preflight", action="store_true", help="Validate launch inputs and GSC configuration without changing files or GitHub variables.")
    args = parser.parse_args()

    origin = normalize_origin(args.origin)
    sitemap_url = args.sitemap_url.strip() or ensure_sitemap_url(origin)
    site_url = args.site_url.strip() or f"{origin}/"

    env = os.environ.copy()
    env["SITE_ORIGIN"] = origin
    env["GSC_SITE_URL"] = site_url
    env["GSC_SITEMAP_URL"] = sitemap_url
    if args.contact_email:
        env["PUBLIC_CONTACT_EMAIL"] = args.contact_email
    if args.contact_url:
        env["PUBLIC_CONTACT_URL"] = args.contact_url
    if args.ga4_measurement_id:
        env["GA4_MEASUREMENT_ID"] = args.ga4_measurement_id
    if args.adsense_publisher_id:
        env["ADSENSE_PUBLISHER_ID"] = args.adsense_publisher_id

    if args.preflight:
        preflight(args, origin, site_url, sitemap_url, env)
        return 0

    if args.set_github_vars:
        repo = github_repo(env)
        print(f"Setting GitHub variables on {repo}")
        set_github_variable(repo, "GSC_SITE_URL", site_url, env)
        set_github_variable(repo, "GSC_SITEMAP_URL", sitemap_url, env)

    run_step("Generate public artifacts with production origin", [sys.executable, "scripts/generate_aca_articles.py"], env)
    if args.contact_email or args.contact_url:
        run_step("Apply public contact channel", [sys.executable, "scripts/apply_contact_channel.py"], env)
    if args.ga4_measurement_id:
        run_step("Apply GA4 measurement ID", [sys.executable, "scripts/apply_ga4_measurement.py"], env)
    if args.adsense_publisher_id:
        run_step("Apply AdSense ads.txt", [sys.executable, "scripts/apply_ads_txt.py"], env)
    run_step("Apply production origin to static files", [sys.executable, "scripts/apply_site_origin.py", "--origin", origin], env)
    run_step("Validate production content", [sys.executable, "scripts/validate_content_quality.py", "--write-report", "--require-site-origin"], env)

    if not args.skip_gsc_check:
        run_step(
            "Validate GSC sitemap configuration",
            [
                sys.executable,
                "scripts/gsc_submit_sitemap.py",
                "--check-config",
                "--site-url",
                site_url,
                "--sitemap-url",
                sitemap_url,
            ],
            env,
        )

    readiness_args = [sys.executable, "scripts/production_readiness_audit.py", "--write-report"]
    if not args.allow_incomplete_readiness:
        readiness_args.append("--require-ready")
    run_step("Write production readiness report", readiness_args, env)
    if args.allow_incomplete_readiness:
        print("\nLaunch preparation report written with incomplete readiness allowed.")
    else:
        print("\nLaunch preparation checks completed.")
    print(f"SITE_ORIGIN={origin}")
    print(f"GSC_SITE_URL={site_url}")
    print(f"GSC_SITEMAP_URL={sitemap_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
