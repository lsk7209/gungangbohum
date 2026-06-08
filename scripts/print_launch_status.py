import json
import argparse
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS_REPORT = ROOT / "reports" / "production-readiness-report.json"
ARTICLE_QUEUE = ROOT / "content" / "article-queue.json"
KST = timezone(timedelta(hours=9))
READINESS_INPUTS = [
    ROOT / "reports" / "article-generation-report.json",
    ROOT / "reports" / "content-quality-report.json",
    ROOT / "reports" / "performance-budget-report.json",
    ROOT / "reports" / "seo-adsense-audit-report.json",
]


def names(items):
    return [item.get("name", "") for item in items if item.get("name")]


def newer_inputs():
    if not READINESS_REPORT.exists():
        return []
    readiness_mtime = READINESS_REPORT.stat().st_mtime
    return [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in READINESS_INPUTS
        if path.exists() and path.stat().st_mtime > readiness_mtime
    ]


def current_git_changed_paths():
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return ["<git status unavailable>"]
    ignored = {"reports/production-readiness-report.json"}
    changed = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].replace("\\", "/")
        if path not in ignored:
            changed.append(path)
    return changed


def display_code_blockers(summary, current_changed_paths, stale_git_status):
    blockers = list(summary.get("code_or_repository_blockers", []))
    if stale_git_status and not current_changed_paths:
        blockers = [name for name in blockers if name != "git_worktree_clean"]
    if current_changed_paths and "git_worktree_clean" not in blockers:
        blockers.append("git_worktree_clean")
    return blockers


def display_actions(actions, current_changed_paths, stale_git_status):
    filtered = []
    for action in actions:
        if stale_git_status and not current_changed_paths and action == "Commit the local work before git push.":
            continue
        filtered.append(action)
    if current_changed_paths and "Commit the local work before git push." not in filtered:
        filtered.append("Commit the local work before git push.")
    return filtered


def parse_publish_at(value):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def next_scheduled_article():
    if not ARTICLE_QUEUE.exists():
        return None
    queue = json.loads(ARTICLE_QUEUE.read_text(encoding="utf-8"))
    scheduled = [
        item
        for item in queue
        if not item.get("is_published") and item.get("publishAt")
    ]
    if not scheduled:
        return None
    return min(scheduled, key=lambda item: parse_publish_at(item["publishAt"]))


def main():
    parser = argparse.ArgumentParser(description="Print the latest production readiness summary.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero when production readiness is incomplete.")
    args = parser.parse_args()

    if not READINESS_REPORT.exists():
        raise SystemExit("reports/production-readiness-report.json is missing. Run npm run ready first.")

    report = json.loads(READINESS_REPORT.read_text(encoding="utf-8"))
    stale_inputs = newer_inputs()
    report_git = report.get("git_snapshot", {})
    current_changed_paths = current_git_changed_paths()
    stale_git_status = bool(report_git.get("changed_paths") and not current_changed_paths)
    current_dirty_after_clean_report = bool(report_git.get("worktree_clean") and current_changed_paths)
    summary = report.get("blocker_summary", {})
    quality = report.get("quality_snapshot", {})
    article_generation = report.get("article_generation_snapshot", {})
    seo = report.get("seo_adsense_snapshot", {})
    performance = report.get("performance_snapshot", {})
    missing_inputs = report.get("missing_external_inputs", [])

    print("Launch status")
    if stale_inputs:
        print(f"Warning: readiness report may be stale. Run npm run ready. Newer inputs: {', '.join(stale_inputs)}")
    if stale_git_status:
        print("Warning: readiness report captured uncommitted files, but the current worktree is clean. Run npm run ready.")
    if current_dirty_after_clean_report:
        print("Warning: readiness report captured a clean worktree, but the current worktree now has uncommitted files. Run npm run ready.")
    print(f"Ready for production submission: {str(bool(report.get('ready_for_production_submission'))).lower()}")
    print(f"Current worktree: {'dirty' if current_changed_paths else 'clean'}")
    print(f"Code or repository blockers: {', '.join(display_code_blockers(summary, current_changed_paths, stale_git_status)) or 'none'}")
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
    next_article = next_scheduled_article()
    if next_article:
        print(f"Next scheduled article: {next_article.get('publishAt')} - {next_article.get('title')}")
    else:
        print("Next scheduled article: none")
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
    print("Remote CI gate: run npm run launch:check-ci before launch preparation")

    actions = display_actions(report.get("next_required_actions", []), current_changed_paths, stale_git_status)
    if actions:
        print("Next required actions:")
        for action in actions:
            print(f"- {action}")

    if args.require_ready and not report.get("ready_for_production_submission"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
