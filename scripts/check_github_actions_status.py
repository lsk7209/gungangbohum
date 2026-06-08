import argparse
import json
import subprocess


def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None


def git_value(args):
    result = run(["git", *args])
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()


def gh_json(args):
    result = run(["gh", *args])
    if result is None:
        raise RuntimeError("GitHub CLI is not available")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh command failed")
    return json.loads(result.stdout or "[]")


def repo_name():
    result = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if result is None:
        raise RuntimeError("GitHub CLI is not available")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh repo view failed")
    return result.stdout.strip()


def workflow_runs(repo, branch, workflow, limit=20):
    return gh_json([
        "run",
        "list",
        "--repo",
        repo,
        "--branch",
        branch,
        "--workflow",
        workflow,
        "--json",
        "databaseId,headSha,status,conclusion,workflowName,displayTitle,createdAt,event",
        "--limit",
        str(limit),
    ])


def run_for_head(runs, head):
    return next((item for item in runs if item.get("headSha") == head), None)


def run_summary(item):
    if not item:
        return None
    return {
        "databaseId": item.get("databaseId"),
        "workflowName": item.get("workflowName"),
        "displayTitle": item.get("displayTitle"),
        "status": item.get("status"),
        "conclusion": item.get("conclusion"),
        "createdAt": item.get("createdAt"),
        "event": item.get("event"),
        "headSha": item.get("headSha"),
    }


def check_workflow(repo, branch, head, workflow, required=True):
    runs = workflow_runs(repo, branch, workflow)
    current = run_for_head(runs, head)
    latest = runs[0] if runs else None
    ok = bool(current and current.get("status") == "completed" and current.get("conclusion") == "success")
    if not required and current is None:
        ok = True
    return {
        "name": workflow,
        "ok": ok,
        "required": required,
        "current_head_run": run_summary(current),
        "latest_run": run_summary(latest),
    }


def main():
    parser = argparse.ArgumentParser(description="Check GitHub Actions status for the current launch commit.")
    parser.add_argument("--require-gsc-success", action="store_true", help="Require the GSC sitemap workflow to have succeeded for the current HEAD.")
    args = parser.parse_args()

    head = git_value(["rev-parse", "--verify", "HEAD"])
    branch = git_value(["branch", "--show-current"]) or "main"
    repo = repo_name()
    checks = [
        check_workflow(repo, branch, head, "Content quality", required=True),
        check_workflow(repo, branch, head, "Submit sitemap to Google Search Console", required=args.require_gsc_success),
    ]
    report = {
        "passed": all(item["ok"] for item in checks),
        "repo": repo,
        "branch": branch,
        "head": head,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
