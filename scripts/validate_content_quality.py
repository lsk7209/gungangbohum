import argparse
import json
import re
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "aca"
GUIDE_DIR = ROOT / "guides"
CONTENT_DIR = ROOT / "content"
REPORT_DIR = ROOT / "reports"

BAD_PATTERNS = re.compile(
    r"insupang|healthgotoo|coverclarity\.com|adsbygoogle|Advertisement|adslot|<ins|"
    r"\?\?/(?:span|button|a|div)>|\?[\uBD4F\uBE29]|\?\?\{money|\"\?\? \+ money|"
    r"\.nav nav\{display:none\}|\.mainnav\s*\{\s*display:\s*none|"
    r"\uCA0C|\u0431\u0434",
    re.IGNORECASE,
)
CLUSTER_ARTICLES = {
    "County and rating area",
    "Life event and income change",
    "Plan selection and out-of-pocket costs",
    "Tax, MAGI, and reconciliation",
    "Official verification and troubleshooting",
}

HUB_INDEXES = set(range(60, 80)) | set(range(100, 105)) | set(range(140, 145))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.headings = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(tag)
        if tag == "img":
            self.images.append(values)


def words_from_html(html):
    text = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>|<[^>]+>", " ", html)
    return len(re.findall(r"\b[A-Za-z][A-Za-z']*\b", text))


def body_sentences_from_html(html):
    body = re.search(r"<article[\s\S]*?</article>", html)
    text = body.group(0) if body else html
    text = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>|<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    skip_fragments = [
        "Official source",
        "Reviewed by CoverClarity editorial desk",
        "Internal links:",
        "Editorial standards for this ACA estimate",
        "Related guide path",
    ]
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = sentence.strip()
        if len(sentence) < 90:
            continue
        if any(fragment in sentence for fragment in skip_fragments):
            continue
        sentences.append(sentence)
    return sentences


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def origin_from_canonical(url):
    if url.startswith("{SITE_ORIGIN}"):
        return "{SITE_ORIGIN}"
    match = re.match(r"https://[^/]+", url)
    return match.group(0) if match else ""


def schema_types(html):
    types = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
        types.append(json.loads(raw).get("@type"))
    return types


def schemas_from_html(html):
    return [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html)]


def parse_page(path):
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def validate_html_structure(files):
    errors = []
    parsers = {path: parse_page(path) for path in files}
    for path, parser in parsers.items():
        html = path.read_text(encoding="utf-8")
        if "<main" not in html:
            errors.append({"type": "html_missing_main", "file": str(path.relative_to(ROOT))})
        if parser.headings.count("h1") != 1:
            errors.append({
                "type": "html_bad_h1_count",
                "file": str(path.relative_to(ROOT)),
                "count": parser.headings.count("h1"),
            })
        previous_level = 0
        for heading in parser.headings:
            level = int(heading[1])
            if previous_level and level > previous_level + 1:
                errors.append({
                    "type": "html_heading_hierarchy_jump",
                    "file": str(path.relative_to(ROOT)),
                    "from": f"h{previous_level}",
                    "to": heading,
                })
            previous_level = level
        for image in parser.images:
            if "alt" not in image or not image.get("alt", "").strip():
                errors.append({
                    "type": "html_image_missing_alt",
                    "file": str(path.relative_to(ROOT)),
                    "src": image.get("src", ""),
                })
        for href in parser.links:
            if href.startswith(("http://", "https://", "mailto:", "tel:")) or href.startswith("{SITE_ORIGIN}"):
                continue
            target_part, fragment = href.split("#", 1) if "#" in href else (href, "")
            if not target_part:
                target = path
            else:
                target = (path.parent / unquote(urlsplit(target_part).path)).resolve()
            if target_part and not target.exists():
                errors.append({
                    "type": "html_broken_internal_link",
                    "file": str(path.relative_to(ROOT)),
                    "href": href,
                })
                continue
            if fragment:
                try:
                    target_path = Path(target)
                    target_parser = parsers.get(target_path) or parse_page(target_path)
                except OSError:
                    continue
                if fragment not in target_parser.ids:
                    errors.append({
                        "type": "html_broken_fragment",
                        "file": str(path.relative_to(ROOT)),
                        "href": href,
                    })
    return errors


def validate_home_calculator(html):
    errors = []
    required_markers = [
        ('id="calc"', "calc_anchor"),
        ('id="calculate"', "calculate_button"),
        ('id="results"', "results_region"),
        ("function estimate()", "estimate_function"),
        ("function renderResults()", "render_results_function"),
        ("function applicableEnhanced", "enhanced_formula"),
        ("function applicableOriginal", "original_formula"),
        ("coverageGap", "coverage_gap_logic"),
        ("extra savings called CSR", "csr_label"),
        ("history.replaceState", "shareable_query_state"),
    ]
    for needle, label in required_markers:
        if needle not in html:
            errors.append({"type": f"home_calculator_missing_{label}"})
    if "−${money(res.enhanced.credit)}/mo" not in html:
        errors.append({"type": "home_calculator_enhanced_credit_format"})
    if '"−" + money(res.original.credit) + "/mo"' not in html:
        errors.append({"type": "home_calculator_original_credit_format"})
    if re.search(r"\?\?/(?:span|button|a|div)>|\?\?\{money|\"\?\? \+ money", html):
        errors.append({"type": "home_calculator_broken_markup_or_money_string"})
    return errors


def validate(require_site_origin=False):
    errors = []
    package_path = ROOT / "package.json"
    vercel_path = ROOT / "vercel.json"
    quality_workflow_path = ROOT / ".github" / "workflows" / "content-quality.yml"
    gsc_workflow_path = ROOT / ".github" / "workflows" / "gsc-sitemap-submit.yml"
    readme_path = ROOT / "README.md"
    phase0_report_path = ROOT / "docs" / "phase0-verification-report.md"
    readiness_script_path = ROOT / "scripts" / "production_readiness_audit.py"
    launch_script_path = ROOT / "scripts" / "launch_prepare.py"
    contact_script_path = ROOT / "scripts" / "apply_contact_channel.py"
    ads_txt_script_path = ROOT / "scripts" / "apply_ads_txt.py"
    ga4_script_path = ROOT / "scripts" / "apply_ga4_measurement.py"
    seo_audit_script_path = ROOT / "scripts" / "audit_seo_adsense.py"
    seo_audit_report_path = ROOT / "reports" / "seo-adsense-audit-report.json"
    performance_audit_script_path = ROOT / "scripts" / "audit_performance_budget.py"
    performance_audit_report_path = ROOT / "reports" / "performance-budget-report.json"
    for path, label in [
        (package_path, "package_json"),
        (vercel_path, "vercel_json"),
        (quality_workflow_path, "content_quality_workflow"),
        (gsc_workflow_path, "gsc_sitemap_workflow"),
        (readme_path, "readme"),
        (phase0_report_path, "phase0_verification_report"),
        (readiness_script_path, "production_readiness_audit"),
        (launch_script_path, "launch_prepare"),
        (contact_script_path, "apply_contact_channel"),
        (ads_txt_script_path, "apply_ads_txt"),
        (ga4_script_path, "apply_ga4_measurement"),
        (seo_audit_script_path, "seo_adsense_audit"),
        (performance_audit_script_path, "performance_budget_audit"),
    ]:
        if not path.exists():
            errors.append({"type": f"missing_{label}", "file": str(path.relative_to(ROOT))})
    if package_path.exists():
        package_data = load_json(package_path)
        scripts = package_data.get("scripts", {})
        for script in ("generate", "validate", "check"):
            if script not in scripts:
                errors.append({"type": "missing_package_script", "script": script})
        for script in ("adsense:apply", "analytics:apply", "audit:performance", "audit:seo", "contact:apply", "check:production", "launch:prepare", "ready", "ready:production", "gsc:check", "gsc:submit"):
            if script not in scripts:
                errors.append({"type": "missing_operations_package_script", "script": script})
    if vercel_path.exists():
        vercel_data = load_json(vercel_path)
        if not any(header.get("source") == "/(sitemap|feed|opensearch)\\.xml" for header in vercel_data.get("headers", [])):
            errors.append({"type": "vercel_missing_xml_headers"})
        if not any(header.get("source") == "/(robots|llms|ads)\\.txt" for header in vercel_data.get("headers", [])):
            errors.append({"type": "vercel_missing_text_headers"})
    if quality_workflow_path.exists():
        workflow = quality_workflow_path.read_text(encoding="utf-8")
        if "generate_aca_articles.py" not in workflow or "validate_content_quality.py" not in workflow:
            errors.append({"type": "content_quality_workflow_missing_commands"})
        if "audit_seo_adsense.py" not in workflow:
            errors.append({"type": "content_quality_workflow_missing_seo_adsense_audit"})
        if "audit_performance_budget.py" not in workflow:
            errors.append({"type": "content_quality_workflow_missing_performance_audit"})
    if seo_audit_report_path.exists():
        seo_audit_report = load_json(seo_audit_report_path)
        if seo_audit_report.get("error_count") != 0 or not seo_audit_report.get("passed"):
            errors.append({"type": "seo_adsense_audit_report_failed"})
    if performance_audit_report_path.exists():
        performance_audit_report = load_json(performance_audit_report_path)
        if performance_audit_report.get("error_count") != 0 or not performance_audit_report.get("passed"):
            errors.append({"type": "performance_audit_report_failed"})
    if gsc_workflow_path.exists():
        workflow = gsc_workflow_path.read_text(encoding="utf-8")
        for needle, label in [
            ("push:", "push_trigger"),
            ("workflow_dispatch:", "manual_trigger"),
            ("GSC_SITE_URL", "site_url_var"),
            ("GSC_SITEMAP_URL", "sitemap_url_var"),
            ("GSC_CLIENT_JSON", "client_secret"),
            ("GSC_TOKEN_JSON", "token_secret"),
            ("--check-config", "config_check"),
            ("scripts/gsc_submit_sitemap.py", "submit_script"),
        ]:
            if needle not in workflow:
                errors.append({"type": f"gsc_workflow_missing_{label}"})
    if phase0_report_path.exists():
        phase0_report = phase0_report_path.read_text(encoding="utf-8")
        for needle, label in [
            ("G0-1 County And Rating Area Scope", "county_rating_area"),
            ("G0-2 SLCSP Calculation Scope", "slcsp_scope"),
            ("G0-3 Subsidy Regime Status", "subsidy_regime"),
            ("G0-4 Florida Coverage Gap Handling", "coverage_gap"),
            ("Production domain is not assigned", "domain_blocker"),
            ("PUBLIC_CONTACT_EMAIL", "public_contact_email"),
            ("npm run contact:apply", "contact_apply_gate"),
            ("GA4_MEASUREMENT_ID", "ga4_measurement_id"),
            ("npm run analytics:apply", "analytics_apply_gate"),
            ("ADSENSE_PUBLISHER_ID", "adsense_publisher_id"),
            ("npm run adsense:apply", "adsense_apply_gate"),
            ("npm run check:production", "production_gate"),
            ("npm run launch:prepare", "launch_prepare_gate"),
            ("npm run gsc:submit", "gsc_submit_gate"),
            ("npm run ready:production", "readiness_gate"),
        ]:
            if needle not in phase0_report:
                errors.append({"type": f"phase0_report_missing_{label}"})

    queue_path = CONTENT_DIR / "article-queue.json"
    q = load_json(queue_path)
    site_origin = origin_from_canonical(q[0].get("canonical", "")) if q else "{SITE_ORIGIN}"
    expected_org_id = f"{site_origin}/#organization"
    expected_website_id = f"{site_origin}/#website"
    if require_site_origin and (site_origin == "{SITE_ORIGIN}" or not site_origin.startswith("https://")):
        errors.append({"type": "production_site_origin_not_set", "site_origin": site_origin})
    by_slug = {item["slug"]: item for item in q}
    published_items = [item for item in q if item.get("is_published")]
    scheduled_items = [item for item in q if not item.get("is_published")]
    article_files = sorted(ARTICLE_DIR.glob("*.html"))
    all_html_files = sorted(ROOT.glob("*.html")) + article_files + sorted(GUIDE_DIR.glob("*.html"))
    errors.extend(validate_html_structure(all_html_files))

    for field in ("title", "slug", "main_keyword", "meta_title", "meta_description"):
        values = [item[field] for item in q]
        if len(values) != len(set(values)):
            errors.append({"type": f"duplicate_{field}"})

    weak_title_pattern = re.compile(r"\ba Orlando\b|\ba [AEIOUaeiou]|changes changes|\bflorida\b|\bfpl\b|\baca\b")
    weak_meta_ending_pattern = re.compile(r"\b(and|or|with|for|to|of|in|at|by|from|before|after|when|while|plus)\.$", re.IGNORECASE)
    weak_meta_title_ending_pattern = re.compile(
        r"(\.$|\b(a|an|the|and|or|with|for|to|of|in|at|by|from|before|after|when|while|plus|near|around|inside|without|read|can)$)",
        re.IGNORECASE,
    )
    for item in q:
        if len(item["meta_title"]) > 58:
            errors.append({"type": "meta_title_too_long", "slug": item["slug"], "length": len(item["meta_title"])})
        if len(item["meta_title"]) < 30:
            errors.append({"type": "meta_title_too_short", "slug": item["slug"], "length": len(item["meta_title"]), "meta_title": item["meta_title"]})
        if len(item["meta_description"]) > 155:
            errors.append({"type": "meta_description_too_long", "slug": item["slug"], "length": len(item["meta_description"])})
        if item["title"] and item["title"][0].islower():
            errors.append({"type": "title_starts_lowercase", "slug": item["slug"]})
        if weak_title_pattern.search(item["title"]):
            errors.append({"type": "weak_title_pattern", "slug": item["slug"], "title": item["title"]})
        if item["title"].lower().count("before choosing") > 1:
            errors.append({"type": "repeated_title_phrase", "slug": item["slug"], "title": item["title"]})
        if weak_meta_title_ending_pattern.search(item["meta_title"]):
            errors.append({"type": "weak_meta_title_ending", "slug": item["slug"], "meta_title": item["meta_title"]})
        if re.search(r"\d+\s+%", item["meta_title"]):
            errors.append({"type": "meta_title_bad_percent_spacing", "slug": item["slug"], "meta_title": item["meta_title"]})
        if weak_meta_ending_pattern.search(item["meta_description"]):
            errors.append({"type": "weak_meta_description_ending", "slug": item["slug"], "meta_description": item["meta_description"]})
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["slug"]):
            errors.append({"type": "non_readable_slug", "slug": item["slug"]})
        if len(item["slug"]) > 120:
            errors.append({"type": "slug_too_long", "slug": item["slug"], "length": len(item["slug"])})

    for i in range(1, len(q)):
        prev = datetime.fromisoformat(q[i - 1]["publishAt"])
        cur = datetime.fromisoformat(q[i]["publishAt"])
        if (cur - prev).total_seconds() != 18000:
            errors.append({"type": "bad_publish_interval", "index": i})

    valid_files = {f"{item['slug']}.html" for item in q}
    extras = sorted(p.name for p in article_files if p.name not in valid_files)
    missing = sorted(name for name in valid_files if not (ARTICLE_DIR / name).exists())
    for name in extras:
        errors.append({"type": "extra_article_file", "file": name})
    for name in missing:
        errors.append({"type": "missing_article_file", "file": name})

    word_counts = []
    repeated_sentences = Counter()
    hub_words = []
    nonhub_words = []
    schema_counts = {}
    visible_guide_links = 0
    article_feed_alt_missing = 0
    article_trust_missing = 0
    article_cta_missing = 0
    article_internal_link_short = 0
    article_external_link_missing = 0

    for i, item in enumerate(q):
        path = ARTICLE_DIR / f"{item['slug']}.html"
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        wc = words_from_html(html)
        word_counts.append(wc)
        repeated_sentences.update(body_sentences_from_html(html))
        if i in HUB_INDEXES:
            hub_words.append(wc)
            if "At-a-glance ACA estimate summary" not in html:
                errors.append({"type": "missing_hub_summary", "slug": item["slug"]})
        else:
            nonhub_words.append(wc)
        if wc < 1300:
            errors.append({"type": "short_article", "slug": item["slug"], "words": wc})
        for needle, label in [
            ('<meta name="description"', "meta_description"),
            ('<link rel="canonical"', "canonical"),
            ("Table of contents", "toc"),
            ("Verification snapshot", "verification_snapshot"),
            ("Reviewed by CoverClarity editorial desk", "reviewed_byline"),
            ("Related guide path", "related_path"),
            ("Editorial standards for this ACA estimate", "editorial_block"),
            ('class="source-list"', "source_list"),
            ('target="_blank"', "external_source"),
            ('<meta property="og:title"', "og_title"),
            ('<meta name="twitter:title"', "twitter_title"),
        ]:
            if needle not in html:
                errors.append({"type": f"missing_{label}", "slug": item["slug"]})
        if 'type="application/rss+xml"' not in html:
            article_feed_alt_missing += 1
        if item.get("is_published"):
            if '<meta name="robots" content="noindex,follow' in html:
                errors.append({"type": "published_article_noindexed", "slug": item["slug"]})
        elif '<meta name="robots" content="noindex,follow' not in html:
            errors.append({"type": "scheduled_article_indexable", "slug": item["slug"]})
        if "../editorial-policy.html" not in html or "../sources-corrections.html" not in html or "../contact.html" not in html:
            article_trust_missing += 1
        parser = parse_page(path)
        article_internal_links = [
            href for href in parser.links
            if not href.startswith(("http://", "https://", "mailto:", "tel:", "{SITE_ORIGIN}"))
        ]
        article_external_links = [
            href for href in parser.links
            if href.startswith(("http://", "https://"))
        ]
        if len(set(article_internal_links)) < 2:
            article_internal_link_short += 1
            errors.append({"type": "article_too_few_internal_links", "slug": item["slug"], "count": len(set(article_internal_links))})
        if not article_external_links:
            article_external_link_missing += 1
            errors.append({"type": "article_missing_external_link", "slug": item["slug"]})
        if 'class="cta"' not in html or "../index.html#calc" not in html:
            article_cta_missing += 1
            errors.append({"type": "article_missing_calculator_cta", "slug": item["slug"]})
        if item.get("category") in CLUSTER_ARTICLES and "../guides/" in html:
            visible_guide_links += 1
        if "Quality score" in html or "Score " in html:
            errors.append({"type": "article_internal_quality_score_visible", "slug": item["slug"]})
        schemas = schemas_from_html(html)
        article_schema = next((schema for schema in schemas if schema.get("@type") == "Article"), None)
        if not any(schema.get("@type") == "Organization" and schema.get("@id") == expected_org_id for schema in schemas):
            errors.append({"type": "article_missing_organization_schema", "slug": item["slug"]})
        if not any(schema.get("@type") == "WebSite" and schema.get("@id") == expected_website_id for schema in schemas):
            errors.append({"type": "article_missing_website_schema", "slug": item["slug"]})
        if not article_schema:
            errors.append({"type": "missing_article_schema", "slug": item["slug"]})
        else:
            for field in ("keywords", "articleSection", "citation", "isPartOf", "datePublished", "dateModified"):
                if not article_schema.get(field):
                    errors.append({"type": f"article_schema_missing_{field}", "slug": item["slug"]})
            if article_schema.get("publisher", {}).get("@id") != expected_org_id:
                errors.append({"type": "article_schema_publisher_not_entity_reference", "slug": item["slug"]})
            if article_schema.get("reviewedBy", {}).get("@id") != expected_org_id:
                errors.append({"type": "article_schema_reviewer_not_entity_reference", "slug": item["slug"]})
            if article_schema.get("isPartOf", {}).get("@id") != expected_website_id:
                errors.append({"type": "article_schema_website_not_entity_reference", "slug": item["slug"]})
            if "T" not in str(article_schema.get("datePublished", "")):
                errors.append({"type": "article_schema_date_not_iso_datetime", "slug": item["slug"]})
            if not isinstance(article_schema.get("keywords"), list) or len(article_schema.get("keywords", [])) < 3:
                errors.append({"type": "article_schema_keywords_weak", "slug": item["slug"]})
            if not isinstance(article_schema.get("citation"), list) or len(article_schema.get("citation", [])) < 2:
                errors.append({"type": "article_schema_citation_weak", "slug": item["slug"]})
        for typ in [schema.get("@type") for schema in schemas]:
            schema_counts[typ] = schema_counts.get(typ, 0) + 1
        if BAD_PATTERNS.search(html):
            errors.append({"type": "bad_pattern_article", "slug": item["slug"]})

    overused_sentences = [
        {"count": count, "sentence": sentence[:160]}
        for sentence, count in repeated_sentences.items()
        if count > 80
    ]
    for item in overused_sentences[:20]:
        errors.append({"type": "overused_article_sentence", **item})

    guide_files = sorted(GUIDE_DIR.glob("*.html"))
    guide_counts = {}
    for p in guide_files:
        html = p.read_text(encoding="utf-8")
        guide_counts[p.name] = len(set(re.findall(r'href="\.\./aca/([^"]+\.html)"', html)))
        for needle, label in [
            ('<link rel="canonical"', "canonical"),
            ('type="application/rss+xml"', "feed_alt"),
            ('"@type":"CollectionPage"', "collection_schema"),
            ('"@type":"ItemList"', "itemlist_schema"),
            ('"@type":"BreadcrumbList"', "breadcrumb_schema"),
            ('"@type":"Organization"', "organization_schema"),
            ('"@type":"WebSite"', "website_schema"),
            ("editorial-policy.html", "editorial_link"),
            ("sources-corrections.html", "sources_link"),
            ("contact.html", "contact_link"),
        ]:
            if needle not in html:
                errors.append({"type": f"guide_missing_{label}", "file": p.name})
        if BAD_PATTERNS.search(html):
            errors.append({"type": "bad_pattern_guide", "file": p.name})
        if "Quality score" in html or "Score " in html:
            errors.append({"type": "guide_internal_quality_score_visible", "file": p.name})

    feed_root = ET.parse(ROOT / "feed.xml").getroot()
    feed_nodes = feed_root.findall("./channel/item")
    feed_items = len(feed_nodes)
    feed_links = {node.findtext("link", default="") for node in feed_nodes}
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    opensearch_path = ROOT / "opensearch.xml"
    if not opensearch_path.exists():
        errors.append({"type": "missing_opensearch"})
        opensearch_xml = ""
    else:
        opensearch_xml = opensearch_path.read_text(encoding="utf-8")
        try:
            opensearch_root = ET.parse(opensearch_path).getroot()
            if not opensearch_root.tag.endswith("OpenSearchDescription"):
                errors.append({"type": "opensearch_bad_root"})
        except ET.ParseError as exc:
            errors.append({"type": "opensearch_parse_error", "message": str(exc)})
        if f"{site_origin}/blog.html?q={{searchTerms}}" not in opensearch_xml:
            errors.append({"type": "opensearch_bad_search_template"})
    search_index = load_json(CONTENT_DIR / "search-index.json")
    documents = search_index["documents"]
    article_documents = [doc for doc in documents if doc.get("type") == "article"]
    legacy_article_urls = {"aca-enhanced-subsidies-2026-florida.html"}
    legacy_article_count = sum(1 for doc in article_documents if doc.get("url") in legacy_article_urls)
    indexed_article_urls = {doc.get("url") for doc in article_documents}
    document_urls = {doc.get("url") for doc in documents}
    if "contact.html" not in document_urls:
        errors.append({"type": "search_index_missing_contact"})
    if "privacy.html" not in document_urls:
        errors.append({"type": "search_index_missing_privacy"})
    if "/privacy.html" not in llms:
        errors.append({"type": "llms_missing_privacy"})
    if feed_items != len(published_items):
        errors.append({"type": "feed_published_count_mismatch", "feed_items": feed_items, "published_items": len(published_items)})
    if len(article_documents) != len(published_items) + legacy_article_count:
        errors.append({"type": "search_index_published_count_mismatch", "search_index_articles": len(article_documents), "published_items": len(published_items), "legacy_article_count": legacy_article_count})
    if "aca-enhanced-subsidies-2026-florida.html" not in indexed_article_urls:
        errors.append({"type": "legacy_article_missing_search_index"})
    for item in published_items:
        article_url = f"{site_origin}/aca/{item['slug']}.html"
        relative_url = f"aca/{item['slug']}.html"
        if article_url not in sitemap:
            errors.append({"type": "published_article_missing_sitemap", "slug": item["slug"]})
        if article_url not in feed_links:
            errors.append({"type": "published_article_missing_feed", "slug": item["slug"]})
        if relative_url not in indexed_article_urls:
            errors.append({"type": "published_article_missing_search_index", "slug": item["slug"]})
    for item in scheduled_items:
        article_url = f"{site_origin}/aca/{item['slug']}.html"
        relative_url = f"aca/{item['slug']}.html"
        if article_url in sitemap:
            errors.append({"type": "scheduled_article_in_sitemap", "slug": item["slug"]})
        if article_url in feed_links:
            errors.append({"type": "scheduled_article_in_feed", "slug": item["slug"]})
        if relative_url in indexed_article_urls:
            errors.append({"type": "scheduled_article_in_search_index", "slug": item["slug"]})
    blog_html = (ROOT / "blog.html").read_text(encoding="utf-8")
    blog_size_bytes = (ROOT / "blog.html").stat().st_size
    blog_schema_posts = blog_html.count('"@type":"BlogPosting"')
    html_with_skip_links = sum(1 for path in all_html_files if 'class="skip-link"' in path.read_text(encoding="utf-8"))
    html_with_focus_visible = sum(1 for path in all_html_files if ":focus-visible" in path.read_text(encoding="utf-8"))
    html_with_search_discovery = sum(
        1
        for path in all_html_files
        if 'rel="search"' in path.read_text(encoding="utf-8")
        and "application/opensearchdescription+xml" in path.read_text(encoding="utf-8")
    )
    if html_with_skip_links != len(all_html_files):
        errors.append({"type": "too_few_skip_links", "count": html_with_skip_links})
    if html_with_focus_visible != len(all_html_files):
        errors.append({"type": "too_few_focus_visible_styles", "count": html_with_focus_visible})
    if html_with_search_discovery != len(all_html_files):
        errors.append({"type": "too_few_search_discovery_links", "count": html_with_search_discovery})
    if blog_size_bytes > 350_000:
        errors.append({"type": "blog_html_too_large", "bytes": blog_size_bytes})
    if blog_schema_posts > 50:
        errors.append({"type": "blog_schema_too_many_posts", "count": blog_schema_posts})
    if "Score " in blog_html or "quality_score" in blog_html:
        errors.append({"type": "blog_internal_quality_score_visible"})
    blog_schemas = schemas_from_html(blog_html)
    if not any(schema.get("@type") == "Organization" and schema.get("@id") == expected_org_id for schema in blog_schemas):
        errors.append({"type": "blog_missing_organization_schema"})
    website_schema = next((schema for schema in blog_schemas if schema.get("@type") == "WebSite"), None)
    if not website_schema or website_schema.get("potentialAction", {}).get("@type") != "SearchAction":
        errors.append({"type": "blog_missing_searchaction_schema"})

    public_artifacts = [
        path
        for path in [
            ROOT / "feed.xml",
            ROOT / "llms.txt",
            ROOT / "sitemap.xml",
            ROOT / "robots.txt",
            opensearch_path,
            CONTENT_DIR / "search-index.json",
            CONTENT_DIR / "article-queue.json",
        ]
        if path.exists()
    ] + all_html_files
    public_internal_pattern = re.compile(r"pSEO|quality_score|codex_only_generation|manual_ad_slots|Search intent map", re.IGNORECASE)
    for path in public_artifacts:
        public_text = path.read_text(encoding="utf-8")
        if public_internal_pattern.search(public_text):
            errors.append({"type": "public_internal_marker_visible", "file": str(path.relative_to(ROOT))})
        if require_site_origin and "{SITE_ORIGIN}" in public_text:
            errors.append({"type": "production_placeholder_visible", "file": str(path.relative_to(ROOT))})

    for file_name in [
        "index.html",
        "blog.html",
        "methodology.html",
        "about.html",
        "contact.html",
        "privacy.html",
        "editorial-policy.html",
        "sources-corrections.html",
        "aca-enhanced-subsidies-2026-florida.html",
    ]:
        html = (ROOT / file_name).read_text(encoding="utf-8")
        if '<meta name="description"' not in html or '<link rel="canonical"' not in html:
            errors.append({"type": "static_meta_missing", "file": file_name})
        for needle, label in [
            ('type="application/rss+xml"', "feed_alt"),
            ('<meta property="og:title"', "og_title"),
            ('<meta name="twitter:title"', "twitter_title"),
            ('<script type="application/ld+json"', "schema"),
        ]:
            if needle not in html:
                errors.append({"type": f"static_missing_{label}", "file": file_name})
        if BAD_PATTERNS.search(html):
            errors.append({"type": "bad_pattern_static", "file": file_name})
        if file_name in {"about.html", "privacy.html", "editorial-policy.html", "sources-corrections.html"} and "contact.html" not in html:
            errors.append({"type": "static_missing_contact_link", "file": file_name})
        if file_name == "privacy.html":
            for needle, label in [
                ("Google AdSense", "adsense"),
                ("cookies", "cookies"),
                ("personalize ads", "personalized_ads"),
                ("browser", "browser_processing"),
                ("quote leads", "lead_sale"),
                ("policies.google.com", "google_policy_links"),
            ]:
                if needle not in html:
                    errors.append({"type": f"privacy_missing_{label}"})
        if file_name == "index.html":
            errors.extend(validate_home_calculator(html))
            schemas = schemas_from_html(html)
            if not any(schema.get("@type") == "Organization" and schema.get("@id") == expected_org_id for schema in schemas):
                errors.append({"type": "home_missing_organization_schema"})
            home_website = next((schema for schema in schemas if schema.get("@type") == "WebSite"), None)
            if not home_website or home_website.get("potentialAction", {}).get("@type") != "SearchAction":
                errors.append({"type": "home_missing_searchaction_schema"})
            home_app = next((schema for schema in schemas if schema.get("@type") == "WebApplication"), None)
            if not home_app or home_app.get("publisher", {}).get("@id") != expected_org_id:
                errors.append({"type": "home_app_missing_entity_publisher"})

    not_found_html = (ROOT / "404.html").read_text(encoding="utf-8")
    for needle, label in [
        ('<meta name="robots" content="noindex,follow"', "noindex_follow"),
        ('href="index.html#calc"', "calculator_link"),
        ('href="blog.html"', "blog_link"),
        ('href="guides/county-and-rating-area-guides.html"', "guide_link"),
        ('<script type="application/ld+json"', "schema"),
    ]:
        if needle not in not_found_html:
            errors.append({"type": f"not_found_missing_{label}"})
    if f"{site_origin}/404.html" in sitemap:
        errors.append({"type": "not_found_in_sitemap"})
    if f"{site_origin}/opensearch.xml" in sitemap:
        errors.append({"type": "opensearch_in_sitemap"})
    if f"{site_origin}/contact.html" not in sitemap:
        errors.append({"type": "contact_missing_from_sitemap"})
    if f"{site_origin}/aca-enhanced-subsidies-2026-florida.html" not in sitemap:
        errors.append({"type": "legacy_article_missing_sitemap"})

    summary = {
        "queue_count": len(q),
        "site_origin": site_origin,
        "production_site_origin_required": require_site_origin,
        "package_json_present": package_path.exists(),
        "vercel_json_present": vercel_path.exists(),
        "content_quality_workflow_present": quality_workflow_path.exists(),
        "readme_present": readme_path.exists(),
        "article_files": len(article_files),
        "published_article_files": len(published_items),
        "scheduled_article_files": len(scheduled_items),
        "guide_files": len(guide_files),
        "feed_items": feed_items,
        "sitemap_urls": sitemap.count("<url>"),
        "sitemap_article_urls": len(re.findall(r"/aca/[^<]+\.html", sitemap)),
        "sitemap_guide_urls": len(re.findall(r"/guides/[^<]+\.html", sitemap)),
        "search_index_documents": len(documents),
        "search_index_articles": sum(1 for d in documents if d["type"] == "article"),
        "search_index_guides": sum(1 for d in documents if d["type"] == "guide_hub"),
        "search_index_trust_pages": sum(1 for d in documents if d["type"] == "trust_page"),
        "blog_size_bytes": blog_size_bytes,
        "blog_schema_posts": blog_schema_posts,
        "html_files_checked": len(all_html_files),
        "html_with_skip_links": html_with_skip_links,
        "html_with_focus_visible": html_with_focus_visible,
        "html_with_search_discovery": html_with_search_discovery,
        "opensearch_present": opensearch_path.exists(),
        "llms_has_sitemap": "/sitemap.xml" in llms,
        "llms_has_feed": "/feed.xml" in llms,
        "llms_has_search_index": "/content/search-index.json" in llms,
        "visible_guide_links": visible_guide_links,
        "article_feed_alt_missing": article_feed_alt_missing,
        "article_trust_missing": article_trust_missing,
        "article_cta_missing": article_cta_missing,
        "article_internal_link_short": article_internal_link_short,
        "article_external_link_missing": article_external_link_missing,
        "overused_sentence_count": len(overused_sentences),
        "schema_counts": schema_counts,
        "guide_counts": guide_counts,
        "word_count_min_avg_max": [min(word_counts), round(statistics.mean(word_counts)), max(word_counts)],
        "hub_word_min_avg_max": [min(hub_words), round(statistics.mean(hub_words)), max(hub_words)],
        "nonhub_word_min_avg_max": [min(nonhub_words), round(statistics.mean(nonhub_words)), max(nonhub_words)],
        "first_publish_at": q[0]["publishAt"],
        "last_publish_at": q[-1]["publishAt"],
        "errors": errors,
        "error_count": len(errors),
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--require-site-origin", action="store_true")
    args = parser.parse_args()
    summary = validate(require_site_origin=args.require_site_origin)
    if args.write_report:
        REPORT_DIR.mkdir(exist_ok=True)
        (REPORT_DIR / "content-quality-report.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
