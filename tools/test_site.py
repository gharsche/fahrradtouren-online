#!/usr/bin/env python3
"""Smoke-test generated routes, assets, and source-key redaction."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE = "/fahrradtouren-online"


class TextExtractor(HTMLParser):
    def __init__(self, content_only=False):
        super().__init__(convert_charrefs=True)
        self.content_only = content_only
        self.started = not content_only
        self.depth = 0
        self.blocked = False
        self.parts = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "style"}:
            self.blocked = True
            return
        if self.content_only and not self.started and tag == "div" and "content-body" in (values.get("class") or "").split():
            self.started = True
            self.depth = 1
            return
        if self.content_only and self.started:
            if tag not in {"img", "br", "hr", "source"}:
                self.depth += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.blocked = False
            return
        if self.content_only and self.started and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.started = False
    def handle_data(self, data):
        if not self.blocked and (self.started or not self.content_only):
            self.parts.append(data)
    def text(self):
        return " ".join(" ".join(self.parts).split())


class RefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("href", "src", "poster"):
            if values.get(key):
                self.refs.append(values[key])


class NavParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_desktop_nav = False
        self.group = None
        self.capture = None
        self.groups = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "nav" and "desktop-nav" in classes:
            self.in_desktop_nav = True
        elif self.in_desktop_nav and tag == "details":
            self.group = {"label": "", "links": []}
            self.groups.append(self.group)
        elif self.group is not None and tag == "summary":
            self.capture = "label"
        elif self.group is not None and tag == "a":
            self.group["links"].append("")
            self.capture = "link"
    def handle_endtag(self, tag):
        if tag in {"summary", "a"}:
            self.capture = None
        elif tag == "details":
            self.group = None
        elif tag == "nav":
            self.in_desktop_nav = False
    def handle_data(self, data):
        if self.group is None or self.capture is None:
            return
        if self.capture == "label":
            self.group["label"] += data
        else:
            self.group["links"][-1] += data


def file_for_url(value: str) -> Path | None:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if path == BASE:
        path = "/"
    elif path.startswith(BASE + "/"):
        path = path[len(BASE):]
    else:
        return None
    if path.endswith("/") or not Path(path).suffix:
        return DOCS / path.strip("/") / "index.html" if path.strip("/") else DOCS / "index.html"
    return DOCS / path.lstrip("/")


def main():
    data = json.loads((ROOT / "content" / "wordpress-export.json").read_text(encoding="utf-8"))
    expected = {x["path"] for x in data["pages"] + data["posts"]}
    missing_routes = [p for p in sorted(expected) if not (DOCS / p.strip("/") / "index.html").is_file()]
    missing_content = []
    for record in data["pages"] + data["posts"]:
        source_parser = TextExtractor()
        source_parser.feed(record.get("content_html", ""))
        source_text = source_parser.text()
        output_path = DOCS / record["path"].strip("/") / "index.html"
        rendered_parser = TextExtractor(content_only=True)
        rendered_parser.feed(output_path.read_text(encoding="utf-8"))
        rendered_text = rendered_parser.text().replace("Kartenmodul der Originalseite hier wieder einbinden", "").replace("Bild der Originalseite ist nicht verfügbar", "")
        rendered_text = " ".join(rendered_text.split())
        if source_text and source_text not in rendered_text:
            missing_content.append({"path": record["path"], "source_sample": source_text[:100], "rendered_sample": rendered_text[:100]})
    html_files = list(DOCS.rglob("*.html"))
    missing_local = []
    duplicate_menu_entries = []
    for page in html_files:
        parser = RefParser()
        parser.feed(page.read_text(encoding="utf-8"))
        nav_parser = NavParser()
        nav_parser.feed(page.read_text(encoding="utf-8"))
        for group in nav_parser.groups:
            if group["label"].strip() in {link.strip() for link in group["links"]}:
                duplicate_menu_entries.append({"page": page.relative_to(DOCS).as_posix(), "label": group["label"].strip()})
        for ref in parser.refs:
            local = file_for_url(ref)
            if local and not local.is_file():
                missing_local.append((page.relative_to(DOCS).as_posix(), ref))
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in html_files)
    home_html = (DOCS / "index.html").read_text(encoding="utf-8")
    original_image_url = "https://harsche.com/wp-content/uploads/2023/01/cropped-iStock-1353080098-e1672999846998-1-e1673000401406.jpg"
    original_image_path = data["media"].get(original_image_url, "")
    expected_home_image = BASE + "/" + original_image_path.lstrip("/") if original_image_path else ""
    search_data = json.loads((DOCS / "assets" / "search-index.json").read_text(encoding="utf-8"))
    carbon_page = (DOCS / "aufruestung-des-rose-backroad-mit-carbonfelgen" / "index.html").read_text(encoding="utf-8")
    privacy_page = (DOCS / "datenschutzerklaerung" / "index.html").read_text(encoding="utf-8")
    strava_map_tags = re.findall(r'<img\b(?=[^>]*class="strava-map")[^>]*>', home_html)
    html_without_strava_map_tags = re.sub(r'<img\b(?=[^>]*class="strava-map")[^>]*>', "", text)
    results = {
        "source_pages": len(data["pages"]),
        "source_posts": len(data["posts"]),
        "source_urls_generated": len(expected),
        "html_files": len(html_files),
        "search_records": len(search_data),
        "category_archives": sum(1 for c in data["categories"] if (DOCS / "category" / c["slug"] / "index.html").is_file()),
        "missing_source_routes": missing_routes,
        "content_text_missing": missing_content[:10],
        "content_text_missing_count": len(missing_content),
        "missing_local_references": missing_local[:25],
        "missing_local_reference_count": len(missing_local),
        "duplicate_menu_entries": duplicate_menu_entries[:25],
        "duplicate_menu_entry_count": len(duplicate_menu_entries),
        "google_key_marker_outside_strava_map_html": "AIza" in html_without_strava_map_tags,
        "strava_logo_present": 'class="strava-brand"' in home_html and 'strava-powered-by-orange.svg' in home_html and (DOCS / "assets" / "strava-powered-by-orange.svg").is_file() and "#FC5200" in (DOCS / "assets" / "strava-powered-by-orange.svg").read_text(encoding="utf-8"),
        "strava_map_image_present": bool(strava_map_tags and "maps.googleapis.com/maps/api/staticmap?" in strava_map_tags[0] and "AIza" in strava_map_tags[0]),
        "privacy_discloses_google_map": "Google Maps Static API" in privacy_page and "maps.googleapis.com" in privacy_page,
        "hero_image_exists": (DOCS / "assets" / "bergstrasse-cycling.png").is_file(),
        "homepage_original_image_used": bool(expected_home_image and expected_home_image in home_html),
        "carbon_tile_uses_full_artwork_layout": '<section class="hero artwork-hero">' in carbon_page and 'class="visually-hidden">Aufrüstung des Rose Backroad mit Carbonfelgen</h1>' in carbon_page,
        "hero_headings_keep_words_intact": ".hero-copy h1{font-size:clamp(32px,4.2vw,56px);overflow-wrap:normal;word-break:normal;hyphens:none}" in (DOCS / "assets" / "site.css").read_text(encoding="utf-8"),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if missing_routes or missing_content or missing_local or duplicate_menu_entries or results["google_key_marker_outside_strava_map_html"] or not results["strava_logo_present"] or not results["strava_map_image_present"] or not results["privacy_discloses_google_map"] or not results["hero_image_exists"] or not results["homepage_original_image_used"] or not results["carbon_tile_uses_full_artwork_layout"] or not results["hero_headings_keep_words_intact"] or len(search_data) != len(expected):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
