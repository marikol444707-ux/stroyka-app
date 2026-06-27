#!/usr/bin/env python3
import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BUILD = ROOT / "build"

REQUIRED_PAGES = [
    "index.html",
    "features.html",
    "project-catalog.html",
    "contacts.html",
    "privacy.html",
    "terms.html",
    "llms.txt",
    "robots.txt",
    "sitemap.xml",
    "manifest.json",
]

PUBLIC_URLS = [
    "https://stroyka26.pro/",
    "https://stroyka26.pro/features.html",
    "https://stroyka26.pro/project-catalog.html",
    "https://stroyka26.pro/contacts.html",
    "https://stroyka26.pro/privacy.html",
    "https://stroyka26.pro/terms.html",
]


class PublicSiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.catalog_cards = 0
        self.catalog_items = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag == "article" and "catalog-card" in attrs.get("class", ""):
            self.catalog_cards += 1
        if tag == "li":
            self.catalog_items += 1
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])


def fail(message):
    print(f"FAIL {message}", file=sys.stderr)
    sys.exit(1)


def read(path):
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    data = path.read_text(encoding="utf-8")
    if not data.strip():
        fail(f"empty file: {path.relative_to(ROOT)}")
    return data


def quoted_strings(value):
    return re.findall(r"'([^']+)'", value or "")


def check_public_files():
    for name in REQUIRED_PAGES:
        read(PUBLIC / name)

    manifest = json.loads(read(PUBLIC / "manifest.json"))
    if "строительство" not in json.dumps(manifest, ensure_ascii=False).lower():
        fail("manifest description does not mention public construction positioning")


def check_sitemap_robots_llms():
    sitemap = read(PUBLIC / "sitemap.xml")
    robots = read(PUBLIC / "robots.txt")
    llms = read(PUBLIC / "llms.txt")

    for url in PUBLIC_URLS:
        if url not in sitemap:
            fail(f"sitemap missing {url}")

    for page in ["features.html", "project-catalog.html", "contacts.html", "privacy.html", "terms.html"]:
        if f"Allow: /{page}" not in robots:
            fail(f"robots missing Allow for /{page}")
        if page not in llms:
            fail(f"llms.txt missing {page}")

    if "45 стартовыми карточками" not in llms and "45 стартовых карточек" not in llms:
        fail("llms.txt missing project catalog scale")


def check_catalog_assets():
    catalog = read(PUBLIC / "project-catalog.html")
    parser = PublicSiteParser()
    parser.feed(catalog)

    if parser.catalog_cards != 15:
        fail(f"project catalog should have 15 direction cards, got {parser.catalog_cards}")
    if parser.catalog_items != 45:
        fail(f"project catalog should have 45 project items, got {parser.catalog_items}")
    if len(parser.images) < 30:
        fail(f"project catalog should expose facade and plan previews, got {len(parser.images)} images")

    for src in parser.images:
        if src.startswith("http"):
            continue
        asset = PUBLIC / src.lstrip("/")
        if not asset.exists():
            fail(f"catalog image missing: {src}")

    if "/#request" not in parser.links:
        fail("project catalog missing request CTA")


def check_catalog_matches_react_source():
    source = read(ROOT / "src" / "components" / "PublicSitePage.jsx")
    catalog = read(PUBLIC / "project-catalog.html")

    cards_match = re.search(
        r"const readyProjectCardsByDirection = \{(?P<body>.*?)\n\};\n\nconst makeProjectMedia",
        source,
        re.S,
    )
    if not cards_match:
        fail("cannot find readyProjectCardsByDirection in PublicSitePage.jsx")

    react_projects = {
        (code, title)
        for code, title in re.findall(
            r"code:\s*'([^']+)'\s*,\s*title:\s*'([^']+)'",
            cards_match.group("body"),
            re.S,
        )
    }
    if len(react_projects) != 45:
        fail(f"React project catalog should expose 45 projects, got {len(react_projects)}")

    html_projects = {
        (code, unescape(title).strip())
        for code, title in re.findall(
            r"<li>\s*([A-Z0-9-]+)\s+—\s+([^<]+)</li>",
            catalog,
        )
    }
    if react_projects != html_projects:
        missing = sorted(react_projects - html_projects)
        extra = sorted(html_projects - react_projects)
        fail(f"static catalog differs from React catalog; missing={missing[:5]} extra={extra[:5]}")

    directions_match = re.search(
        r"const referenceDirections = \[(?P<body>.*?)\n\];\n\nconst readyProjectCardsByDirection",
        source,
        re.S,
    )
    if not directions_match:
        fail("cannot find referenceDirections in PublicSitePage.jsx")

    react_directions = [
        title
        for title in re.findall(r"title:\s*'([^']+)'", directions_match.group("body"))
    ]
    html_directions = [
        unescape(title).strip()
        for title in re.findall(
            r'<article class="card catalog-card">.*?<h2>(.*?)</h2>',
            catalog,
            re.S,
        )
    ]
    if react_directions != html_directions:
        fail("static catalog direction order differs from React referenceDirections")


def check_react_project_media_assets():
    source = read(ROOT / "src" / "components" / "PublicSitePage.jsx")

    cards_match = re.search(
        r"const readyProjectCardsByDirection = \{(?P<body>.*?)\n\};\n\nconst makeProjectMedia",
        source,
        re.S,
    )
    if not cards_match:
        fail("cannot find readyProjectCardsByDirection in PublicSitePage.jsx")

    project_codes = set(re.findall(r"code:\s*'([^']+)'", cards_match.group("body")))
    expected_slugs = {code.lower() for code in project_codes}
    media_by_slug = {slug: set() for slug in expected_slugs}

    for src in re.findall(r"src:\s*'(/site-assets/projects/[^']+)'", cards_match.group("body")):
        parts = Path(src).parts
        if len(parts) < 4:
            fail(f"unexpected project media path: {src}")
        slug = parts[-2]
        media_by_slug.setdefault(slug, set()).add(src)

    media_map_match = re.search(
        r"const readyProjectMediaByCode = \{(?P<body>.*?)\n\};\n\nconst getReferenceProjectCards",
        source,
        re.S,
    )
    if not media_map_match:
        fail("cannot find readyProjectMediaByCode in PublicSitePage.jsx")

    default_files = ["facade.svg", "side.svg", "plan.svg"]
    for match in re.finditer(
        r"makeProjectMediaMap\(\s*\[(?P<codes>.*?)\]\s*,\s*\[(?P<labels>.*?)\]\s*(?:,\s*\[(?P<files>.*?)\])?\s*,?\s*\)",
        media_map_match.group("body"),
        re.S,
    ):
        files = quoted_strings(match.group("files")) if match.group("files") else default_files
        for code in quoted_strings(match.group("codes")):
            slug = code.lower()
            for file_name in files:
                media_by_slug.setdefault(slug, set()).add(f"/site-assets/projects/{slug}/{file_name}")

    if set(media_by_slug) != expected_slugs:
        fail("project media slugs differ from React project codes")

    assets_root = PUBLIC / "site-assets" / "projects"
    asset_dirs = {path.name for path in assets_root.iterdir() if path.is_dir()}
    if asset_dirs != expected_slugs:
        missing = sorted(expected_slugs - asset_dirs)
        extra = sorted(asset_dirs - expected_slugs)
        fail(f"project asset directories differ from React project codes; missing={missing[:5]} extra={extra[:5]}")

    for slug, sources in sorted(media_by_slug.items()):
        if len(sources) < 3:
            fail(f"project {slug} should have at least 3 media files, got {len(sources)}")
        if not any(Path(src).name.startswith("plan") for src in sources):
            fail(f"project {slug} missing plan media")
        for src in sorted(sources):
            asset = PUBLIC / src.lstrip("/")
            if not asset.exists():
                fail(f"project media missing: {src}")
            if asset.stat().st_size < 100:
                fail(f"project media looks empty: {src}")


def check_index_jsonld():
    index = read(PUBLIC / "index.html")
    blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', index, re.S)
    if not blocks:
        fail("index.html missing JSON-LD")

    graph_types = []
    for block in blocks:
        payload = json.loads(block)
        graph_types.extend(item.get("@type") for item in payload.get("@graph", []))

    for expected in ["Organization", "WebSite", "LocalBusiness", "Service", "ItemList", "FAQPage"]:
        if expected not in graph_types:
            fail(f"JSON-LD missing {expected}")

    if "Каталог проектов" not in index:
        fail("index noscript/footer should link to project catalog")


def check_build_copy_if_present():
    if not BUILD.exists():
        return
    for name in ["project-catalog.html", "features.html", "contacts.html", "privacy.html", "terms.html"]:
        if not (BUILD / name).exists():
            fail(f"build missing copied public page: {name}")


def main():
    check_public_files()
    check_sitemap_robots_llms()
    check_catalog_assets()
    check_catalog_matches_react_source()
    check_react_project_media_assets()
    check_index_jsonld()
    check_build_copy_if_present()
    print("Public static site check OK")


if __name__ == "__main__":
    main()
