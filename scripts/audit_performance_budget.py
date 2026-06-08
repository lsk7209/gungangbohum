import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "aca"
GUIDE_DIR = ROOT / "guides"
CONTENT_DIR = ROOT / "content"
REPORT_DIR = ROOT / "reports"
REPORT_PATH = REPORT_DIR / "performance-budget-report.json"

HTML_MAX_BYTES = 75_000
ARTICLE_MAX_BYTES = 45_000
ARTICLE_AVG_MAX_BYTES = 34_000
BLOG_MAX_BYTES = 60_000
INDEX_MAX_BYTES = 65_000
QUEUE_MAX_BYTES = 500_000
SEARCH_INDEX_MAX_BYTES = 150_000
INLINE_STYLE_MAX_BYTES = 24_000
INLINE_SCRIPT_MAX_BYTES = 28_000


def rel(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def public_html_files():
    return sorted(ROOT.glob("*.html")) + sorted(ARTICLE_DIR.glob("*.html")) + sorted(GUIDE_DIR.glob("*.html"))


def inline_bytes(html, tag):
    pattern = rf"<{tag}\b[^>]*>([\s\S]*?)</{tag}>"
    return sum(len(match.encode("utf-8")) for match in re.findall(pattern, html, flags=re.IGNORECASE))


def header_value(vercel, source, key):
    for block in vercel.get("headers", []):
        if block.get("source") != source:
            continue
        for header in block.get("headers", []):
            if header.get("key", "").lower() == key.lower():
                return header.get("value", "")
    return ""


def audit():
    errors = []
    warnings = []
    html_files = public_html_files()
    html_sizes = []
    article_sizes = []
    inline_style_sizes = []
    inline_script_sizes = []

    for path in html_files:
        size = path.stat().st_size
        html_sizes.append((rel(path), size))
        if path.parent == ARTICLE_DIR:
            article_sizes.append(size)
        if size > HTML_MAX_BYTES:
            errors.append({"type": "html_file_over_budget", "file": rel(path), "bytes": size, "budget": HTML_MAX_BYTES})
        if path.parent == ARTICLE_DIR and size > ARTICLE_MAX_BYTES:
            errors.append({"type": "article_file_over_budget", "file": rel(path), "bytes": size, "budget": ARTICLE_MAX_BYTES})
        html = path.read_text(encoding="utf-8")
        style_size = inline_bytes(html, "style")
        script_size = inline_bytes(html, "script")
        inline_style_sizes.append((rel(path), style_size))
        inline_script_sizes.append((rel(path), script_size))
        if style_size > INLINE_STYLE_MAX_BYTES:
            errors.append({"type": "inline_style_over_budget", "file": rel(path), "bytes": style_size, "budget": INLINE_STYLE_MAX_BYTES})
        if script_size > INLINE_SCRIPT_MAX_BYTES:
            errors.append({"type": "inline_script_over_budget", "file": rel(path), "bytes": script_size, "budget": INLINE_SCRIPT_MAX_BYTES})

    article_avg = round(sum(article_sizes) / len(article_sizes)) if article_sizes else 0
    if article_avg > ARTICLE_AVG_MAX_BYTES:
        errors.append({"type": "article_average_over_budget", "bytes": article_avg, "budget": ARTICLE_AVG_MAX_BYTES})
    for file_name, budget in [("index.html", INDEX_MAX_BYTES), ("blog.html", BLOG_MAX_BYTES)]:
        path = ROOT / file_name
        if path.exists() and path.stat().st_size > budget:
            errors.append({"type": "static_page_over_budget", "file": file_name, "bytes": path.stat().st_size, "budget": budget})

    queue_path = CONTENT_DIR / "article-queue.json"
    search_index_path = CONTENT_DIR / "search-index.json"
    if queue_path.exists() and queue_path.stat().st_size > QUEUE_MAX_BYTES:
        warnings.append({"type": "article_queue_large", "file": rel(queue_path), "bytes": queue_path.stat().st_size, "budget": QUEUE_MAX_BYTES})
    if search_index_path.exists() and search_index_path.stat().st_size > SEARCH_INDEX_MAX_BYTES:
        errors.append({"type": "search_index_over_budget", "file": rel(search_index_path), "bytes": search_index_path.stat().st_size, "budget": SEARCH_INDEX_MAX_BYTES})

    vercel_path = ROOT / "vercel.json"
    if not vercel_path.exists():
        errors.append({"type": "missing_vercel_json"})
        vercel = {}
    else:
        vercel = json.loads(vercel_path.read_text(encoding="utf-8"))
    required_headers = [
        ("/(.*)\\.html", "Cache-Control", "must-revalidate"),
        ("/(.*)\\.html", "X-Content-Type-Options", "nosniff"),
        ("/(sitemap|feed|opensearch)\\.xml", "Content-Type", "application/xml"),
        ("/content/(.*)\\.json", "Content-Type", "application/json"),
    ]
    for source, key, expected in required_headers:
        value = header_value(vercel, source, key)
        if expected not in value:
            errors.append({"type": "missing_or_weak_header", "source": source, "header": key, "expected": expected, "actual": value})

    largest_html = sorted(html_sizes, key=lambda item: item[1], reverse=True)[:10]
    largest_style = sorted(inline_style_sizes, key=lambda item: item[1], reverse=True)[:5]
    largest_script = sorted(inline_script_sizes, key=lambda item: item[1], reverse=True)[:5]
    return {
        "passed": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "html_files_checked": len(html_files),
        "budgets": {
            "html_max_bytes": HTML_MAX_BYTES,
            "article_max_bytes": ARTICLE_MAX_BYTES,
            "article_avg_max_bytes": ARTICLE_AVG_MAX_BYTES,
            "blog_max_bytes": BLOG_MAX_BYTES,
            "index_max_bytes": INDEX_MAX_BYTES,
            "article_queue_warning_bytes": QUEUE_MAX_BYTES,
            "search_index_max_bytes": SEARCH_INDEX_MAX_BYTES,
            "inline_style_max_bytes": INLINE_STYLE_MAX_BYTES,
            "inline_script_max_bytes": INLINE_SCRIPT_MAX_BYTES,
        },
        "measurements": {
            "largest_html": [{"file": file, "bytes": size} for file, size in largest_html],
            "article_average_bytes": article_avg,
            "largest_inline_style": [{"file": file, "bytes": size} for file, size in largest_style],
            "largest_inline_script": [{"file": file, "bytes": size} for file, size in largest_script],
            "article_queue_bytes": queue_path.stat().st_size if queue_path.exists() else None,
            "search_index_bytes": search_index_path.stat().st_size if search_index_path.exists() else None,
        },
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.write_report:
        REPORT_DIR.mkdir(exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
