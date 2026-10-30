#!/usr/bin/env python3
"""Export published content and referenced images from the public WordPress API."""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://harsche.com/wp-json/wp/v2/"
EXTRA_IMAGES = [
    "https://harsche.com/wp-content/uploads/2026/03/81Yuisb-K-L._SL1500_-1024x1024.jpg",
    "https://harsche.com/wp-content/uploads/2026/03/OIP.jpeg",
    "https://harsche.com/wp-content/uploads/2023/01/cropped-iStock-1353080098-e1672999846998-1-e1673000401406.jpg",
]
FALLBACK_MEDIA = {
    "https://harsche.com/wp-content/uploads/2023/03/5068e33d-edb2-462c-9fa2-18e3b0b3db8a-225x300-1.jpg": "https://harsche.com/wp-content/uploads/2023/09/5068e33d-edb2-462c-9fa2-18e3b0b3db8a-225x300-1.jpg",
}
MEDIA_DIR = ROOT / "docs" / "assets" / "wp-media"
DATA_PATH = ROOT / "content" / "wordpress-export.json"
HEADERS = {"User-Agent": "harsche.com-static-redesign/1.0", "Accept": "application/json"}


class ImageSrcParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources: list[str] = []
        self.assets: list[str] = []
        self.documents: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == "img":
            src = values.get("src") or values.get("data-src")
            if src:
                self.sources.append(src.strip())
        for key in ("href", "src", "data"):
            value = (values.get(key) or "").strip()
            suffix = Path(urllib.parse.urlparse(value).path).suffix.lower() if value else ""
            if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}:
                self.assets.append(value)
            if suffix in {".pdf", ".gpx", ".tcx", ".zip"}:
                self.documents.append(value)


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response), response.headers


def page_all(endpoint: str):
    items = []
    page = 1
    while True:
        url = f"{API}{endpoint}?per_page=100&page={page}&_embed=1"
        batch, headers = fetch_json(url)
        items.extend(batch)
        total_pages = int(headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            return items
        page += 1


def redact_api_keys(value: str) -> str:
    return re.sub(r'((?:\?|&|&#038;)key=)[^&#"\s]+', r'\1[removed]', value, flags=re.IGNORECASE)


def record(item: dict, kind: str) -> dict:
    embedded = item.get("_embedded", {})
    author = (embedded.get("author") or [{}])[0].get("name", "")
    terms = embedded.get("wp:term") or []
    categories = [
        {"id": t.get("id"), "slug": t.get("slug"), "name": html.unescape(t.get("name", ""))}
        for group in terms for t in group if t.get("taxonomy") == "category"
    ]
    featured = None
    media = (embedded.get("wp:featuredmedia") or [{}])[0]
    if media.get("source_url"):
        featured = {"url": media["source_url"], "alt": html.unescape(media.get("alt_text", ""))}
    path = urllib.parse.urlparse(item.get("link", "")).path or "/"
    return {
        "kind": kind,
        "id": item.get("id"),
        "slug": item.get("slug", ""),
        "path": path,
        "link": item.get("link", ""),
        "title": html.unescape(item.get("title", {}).get("rendered", "")),
        "content_html": redact_api_keys(item.get("content", {}).get("rendered", "")),
        "excerpt_html": redact_api_keys(item.get("excerpt", {}).get("rendered", "")),
        "date": item.get("date", ""),
        "modified": item.get("modified", ""),
        "author": html.unescape(author),
        "categories": categories,
        "featured_image": featured,
    }


def localize_image(url: str, failures: list[dict]) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"harsche.com", "www.harsche.com"} or "/wp-content/uploads/" not in parsed.path:
        return None
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg"}:
        suffix = ".img"
    path = MEDIA_DIR / f"{digest}{suffix}"
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                data = response.read(15 * 1024 * 1024 + 1)
                if len(data) > 15 * 1024 * 1024:
                    raise ValueError("image exceeds 15 MB limit")
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    raise ValueError(f"not an image: {content_type}")
                path.write_bytes(data)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            return None
    return path.relative_to(ROOT / "docs").as_posix()


def localize_document(url: str, failures: list[dict]) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"harsche.com", "www.harsche.com"} or "/wp-content/uploads/" not in parsed.path:
        return None
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".pdf", ".gpx", ".tcx", ".zip"}:
        return None
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    path = MEDIA_DIR / f"{digest}{suffix}"
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                data = response.read(30 * 1024 * 1024 + 1)
                if len(data) > 30 * 1024 * 1024:
                    raise ValueError("document exceeds 30 MB limit")
                path.write_bytes(data)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            return None
    return path.relative_to(ROOT / "docs").as_posix()


def main():
    pages = [record(item, "page") for item in page_all("pages")]
    posts = [record(item, "post") for item in page_all("posts")]
    category_items, _ = fetch_json(f"{API}categories?per_page=100")
    categories = [{"id": c["id"], "slug": c["slug"], "name": html.unescape(c["name"]), "count": c["count"]} for c in category_items]

    image_sources: set[str] = set(EXTRA_IMAGES)
    document_sources: set[str] = set()
    for item in pages + posts:
        if item["featured_image"]:
            image_sources.add(item["featured_image"]["url"])
        parser = ImageSrcParser()
        parser.feed(item["content_html"])
        image_sources.update(parser.sources)
        image_sources.update(parser.assets)
        document_sources.update(parser.documents)

    failures: list[dict] = []
    media = {}
    for url in sorted(image_sources):
        local = localize_image(FALLBACK_MEDIA.get(url, url), failures)
        if local:
            media[url] = local
    for url in sorted(document_sources):
        local = localize_document(url, failures)
        if local:
            media[url] = local

    export = {
        "source": "https://harsche.com",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "posts": posts,
        "categories": categories,
        "media": media,
        "media_failures": failures,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "page_count": len(pages),
        "post_count": len(posts),
        "category_count": len(categories),
        "image_urls": len(image_sources),
        "images_saved": len(media),
        "image_failures": failures,
        "export_file": str(DATA_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
