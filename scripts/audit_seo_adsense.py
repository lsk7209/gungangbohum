import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
REPORT_PATH = REPORT_DIR / "seo-adsense-audit-report.json"
ARTICLE_DIR = ROOT / "aca"
GUIDE_DIR = ROOT / "guides"
ADS_TXT_RE = re.compile(r"^google\.com,\s+pub-\d{16},\s+DIRECT,\s+f08c47fec0942fa\s*$")
TITLE_MIN_LENGTH = 30
TITLE_MAX_LENGTH = 70
DESCRIPTION_MIN_LENGTH = 90
DESCRIPTION_MAX_LENGTH = 170


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.meta = {}
        self.links = []
        self.headings = []
        self.images = []
        self.forms = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = values.get("name") or values.get("property")
            if key:
                self.meta[key] = values.get("content", "")
        if tag == "link":
            rel = values.get("rel", "")
            if rel:
                self.links.append(values)
        if tag == "a" and values.get("href"):
            self.links.append(values)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(tag)
        if tag == "img":
            self.images.append(values)
        if tag == "form":
            self.forms += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def public_html_files():
    return sorted(ROOT.glob("*.html")) + sorted(ARTICLE_DIR.glob("*.html")) + sorted(GUIDE_DIR.glob("*.html"))


def parse_html(path):
    parser = AuditParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def canonical(parser):
    for link in parser.links:
        if link.get("rel") == "canonical":
            return link.get("href", "")
    return ""


def is_readable_url(path):
    name = path.name
    if name in {"index.html", "404.html"}:
        return True
    stem = path.stem
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", stem)) and len(stem) <= 130


def heading_hierarchy_ok(headings):
    if headings.count("h1") != 1:
        return False
    previous = 0
    for heading in headings:
        level = int(heading[1])
        if previous and level > previous + 1:
            return False
        previous = level
    return True


def link_counts(path, parser):
    internal = 0
    external = 0
    for link in parser.links:
        href = link.get("href", "")
        if not href or href.startswith(("mailto:", "tel:")):
            continue
        if href.startswith(("http://", "https://")):
            if "{SITE_ORIGIN}" in href:
                internal += 1
            else:
                external += 1
        elif href.endswith(".xml") or href.endswith(".json"):
            continue
        else:
            internal += 1
    return internal, external


def keyword_front_signal(parser):
    title = parser.title.strip()
    description = parser.meta.get("description", "").strip()
    title_front = title[:70].lower()
    desc_front = description[:110].lower()
    target_terms = (
        "aca",
        "subsidy",
        "marketplace",
        "florida",
        "premium tax credit",
        "csr",
        "cost-sharing",
        "slcsp",
        "coverage",
        "privacy",
        "contact",
        "editorial",
        "sources",
    )
    return any(term in title_front for term in target_terms) and any(term in desc_front for term in target_terms)


def normalized_snippet_text(value):
    return re.sub(r"\s+", " ", value).strip()


def snippet_length_ok(value, minimum, maximum):
    length = len(normalized_snippet_text(value))
    return minimum <= length <= maximum


def add_duplicate_snippet_errors(pages, field, error_type, errors):
    seen = {}
    for page in pages:
        if page["noindex"]:
            continue
        value = normalized_snippet_text(page.get(field, ""))
        if not value:
            continue
        seen.setdefault(value, []).append(page["file"])
    for value, files in seen.items():
        if len(files) > 1:
            errors.append({"files": files, "type": error_type, "value": value})


def audit():
    html_files = public_html_files()
    pages = []
    errors = []
    warnings = []
    blog_articles = []

    for path in html_files:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        html = path.read_text(encoding="utf-8")
        parser = parse_html(path)
        page_errors = []
        page_warnings = []
        internal_links, external_links = link_counts(path, parser)
        title_text = normalized_snippet_text(parser.title)
        description_text = normalized_snippet_text(parser.meta.get("description", ""))
        noindex = parser.meta.get("robots", "").startswith("noindex")

        if not title_text:
            page_errors.append("missing_title")
        elif not noindex and not snippet_length_ok(title_text, TITLE_MIN_LENGTH, TITLE_MAX_LENGTH):
            page_errors.append("title_length_outside_search_snippet_range")
        if not description_text:
            page_errors.append("missing_meta_description")
        elif not noindex and not snippet_length_ok(description_text, DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH):
            page_errors.append("meta_description_length_outside_search_snippet_range")
        if not canonical(parser):
            page_errors.append("missing_canonical")
        if not heading_hierarchy_ok(parser.headings):
            page_errors.append("bad_heading_hierarchy")
        if any(not image.get("alt", "").strip() for image in parser.images):
            page_errors.append("image_missing_alt")
        if not is_readable_url(path):
            page_errors.append("unreadable_url")
        if "<ins" in html or "adsbygoogle" in html or "adslot" in html.lower():
            page_errors.append("manual_ad_slot_marker")
        if parser.forms:
            page_warnings.append("form_present_review_for_lead_capture")
        if noindex:
            pass
        elif not keyword_front_signal(parser):
            page_warnings.append("weak_keyword_front_signal")

        if rel.startswith("aca/") or rel == "aca-enhanced-subsidies-2026-florida.html":
            has_cta = 'class="cta"' in html or "index.html#calc" in html or "../index.html#calc" in html
            if not has_cta:
                page_errors.append("article_missing_cta")
            if internal_links < 2:
                page_errors.append("article_internal_links_below_2")
            if external_links < 1:
                page_errors.append("article_external_links_below_1")
            blog_articles.append(rel)

        for item in page_errors:
            errors.append({"file": rel, "type": item})
        for item in page_warnings:
            warnings.append({"file": rel, "type": item})
        pages.append({
            "file": rel,
            "title": bool(title_text),
            "title_text": title_text,
            "title_length_ok": noindex or snippet_length_ok(title_text, TITLE_MIN_LENGTH, TITLE_MAX_LENGTH),
            "meta_description": bool(description_text),
            "description_text": description_text,
            "description_length_ok": noindex or snippet_length_ok(description_text, DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH),
            "noindex": noindex,
            "canonical": bool(canonical(parser)),
            "heading_hierarchy": heading_hierarchy_ok(parser.headings),
            "images": len(parser.images),
            "images_with_alt": sum(1 for image in parser.images if image.get("alt", "").strip()),
            "readable_url": is_readable_url(path),
            "internal_links": internal_links,
            "external_links": external_links,
        })

    add_duplicate_snippet_errors(pages, "title_text", "duplicate_meta_title", errors)
    add_duplicate_snippet_errors(pages, "description_text", "duplicate_meta_description", errors)

    sitemap_exists = (ROOT / "sitemap.xml").exists()
    robots_exists = (ROOT / "robots.txt").exists()
    ads_txt_path = ROOT / "ads.txt"
    ads_txt_valid = False
    if not sitemap_exists:
        errors.append({"file": "sitemap.xml", "type": "missing_sitemap"})
    if not robots_exists:
        errors.append({"file": "robots.txt", "type": "missing_robots"})
    if not ads_txt_path.exists():
        errors.append({"file": "ads.txt", "type": "missing_ads_txt"})
    else:
        ads_txt_lines = [line.strip() for line in ads_txt_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        ads_txt_valid = any(ADS_TXT_RE.match(line) for line in ads_txt_lines)
        if not ads_txt_valid:
            errors.append({"file": "ads.txt", "type": "invalid_ads_txt"})

    checklist = {
        "meta_title_per_page": all(page["title"] for page in pages),
        "meta_title_length": all(page["title_length_ok"] for page in pages),
        "meta_title_unique": not any(error["type"] == "duplicate_meta_title" for error in errors),
        "meta_description_per_page": all(page["meta_description"] for page in pages),
        "meta_description_length": all(page["description_length_ok"] for page in pages),
        "meta_description_unique": not any(error["type"] == "duplicate_meta_description" for error in errors),
        "keyword_front_signal": len([w for w in warnings if w["type"] == "weak_keyword_front_signal"]) == 0,
        "canonical_per_page": all(page["canonical"] for page in pages),
        "sitemap_xml_present": sitemap_exists,
        "robots_txt_present": robots_exists,
        "ads_txt_present_valid": ads_txt_valid,
        "h_tags_per_page": all(page["heading_hierarchy"] for page in pages),
        "image_alt_text": all(page["images"] == page["images_with_alt"] for page in pages),
        "blog_cta_inlink_outlink": not any(error["type"].startswith("article_") for error in errors),
        "readable_urls": all(page["readable_url"] for page in pages),
        "adsense_auto_ads_only": not any(error["type"] == "manual_ad_slot_marker" for error in errors),
    }
    return {
        "pages_checked": len(pages),
        "article_pages_checked": len(blog_articles),
        "checklist": checklist,
        "passed": not errors,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "errors": errors,
        "warnings": warnings[:100],
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
