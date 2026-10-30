#!/usr/bin/env python3
"""Smoke-test generated routes, assets, and source-key redaction."""
from __future__ import annotations

import json
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
    for page in html_files:
        parser = RefParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for ref in parser.refs:
            local = file_for_url(ref)
            if local and not local.is_file():
                missing_local.append((page.relative_to(DOCS).as_posix(), ref))
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in html_files)
    search_data = json.loads((DOCS / "assets" / "search-index.json").read_text(encoding="utf-8"))
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
        "google_key_marker_in_html": "AIza" in text,
        "hero_image_exists": (DOCS / "assets" / "bergstrasse-cycling.png").is_file(),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if missing_routes or missing_content or missing_local or results["google_key_marker_in_html"] or not results["hero_image_exists"] or len(search_data) != len(expected):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
