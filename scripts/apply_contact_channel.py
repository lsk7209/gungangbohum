import argparse
import html
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTACT_PAGE = ROOT / "contact.html"
PRELAUNCH_BLOCK_RE = re.compile(r'<div class="box"><strong>Current launch status:</strong>.*?</div>', re.DOTALL)
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def is_nonproduction_host(hostname):
    host = (hostname or "").lower()
    return (
        host in {"localhost", "127.0.0.1", "example.com"}
        or host.endswith(".example")
        or "your-domain" in host
    )


def normalize_email(value):
    email = (value or "").strip()
    if not email:
        return ""
    if not EMAIL_RE.match(email):
        raise SystemExit("PUBLIC_CONTACT_EMAIL must be a valid email address.")
    domain = email.rsplit("@", 1)[1]
    if is_nonproduction_host(domain):
        raise SystemExit("PUBLIC_CONTACT_EMAIL must use a production domain, not a placeholder, example, or local domain.")
    return email


def normalize_url(value):
    url = (value or "").strip()
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("PUBLIC_CONTACT_URL must be an https:// URL.")
    if is_nonproduction_host(parsed.hostname):
        raise SystemExit("PUBLIC_CONTACT_URL must be public, not a placeholder, example, or local URL.")
    return url


def contact_block(email, url):
    channels = []
    if email:
        escaped_email = html.escape(email, quote=True)
        channels.append(f'<a href="mailto:{escaped_email}">{escaped_email}</a>')
    if url:
        escaped_url = html.escape(url, quote=True)
        channels.append(f'<a href="{escaped_url}">public contact form</a>')
    if not channels:
        raise SystemExit("Set PUBLIC_CONTACT_EMAIL, PUBLIC_CONTACT_URL, or pass --email/--url.")
    channel_text = " or ".join(channels)
    return (
        '<div class="box"><strong>Public contact channel:</strong> '
        f'For corrections, privacy questions, source concerns, or accessibility issues, use {channel_text}. '
        "Include the page URL, the sentence or estimate at issue, the official source you checked, "
        "and the date you reviewed it.</div>"
    )


def main():
    parser = argparse.ArgumentParser(description="Replace the prelaunch contact notice with a public contact channel.")
    parser.add_argument("--email", default=os.getenv("PUBLIC_CONTACT_EMAIL", ""))
    parser.add_argument("--url", default=os.getenv("PUBLIC_CONTACT_URL", ""))
    args = parser.parse_args()

    if not CONTACT_PAGE.exists():
        raise SystemExit("contact.html is missing.")
    email = normalize_email(args.email)
    url = normalize_url(args.url)
    replacement = contact_block(email, url)
    text = CONTACT_PAGE.read_text(encoding="utf-8")
    updated, count = PRELAUNCH_BLOCK_RE.subn(replacement, text, count=1)
    if count == 0:
        if "Public contact channel:" in text:
            print("contact.html already contains a public contact channel.")
            return 0
        raise SystemExit("Could not find the prelaunch contact notice in contact.html.")
    CONTACT_PAGE.write_text(updated, encoding="utf-8")
    print("Applied public contact channel to contact.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
