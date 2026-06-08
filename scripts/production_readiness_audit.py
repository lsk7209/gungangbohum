import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
QUALITY_REPORT = REPORT_DIR / "content-quality-report.json"
READINESS_REPORT = REPORT_DIR / "production-readiness-report.json"


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


def audit():
    quality = load_quality_report()
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
    worktree_clean = bool(git_status and git_status.returncode == 0 and not git_status.stdout.strip())
    remotes = []
    if git_remote and git_remote.returncode == 0:
        remotes = [line.strip() for line in git_remote.stdout.splitlines() if line.strip()]
    remote_repo = ""
    if remotes:
        repo_view = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
        if repo_view and repo_view.returncode == 0:
            remote_repo = repo_view.stdout.strip()

    gsc_env = {
        "GSC_SITE_URL": bool(os.getenv("GSC_SITE_URL")),
        "GSC_SITEMAP_URL": bool(os.getenv("GSC_SITEMAP_URL")),
        "GSC_CLIENT_JSON": bool(os.getenv("GSC_CLIENT_JSON") or (Path(r"D:\env\adsense_oauth_client.json").exists())),
        "GSC_TOKEN_JSON": bool(os.getenv("GSC_TOKEN_JSON") or (Path(r"D:\env\gsc_token.json").exists())),
    }
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

    checks = [
        {
            "name": "content_quality",
            "ok": bool(quality and quality.get("error_count") == 0),
            "detail": "content-quality-report.json has error_count 0" if quality else "content-quality-report.json is missing",
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
            "name": "gsc_configuration",
            "ok": all(gsc_env.values()),
            "detail": gsc_env,
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
    next_required_actions = []
    if public_with_placeholder:
        next_required_actions.append("Assign an HTTPS production domain and run npm run check:production.")
    if not has_commit or not worktree_clean:
        next_required_actions.append("Commit the local work before git push.")
    if not remotes:
        next_required_actions.append("Connect this folder to a GitHub remote repository before git push.")
    if not all(gsc_env.values()):
        next_required_actions.append("Set GSC_SITE_URL and GSC_SITEMAP_URL, then run npm run gsc:submit after the domain is verified in Search Console.")
    if remote_repo and not github_gsc["GSC_SITE_URL_variable"]:
        next_required_actions.append("Set GitHub repository variable GSC_SITE_URL after the production domain is assigned.")
    if remote_repo and not github_gsc["GSC_SITEMAP_URL_variable"]:
        next_required_actions.append("Set GitHub repository variable GSC_SITEMAP_URL after the production domain is assigned.")

    report = {
        "ready_for_production_submission": ready,
        "checks": checks,
        "blockers": blockers,
        "quality_snapshot": {
            "article_files": quality.get("article_files") if quality else None,
            "guide_files": quality.get("guide_files") if quality else None,
            "sitemap_urls": quality.get("sitemap_urls") if quality else None,
            "error_count": quality.get("error_count") if quality else None,
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
        READINESS_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.require_ready and not report["ready_for_production_submission"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
