import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from gsc_submit_sitemap import (
    _json_from_env_or_file,
    normalize_site_url,
    normalize_sitemap_url,
    validate_sitemap_belongs_to_site,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
QUALITY_REPORT = REPORT_DIR / "content-quality-report.json"
ARTICLE_GENERATION_REPORT = REPORT_DIR / "article-generation-report.json"
SEO_ADSENSE_REPORT = REPORT_DIR / "seo-adsense-audit-report.json"
PERFORMANCE_REPORT = REPORT_DIR / "performance-budget-report.json"
READINESS_REPORT = REPORT_DIR / "production-readiness-report.json"
GSC_WORKFLOW = ROOT / ".github" / "workflows" / "gsc-sitemap-submit.yml"
EXTERNAL_INPUT_BLOCKERS = {
    "production_origin_applied",
    "production_contact_channel",
    "gsc_configuration",
    "github_gsc_configuration",
}


def run_git(args):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result


def run_gh(args):
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result


def worktree_has_uncommitted_changes(result):
    if not result or result.returncode != 0:
        return True
    ignored = {"reports/production-readiness-report.json"}
    changed = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].replace("\\", "/")
        if path not in ignored:
            changed.append(path)
    return bool(changed)


def public_files():
    patterns = ["*.html", "aca/*.html", "guides/*.html", "*.xml", "*.txt", "content/*.json"]
    seen = set()
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def load_quality_report():
    if not QUALITY_REPORT.exists():
        return None
    return json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))


def load_json_report(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def report_pass_status(path, label):
    report = load_json_report(path)
    if not report:
        return False, f"{path.name} is missing", None
    passed = bool(report.get("passed") and report.get("error_count") == 0 and report.get("warning_count", 0) == 0)
    if passed:
        return True, f"{label} passed with 0 errors and 0 warnings", report
    return False, {
        "message": f"{label} did not pass cleanly",
        "passed": bool(report.get("passed")),
        "error_count": report.get("error_count"),
        "warning_count": report.get("warning_count"),
    }, report


def article_generation_status():
    report = load_json_report(ARTICLE_GENERATION_REPORT)
    if not report:
        return False, f"{ARTICLE_GENERATION_REPORT.name} is missing", None

    articles = report.get("articles", 0)
    min_quality = report.get("minQualityScore", 0)
    codex_only = report.get("codexOnlyGenerationArticles", 0)
    manual_ad_slots = report.get("manualAdSlotArticles", 0)
    ok = articles >= 200 and min_quality >= 90 and codex_only == articles and manual_ad_slots == 0
    if ok:
        return True, "article generation contract passed: 200+ articles, quality >= 90, Codex-only, no manual ad slots", report
    return False, {
        "message": "article generation contract did not pass",
        "articles": articles,
        "minQualityScore": min_quality,
        "codexOnlyGenerationArticles": codex_only,
        "manualAdSlotArticles": manual_ad_slots,
    }, report


def contact_channel_status():
    contact_page = ROOT / "contact.html"
    if not contact_page.exists():
        return False, "contact.html is missing"
    text = contact_page.read_text(encoding="utf-8")
    prelaunch_markers = [
        "not yet attached to a production domain",
        "public contact channel must be added",
        "public contact channel will be finalized",
    ]
    if any(marker in text for marker in prelaunch_markers):
        return False, "contact page still contains prelaunch contact-channel language"
    if not re.search(r'href="mailto:[^"]+@[^"]+\.[^"]+"|href="https://[^"]+"', text):
        return False, "contact page does not expose a public email or https contact URL"
    return True, "production public contact channel is present"


def gsc_workflow_status():
    if not GSC_WORKFLOW.exists():
        return False, {"file": str(GSC_WORKFLOW.relative_to(ROOT)), "missing": True}
    workflow = GSC_WORKFLOW.read_text(encoding="utf-8")
    markers = {
        "push_trigger": "push:" in workflow,
        "schedule_trigger": "schedule:" in workflow,
        "manual_trigger": "workflow_dispatch:" in workflow,
        "manual_site_url_input": "site_url:" in workflow,
        "manual_sitemap_url_input": "sitemap_url:" in workflow,
        "uses_gsc_site_url": "GSC_SITE_URL" in workflow,
        "uses_gsc_sitemap_url": "GSC_SITEMAP_URL" in workflow,
        "validates_config": "--check-config" in workflow,
        "submits_sitemap": "scripts/gsc_submit_sitemap.py" in workflow,
    }
    return all(markers.values()), markers


def gsc_configuration_status():
    detail = {
        "GSC_SITE_URL": False,
        "GSC_SITEMAP_URL": False,
        "GSC_CLIENT_JSON": False,
        "GSC_TOKEN_JSON": False,
        "errors": [],
    }
    site_url = ""
    sitemap_url = ""
    try:
        site_url = normalize_site_url(os.getenv("GSC_SITE_URL", ""))
        detail["GSC_SITE_URL"] = True
    except ValueError as exc:
        detail["errors"].append({"name": "GSC_SITE_URL", "error": str(exc)})
    try:
        sitemap_url = normalize_sitemap_url(os.getenv("GSC_SITEMAP_URL", ""))
        detail["GSC_SITEMAP_URL"] = True
    except ValueError as exc:
        detail["errors"].append({"name": "GSC_SITEMAP_URL", "error": str(exc)})
    if site_url and sitemap_url:
        try:
            validate_sitemap_belongs_to_site(site_url, sitemap_url)
            detail["GSC_URL_ALIGNMENT"] = True
        except ValueError as exc:
            detail["GSC_URL_ALIGNMENT"] = False
            detail["errors"].append({"name": "GSC_URL_ALIGNMENT", "error": str(exc)})
    else:
        detail["GSC_URL_ALIGNMENT"] = False
    for name, fallback in [
        ("GSC_CLIENT_JSON", r"D:\env\adsense_oauth_client.json"),
        ("GSC_TOKEN_JSON", r"D:\env\gsc_token.json"),
    ]:
        try:
            _json_from_env_or_file(name, fallback)
            detail[name] = True
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
            detail["errors"].append({"name": name, "error": str(exc)})
    ok = all(detail[name] for name in ("GSC_SITE_URL", "GSC_SITEMAP_URL", "GSC_URL_ALIGNMENT", "GSC_CLIENT_JSON", "GSC_TOKEN_JSON"))
    if ok:
        detail.pop("errors")
    return ok, detail


def audit():
    quality = load_quality_report()
    article_generation_ok, article_generation_detail, article_generation = article_generation_status()
    seo_adsense_ok, seo_adsense_detail, seo_adsense = report_pass_status(SEO_ADSENSE_REPORT, "SEO and AdSense audit")
    performance_ok, performance_detail, performance = report_pass_status(PERFORMANCE_REPORT, "Performance budget audit")
    public_with_placeholder = []
    for path in public_files():
        if "{SITE_ORIGIN}" in path.read_text(encoding="utf-8"):
            public_with_placeholder.append(str(path.relative_to(ROOT)))

    git_root = run_git(["rev-parse", "--show-toplevel"])
    git_remote = run_git(["remote", "-v"])
    git_head = run_git(["rev-parse", "--verify", "HEAD"])
    git_status = run_git(["status", "--short"])
    in_git_repo = bool(git_root and git_root.returncode == 0)
    has_commit = bool(git_head and git_head.returncode == 0)
    worktree_clean = not worktree_has_uncommitted_changes(git_status)
    remotes = []
    if git_remote and git_remote.returncode == 0:
        remotes = [line.strip() for line in git_remote.stdout.splitlines() if line.strip()]
    remote_repo = ""
    if remotes:
        repo_view = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
        if repo_view and repo_view.returncode == 0:
            remote_repo = repo_view.stdout.strip()

    gsc_config_ok, gsc_config_detail = gsc_configuration_status()
    github_gsc = {
        "repo": remote_repo,
        "GSC_CLIENT_JSON_secret": False,
        "GSC_TOKEN_JSON_secret": False,
        "GSC_SITE_URL_variable": False,
        "GSC_SITEMAP_URL_variable": False,
    }
    if remote_repo:
        secret_list = run_gh(["secret", "list", "--repo", remote_repo])
        variable_list = run_gh(["variable", "list", "--repo", remote_repo])
        if secret_list and secret_list.returncode == 0:
            secret_names = {line.split()[0] for line in secret_list.stdout.splitlines() if line.strip()}
            github_gsc["GSC_CLIENT_JSON_secret"] = "GSC_CLIENT_JSON" in secret_names
            github_gsc["GSC_TOKEN_JSON_secret"] = "GSC_TOKEN_JSON" in secret_names
        if variable_list and variable_list.returncode == 0:
            variable_names = {line.split()[0] for line in variable_list.stdout.splitlines() if line.strip()}
            github_gsc["GSC_SITE_URL_variable"] = "GSC_SITE_URL" in variable_names
            github_gsc["GSC_SITEMAP_URL_variable"] = "GSC_SITEMAP_URL" in variable_names

    contact_channel_ok, contact_channel_detail = contact_channel_status()
    gsc_workflow_ok, gsc_workflow_detail = gsc_workflow_status()

    checks = [
        {
            "name": "content_quality",
            "ok": bool(quality and quality.get("error_count") == 0),
            "detail": "content-quality-report.json has error_count 0" if quality else "content-quality-report.json is missing",
        },
        {
            "name": "article_generation_contract",
            "ok": article_generation_ok,
            "detail": article_generation_detail,
        },
        {
            "name": "seo_adsense_audit",
            "ok": seo_adsense_ok,
            "detail": seo_adsense_detail,
        },
        {
            "name": "performance_budget_audit",
            "ok": performance_ok,
            "detail": performance_detail,
        },
        {
            "name": "production_origin_applied",
            "ok": not public_with_placeholder,
            "detail": f"{len(public_with_placeholder)} public files still contain {{SITE_ORIGIN}}",
        },
        {
            "name": "git_repository",
            "ok": in_git_repo,
            "detail": git_root.stdout.strip() if in_git_repo else "workspace is not a git repository",
        },
        {
            "name": "git_has_commit",
            "ok": has_commit,
            "detail": "HEAD exists" if has_commit else "repository has no commits yet",
        },
        {
            "name": "git_worktree_clean",
            "ok": worktree_clean,
            "detail": "worktree clean" if worktree_clean else "worktree has uncommitted or untracked files",
        },
        {
            "name": "github_remote",
            "ok": bool(remotes),
            "detail": remotes[:4] if remotes else "no git remotes available",
        },
        {
            "name": "production_contact_channel",
            "ok": contact_channel_ok,
            "detail": contact_channel_detail,
        },
        {
            "name": "gsc_workflow_automation",
            "ok": gsc_workflow_ok,
            "detail": gsc_workflow_detail,
        },
        {
            "name": "gsc_configuration",
            "ok": gsc_config_ok,
            "detail": gsc_config_detail,
        },
        {
            "name": "github_gsc_configuration",
            "ok": all([
                github_gsc["GSC_CLIENT_JSON_secret"],
                github_gsc["GSC_TOKEN_JSON_secret"],
                github_gsc["GSC_SITE_URL_variable"],
                github_gsc["GSC_SITEMAP_URL_variable"],
            ]),
            "detail": github_gsc,
        },
    ]

    ready = all(item["ok"] for item in checks)
    blockers = [item for item in checks if not item["ok"]]
    blocker_summary = {
        "external_input_blockers": [item["name"] for item in blockers if item["name"] in EXTERNAL_INPUT_BLOCKERS],
        "code_or_repository_blockers": [item["name"] for item in blockers if item["name"] not in EXTERNAL_INPUT_BLOCKERS],
    }
    missing_external_inputs = []
    if public_with_placeholder:
        missing_external_inputs.append({
            "name": "SITE_ORIGIN",
            "detail": "Assign the HTTPS production origin, then run npm run launch:prepare or npm run check:production.",
        })
    if not contact_channel_ok:
        missing_external_inputs.append({
            "name": "PUBLIC_CONTACT_EMAIL_OR_URL",
            "detail": "Provide PUBLIC_CONTACT_EMAIL or PUBLIC_CONTACT_URL so contact.html exposes a production public contact channel.",
        })
    if not gsc_config_detail.get("GSC_SITE_URL"):
        missing_external_inputs.append({
            "name": "GSC_SITE_URL",
            "detail": "Set the verified Search Console URL-prefix property or covering sc-domain property after the production domain is assigned.",
        })
    if not gsc_config_detail.get("GSC_SITEMAP_URL"):
        missing_external_inputs.append({
            "name": "GSC_SITEMAP_URL",
            "detail": "Set the production sitemap URL, normally SITE_ORIGIN + /sitemap.xml.",
        })
    if remote_repo and not github_gsc["GSC_SITE_URL_variable"]:
        missing_external_inputs.append({
            "name": "GITHUB_VAR_GSC_SITE_URL",
            "detail": "Set the GitHub repository variable GSC_SITE_URL after the production domain is assigned.",
        })
    if remote_repo and not github_gsc["GSC_SITEMAP_URL_variable"]:
        missing_external_inputs.append({
            "name": "GITHUB_VAR_GSC_SITEMAP_URL",
            "detail": "Set the GitHub repository variable GSC_SITEMAP_URL after the production domain is assigned.",
        })
    next_required_actions = []
    if not article_generation_ok:
        next_required_actions.append("Run npm run generate and fix article generation contract issues before production submission.")
    if not seo_adsense_ok:
        next_required_actions.append("Run npm run audit:seo and fix SEO or AdSense audit issues before production submission.")
    if not performance_ok:
        next_required_actions.append("Run npm run audit:performance and fix static performance budget issues before production submission.")
    if public_with_placeholder:
        next_required_actions.append("Assign an HTTPS production domain and run npm run check:production.")
    if not has_commit or not worktree_clean:
        next_required_actions.append("Commit the local work before git push.")
    if not remotes:
        next_required_actions.append("Connect this folder to a GitHub remote repository before git push.")
    if not contact_channel_ok:
        next_required_actions.append("Replace the prelaunch contact notice with a production public contact channel.")
    if not gsc_workflow_ok:
        next_required_actions.append("Repair .github/workflows/gsc-sitemap-submit.yml before relying on automatic sitemap submission.")
    if not gsc_config_ok:
        next_required_actions.append("Set GSC_SITE_URL and GSC_SITEMAP_URL, then run npm run gsc:submit after the domain is verified in Search Console.")
    if remote_repo and not github_gsc["GSC_SITE_URL_variable"]:
        next_required_actions.append("Set GitHub repository variable GSC_SITE_URL after the production domain is assigned.")
    if remote_repo and not github_gsc["GSC_SITEMAP_URL_variable"]:
        next_required_actions.append("Set GitHub repository variable GSC_SITEMAP_URL after the production domain is assigned.")

    report = {
        "ready_for_production_submission": ready,
        "checks": checks,
        "blockers": blockers,
        "blocker_summary": blocker_summary,
        "missing_external_inputs": missing_external_inputs,
        "quality_snapshot": {
            "article_files": quality.get("article_files") if quality else None,
            "guide_files": quality.get("guide_files") if quality else None,
            "sitemap_urls": quality.get("sitemap_urls") if quality else None,
            "site_origin_placeholder_count": len(public_with_placeholder),
            "site_origin_placeholder_sample": public_with_placeholder[:10],
            "public_origin_mismatch_count": quality.get("public_origin_mismatch_count") if quality else None,
            "error_count": quality.get("error_count") if quality else None,
        },
        "article_generation_snapshot": {
            "articles": article_generation.get("articles") if article_generation else None,
            "publishedArticles": article_generation.get("publishedArticles") if article_generation else None,
            "scheduledArticles": article_generation.get("scheduledArticles") if article_generation else None,
            "minQualityScore": article_generation.get("minQualityScore") if article_generation else None,
            "maxQualityScore": article_generation.get("maxQualityScore") if article_generation else None,
            "codexOnlyGenerationArticles": article_generation.get("codexOnlyGenerationArticles") if article_generation else None,
            "manualAdSlotArticles": article_generation.get("manualAdSlotArticles") if article_generation else None,
        },
        "seo_adsense_snapshot": {
            "pages_checked": seo_adsense.get("pages_checked") if seo_adsense else None,
            "error_count": seo_adsense.get("error_count") if seo_adsense else None,
            "warning_count": seo_adsense.get("warning_count") if seo_adsense else None,
            "ads_txt_present_valid": seo_adsense.get("checklist", {}).get("ads_txt_present_valid") if seo_adsense else None,
            "adsense_auto_ads_only": seo_adsense.get("checklist", {}).get("adsense_auto_ads_only") if seo_adsense else None,
        },
        "performance_snapshot": {
            "html_files_checked": performance.get("html_files_checked") if performance else None,
            "error_count": performance.get("error_count") if performance else None,
            "warning_count": performance.get("warning_count") if performance else None,
            "largest_html_bytes": (
                performance.get("measurements", {}).get("largest_html", [{}])[0].get("bytes")
                if performance and performance.get("measurements", {}).get("largest_html")
                else None
            ),
            "article_average_bytes": performance.get("measurements", {}).get("article_average_bytes") if performance else None,
        },
        "next_required_actions": next_required_actions,
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.write_report:
        REPORT_DIR.mkdir(exist_ok=True)
        READINESS_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.require_ready and not report["ready_for_production_submission"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
