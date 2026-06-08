import argparse
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADS_TXT = ROOT / "ads.txt"
PUB_RE = re.compile(r"^(?:ca-)?pub-\d{16}$")
GOOGLE_CERT_AUTHORITY_ID = "f08c47fec0942fa"


def normalize_publisher_id(value):
    publisher_id = (value or "").strip()
    if not PUB_RE.match(publisher_id):
        raise SystemExit("ADSENSE_PUBLISHER_ID must look like pub-0000000000000000 or ca-pub-0000000000000000.")
    return publisher_id.removeprefix("ca-")


def render_ads_txt(publisher_id):
    return f"google.com, {publisher_id}, DIRECT, {GOOGLE_CERT_AUTHORITY_ID}\n"


def main():
    parser = argparse.ArgumentParser(description="Write ads.txt for a Google AdSense publisher ID.")
    parser.add_argument("--publisher-id", default=os.getenv("ADSENSE_PUBLISHER_ID", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    publisher_id = normalize_publisher_id(args.publisher_id)
    text = render_ads_txt(publisher_id)
    if args.dry_run:
        print(text, end="")
        return 0
    ADS_TXT.write_text(text, encoding="utf-8")
    print(f"Wrote ads.txt for {publisher_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
