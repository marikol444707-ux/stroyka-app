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
    "project-catalog.json",
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
    "https://stroyka26.pro/project-catalog.json",
    "https://stroyka26.pro/contacts.html",
    "https://stroyka26.pro/privacy.html",
    "https://stroyka26.pro/terms.html",
]

EXPECTED_PROJECT_STATUS = "Проект-идея / пример для расчета"


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


def parse_ready_project_details(source):
    cards_match = re.search(
        r"const readyProjectCardsByDirection = \{(?P<body>.*?)\n\};\n\nconst makeProjectMedia",
        source,
        re.S,
    )
    if not cards_match:
        fail("cannot find readyProjectCardsByDirection in PublicSitePage.jsx")

    rows = re.findall(
        r"code:\s*'([^']+)'\s*,\s*title:\s*'([^']+)'\s*,\s*area:\s*'([^']+)'\s*,\s*floors:\s*'([^']+)'\s*,\s*layout:\s*'([^']+)'\s*,\s*visuals:\s*'([^']+)'",
        cards_match.group("body"),
        re.S,
    )
    projects = {
        code: {
            "code": code,
            "title": title,
            "area": area,
            "floors": floors,
            "layout": layout,
            "visuals": visuals,
            "url": f"https://stroyka26.pro/?project={code}#projects",
        }
        for code, title, area, floors, layout, visuals in rows
    }
    if len(projects) != 45:
        fail(f"React project catalog should expose 45 projects, got {len(projects)}")
    return projects


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

    for page in ["features.html", "project-catalog.html", "project-catalog.json", "contacts.html", "privacy.html", "terms.html"]:
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
    catalog_lower = catalog.lower()
    if "проектные примеры" not in catalog_lower or "не договоры" not in catalog_lower:
        fail("project catalog should explain that cards are project examples, not documents")

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

    react_projects = parse_ready_project_details(source)

    html_project_matches = re.findall(
        r'<li>\s*<a href="/\?project=([A-Z0-9-]+)#projects">\s*<span>\s*<b>\1</b>\s*([^<]+)</span>\s*<small>([^<]+)</small>\s*<em>([^<]+)</em>\s*<strong>([^<]+)</strong>\s*</a>\s*</li>',
        catalog,
        re.S,
    )
    html_projects = {
        code: {
            "code": code,
            "title": unescape(title).strip(),
            "area": unescape(area_floor).split(" · ", 1)[0].strip(),
            "floors": unescape(area_floor).split(" · ", 1)[1].strip() if " · " in area_floor else "",
            "layout": unescape(layout).strip(),
            "visuals": unescape(visuals).strip(),
            "url": f"https://stroyka26.pro/?project={code}#projects",
        }
        for code, title, area_floor, layout, visuals in html_project_matches
    }
    if react_projects != html_projects:
        missing = sorted(set(react_projects) - set(html_projects))
        extra = sorted(set(html_projects) - set(react_projects))
        fail(f"static catalog differs from React catalog; missing={missing[:5]} extra={extra[:5]}")

    for code, project in sorted(react_projects.items()):
        if f'href="/?project={code}#projects"' not in catalog:
            fail(f"project catalog missing deep link for {code}")
        if html_projects.get(code) != project:
            fail(f"project catalog details differ for {code}")

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


def check_catalog_json_matches_react_source():
    source = read(ROOT / "src" / "components" / "PublicSitePage.jsx")
    catalog = read(PUBLIC / "project-catalog.html")
    catalog_json = json.loads(read(PUBLIC / "project-catalog.json"))

    if catalog_json.get("directionCount") != 15 or len(catalog_json.get("directions", [])) != 15:
        fail("project-catalog.json should expose 15 directions")
    if catalog_json.get("projectCount") != 45:
        fail("project-catalog.json should expose 45 projects")

    react_projects = parse_ready_project_details(source)
    json_projects = {
        project.get("code"): {
            "code": project.get("code", ""),
            "title": project.get("title", ""),
            "area": project.get("area", ""),
            "floors": project.get("floors", ""),
            "layout": project.get("layout", ""),
            "visuals": project.get("visuals", ""),
            "url": project.get("url", ""),
        }
        for direction in catalog_json.get("directions", [])
        for project in direction.get("projects", [])
    }
    if react_projects != json_projects:
        missing = sorted(set(react_projects) - set(json_projects))
        extra = sorted(set(json_projects) - set(react_projects))
        fail(f"project-catalog.json differs from React catalog; missing={missing[:5]} extra={extra[:5]}")

    for direction in catalog_json.get("directions", []):
        if len(direction.get("projects", [])) != 3:
            fail(f"project-catalog.json direction should have 3 projects: {direction.get('title')}")
        if len(direction.get("previewImages", [])) < 2:
            fail(f"project-catalog.json direction should expose preview images: {direction.get('title')}")
        for image in direction.get("previewImages", []):
            src = image.get("src", "")
            if not src:
                fail(f"project-catalog.json preview image missing src: {direction.get('title')}")
            asset = PUBLIC / src.lstrip("/")
            if not asset.exists():
                fail(f"project-catalog.json preview image missing: {src}")
        for project in direction.get("projects", []):
            code = project.get("code", "")
            if project.get("status") != EXPECTED_PROJECT_STATUS:
                fail(f"project-catalog.json project status mismatch for {code}")
            expected_url = f"https://stroyka26.pro/?project={code}#projects"
            if project.get("url") != expected_url:
                fail(f"project-catalog.json project url mismatch for {code}")
            media = project.get("media", [])
            if len(media) < 3:
                fail(f"project-catalog.json project should expose media: {code}")
            if not any(item.get("role") == "render" for item in media):
                fail(f"project-catalog.json project missing render media: {code}")
            if not any(item.get("role") == "plan" for item in media):
                fail(f"project-catalog.json project missing plan media: {code}")
            for item in media:
                src = item.get("src", "")
                if not src:
                    fail(f"project-catalog.json media missing src: {code}")
                asset = PUBLIC / src.lstrip("/")
                if not asset.exists():
                    fail(f"project-catalog.json media missing: {src}")

    jsonld_blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', catalog, re.S)
    item_list = None
    for block in jsonld_blocks:
        payload = json.loads(block)
        if payload.get("@type") == "ItemList":
            item_list = payload
            break
    if not item_list:
        fail("project-catalog.html missing ItemList JSON-LD")
    if item_list.get("numberOfItems") != 45:
        fail("project-catalog.html ItemList should expose 45 projects")
    item_list_description = item_list.get("description", "").lower()
    if "проектными примерами" not in item_list_description or "не опубликованными документами" not in item_list_description:
        fail("project-catalog.html ItemList should describe cards as examples, not published documents")

    json_urls = {
        project.get("url")
        for direction in catalog_json.get("directions", [])
        for project in direction.get("projects", [])
    }
    jsonld_urls = {item.get("url") for item in item_list.get("itemListElement", [])}
    if json_urls != jsonld_urls:
        fail("project-catalog.html ItemList URLs differ from project-catalog.json")

    jsonld_descriptions = {
        item.get("url"): item.get("description", "")
        for item in item_list.get("itemListElement", [])
    }
    jsonld_images = {
        item.get("url"): item.get("image", [])
        for item in item_list.get("itemListElement", [])
    }
    jsonld_properties = {
        item.get("url"): {
            prop.get("name"): prop.get("value")
            for prop in item.get("additionalProperty", [])
        }
        for item in item_list.get("itemListElement", [])
    }
    for project in json_projects.values():
        description = jsonld_descriptions.get(project["url"], "")
        if EXPECTED_PROJECT_STATUS not in description:
            fail(f"project-catalog.html ItemList missing status in description for {project['code']}")
        if jsonld_properties.get(project["url"], {}).get("Статус") != EXPECTED_PROJECT_STATUS:
            fail(f"project-catalog.html ItemList status property differs for {project['code']}")
        for field in ["area", "floors", "layout", "visuals"]:
            if project[field] not in description:
                fail(f"project-catalog.html ItemList missing {field} for {project['code']}")

    for direction in catalog_json.get("directions", []):
        for project in direction.get("projects", []):
            expected_images = [
                f"https://stroyka26.pro{item.get('src')}"
                for item in project.get("media", [])
            ]
            if jsonld_images.get(project.get("url")) != expected_images:
                fail(f"project-catalog.html ItemList images differ for {project.get('code')}")


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
    for name in ["project-catalog.html", "project-catalog.json", "features.html", "contacts.html", "privacy.html", "terms.html"]:
        if not (BUILD / name).exists():
            fail(f"build missing copied public page: {name}")


def main():
    check_public_files()
    check_sitemap_robots_llms()
    check_catalog_assets()
    check_catalog_matches_react_source()
    check_catalog_json_matches_react_source()
    check_react_project_media_assets()
    check_index_jsonld()
    check_build_copy_if_present()
    print("Public static site check OK")


if __name__ == "__main__":
    main()
