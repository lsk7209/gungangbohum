import argparse
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "aca"
GUIDE_DIR = ROOT / "guides"
GA4_RE = re.compile(r"^G-[A-Z0-9]{6,}$")
EXISTING_GTAG_RE = re.compile(r"https://www\.googletagmanager\.com/gtag/js\?id=G-[A-Z0-9]+")


def public_html_files():
    return sorted(ROOT.glob("*.html")) + sorted(ARTICLE_DIR.glob("*.html")) + sorted(GUIDE_DIR.glob("*.html"))


def normalize_measurement_id(value):
    measurement_id = (value or "").strip().upper()
    if not GA4_RE.match(measurement_id):
        raise SystemExit("GA4_MEASUREMENT_ID must look like G-XXXXXXXXXX.")
    return measurement_id


def snippet(measurement_id):
    return f"""  <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{measurement_id}', {{ anonymize_ip: true }});
  </script>
"""


def apply_to_html(html, measurement_id):
    block = snippet(measurement_id)
    if EXISTING_GTAG_RE.search(html):
        html = re.sub(
            r"\s*<script async src=\"https://www\.googletagmanager\.com/gtag/js\?id=G-[A-Z0-9]+\"></script>\s*<script>[\s\S]*?</script>\s*",
            "\n" + block,
            html,
            count=1,
        )
        return html, "updated"
    if "</head>" not in html:
        raise ValueError("missing </head>")
    return html.replace("</head>", block + "</head>", 1), "inserted"


def main():
    parser = argparse.ArgumentParser(description="Apply a GA4 measurement ID to public HTML files.")
    parser.add_argument("--measurement-id", default=os.getenv("GA4_MEASUREMENT_ID", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    measurement_id = normalize_measurement_id(args.measurement_id)

    changed = []
    errors = []
    for path in public_html_files():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        html = path.read_text(encoding="utf-8")
        try:
            updated, action = apply_to_html(html, measurement_id)
        except ValueError as exc:
            errors.append({"file": rel, "error": str(exc)})
            continue
        if updated != html:
            changed.append({"file": rel, "action": action})
            if not args.dry_run:
                path.write_text(updated, encoding="utf-8")

    print(f"{'Would apply' if args.dry_run else 'Applied'} GA4_MEASUREMENT_ID={measurement_id} to {len(changed)} files.")
    for item in changed[:30]:
        print(f"{item['action']}: {item['file']}")
    if len(changed) > 30:
        print(f"... {len(changed) - 30} more files")
    if errors:
        for item in errors:
            print(f"error: {item['file']}: {item['error']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
