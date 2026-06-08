import json
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS_REPORT = ROOT / "reports" / "production-readiness-report.json"


def names(items):
    return [item.get("name", "") for item in items if item.get("name")]


def main():
    parser = argparse.ArgumentParser(description="Print the latest production readiness summary.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero when production readiness is incomplete.")
    args = parser.parse_args()

    if not READINESS_REPORT.exists():
        raise SystemExit("reports/production-readiness-report.json is missing. Run npm run ready first.")

    report = json.loads(READINESS_REPORT.read_text(encoding="utf-8"))
    summary = report.get("blocker_summary", {})
    quality = report.get("quality_snapshot", {})
    article_generation = report.get("article_generation_snapshot", {})
    seo = report.get("seo_adsense_snapshot", {})
    performance = report.get("performance_snapshot", {})
    missing_inputs = report.get("missing_external_inputs", [])

    print("Launch status")
    print(f"Ready for production submission: {str(bool(report.get('ready_for_production_submission'))).lower()}")
    print(f"Code or repository blockers: {', '.join(summary.get('code_or_repository_blockers', [])) or 'none'}")
    print(f"External input blockers: {', '.join(summary.get('external_input_blockers', [])) or 'none'}")
    print(f"Missing external inputs: {', '.join(names(missing_inputs)) or 'none'}")
    print(f"SITE_ORIGIN placeholders remaining: {quality.get('site_origin_placeholder_count', 'unknown')}")
    print(
        "Articles: "
        f"{article_generation.get('articles', 'unknown')} total, "
        f"{article_generation.get('publishedArticles', 'unknown')} published, "
        f"{article_generation.get('scheduledArticles', 'unknown')} scheduled, "
        f"quality {article_generation.get('minQualityScore', 'unknown')}-{article_generation.get('maxQualityScore', 'unknown')}"
    )
    print(
        "SEO/AdSense audit: "
        f"errors={seo.get('error_count', 'unknown')}, "
        f"warnings={seo.get('warning_count', 'unknown')}, "
        f"auto_ads_only={seo.get('adsense_auto_ads_only', 'unknown')}"
    )
    print(
        "Performance audit: "
        f"errors={performance.get('error_count', 'unknown')}, "
        f"warnings={performance.get('warning_count', 'unknown')}, "
        f"largest_html_bytes={performance.get('largest_html_bytes', 'unknown')}"
    )

    actions = report.get("next_required_actions", [])
    if actions:
        print("Next required actions:")
        for action in actions:
            print(f"- {action}")

    if args.require_ready and not report.get("ready_for_production_submission"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
