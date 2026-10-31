#!/usr/bin/env python3
"""Generate the static, responsive multi-page redesign from the WordPress export."""
from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "content" / "wordpress-export.json"
DOCS = ROOT / "docs"
SITE_BASE = "/fahrradtouren-online"
SITE_ORIGIN = "https://gharsche.github.io"
CURRENT_YEAR = "2026"
HOMEPAGE_IMAGE_URL = "https://harsche.com/wp-content/uploads/2023/01/cropped-iStock-1353080098-e1672999846998-1-e1673000401406.jpg"

NAV = [
    {"label": "Start", "path": "/", "items": []},
    {"label": "News", "path": "/news/", "items": [
        ("Neueste Gravelbike Trends", "/news/neueste-gravelbike-trends/"),
        ("Elektronische Schaltung: WheelTop EDS-TX", "/news/elektronische-schaltung-wheel-top-eds-tx/"),
        ("Nachrüstung Powermeter", "/news/nachruestung-powermeter/"),
        ("Umbau auf MAVIC Carbonfelgen", "/umbau-auf-mavic-carbonfelgen/"),
        ("Aufrüstung des Rose Backroad mit Carbonfelgen", "/aufruestung-des-rose-backroad-mit-carbonfelgen/"),
    ]},
    {"label": "Fahrradtrends", "path": "/fahrradtrends/", "items": [
        ("Rennrad", "/fahrradtrends/road-bike/"),
        ("Gravel Bike", "/fahrradtrends/gravel-bike/"),
        ("Rose Backroad GRX RX810 Di2", "/fahrradtrends/gravel-bike/backroad-grx-rx810-di2-1x11/"),
        ("Mountainbike", "/fahrradtrends/montainbike/"),
        ("E-Bike", "/fahrradtrends/e-bike/"),
    ]},
    {"label": "Touren", "path": "/touren/", "items": [
        ("Rennrad-Touren", "/touren/rennrad-tour/"),
        ("Gravel-Touren", "/gravel-bike-touren/"),
        ("Mountainbike-Touren", "/touren/mountainbike-tour/"),
        ("E-Bike-Touren", "/touren/e-bike-tour/"),
        ("Familientouren", "/touren/familie/"),
    ]},
    {"label": "Virtuelles Radfahren", "path": "/virtuelles-radfahren/", "items": [
        ("Zwift – Virtuelles Radfahren", "/virtuelles-radfahren/zwift-virtuelles-radfahren/"),
        ("Zwift-Rahmen: Ride Smarter", "/virtuelles-radfahren/zwift-bike-zwift-ride-smarter-rahmen/"),
    ]},
    {"label": "Tools & Ratgeber", "path": "/nuetzliche-tools-und-apps/", "items": [
        ("Komoot – Routenplanung", "/nuetzliche-tools-und-apps/komoot-routenplanung/"),
        ("Strava – „If it’s not on Strava, it never happened“", "/nuetzliche-tools-und-apps/strava-if-its-not-on-strava-it-never-happend/"),
        ("Das richtige Fahrrad", "/sample-page/das-richtige-fahrrad/"),
        ("Fahrradkette: Wachs oder Öl", "/fahrradkette-wachs-oder-oel/"),
        ("Sicher im Winter fahren", "/mit-dem-fahrrad-sicher-im-winter-unterwegs/"),
        ("Blinker für Fahrräder", "/blinker-fuer-fahrraeder/"),
        ("Fahrradwege: Benutzungspflicht", "/benutzung-von-fahrradwegen-ein-immer-waehrender-streitpunkt/"),
    ]},
]

ACTIVITIES = [
    ("Gravel Tour am Nachmittag ☀️ 🚴🌞", "https://strava.com/activities/20752096019", "27.10.2026 · 69,57 km · 2:17:20 h · 61 hm · 1.755 kcal"),
    ("Herbstliche Gravel Tour 🚴🌦⛅️", "https://strava.com/activities/20737839286", "26.10.2026 · 63,21 km · 2:16:53 h · 279 hm · 1.677 kcal"),
    ("Zwift - Mech Isle Mayhem in Makuri Islands", "https://strava.com/activities/20725306483", "25.10.2026 · 19,10 km · 0:35:32 h · 116 hm · 401 kcal"),
    ("Zwift - Urumaze in Makuri Islands", "https://strava.com/activities/20724741041", "25.10.2026 · 25,17 km · 0:42:44 h · 197 hm · 586 kcal"),
    ("Zwift – Eine halbe Stunde zum Runterkommen", "https://strava.com/activities/20697913675", "23.10.2026 · 9,39 km · 0:20:17 h · 60 hm · 145 kcal"),
]

CSS = r'''/* Shared visual system: forest green, fresh lime and clear editorial rhythm. */
:root{--pine:#173f35;--pine2:#245448;--leaf:#d7ec75;--paper:#f5f7f1;--white:#fff;--ink:#192821;--muted:#64736b;--line:#dce4d9;--radius:18px;--max:1240px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 "Avenir Next","Segoe UI",Arial,sans-serif}a{color:inherit;text-decoration:none}a:hover{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #8cae37;outline-offset:3px}img{max-width:100%;height:auto;display:block}.wrap{width:min(var(--max),calc(100% - 48px));margin-inline:auto}.skip{position:absolute;left:-9999px;top:8px;padding:10px 14px;background:white;z-index:20}.skip:focus{left:12px}
.site-head{background:var(--white);border-bottom:1px solid var(--line)}.brand-row{min-height:82px;display:flex;align-items:center;justify-content:space-between;gap:24px}.brand{display:inline-flex;align-items:center;gap:14px;color:var(--pine);font-weight:800;font-size:22px;letter-spacing:-.04em;line-height:1.12}.brand-mark{width:39px;height:39px;border-radius:50%;display:grid;place-items:center;background:var(--leaf);color:var(--pine);font-size:19px;flex:none}.slogan{font-size:13px;color:var(--muted);font-weight:600}.desktop-nav{border-top:1px solid #edf0e9}.nav-inner{display:flex;align-items:center;gap:5px;min-height:54px}.nav-inner>a,.nav-group>summary{font-size:13px;font-weight:700;color:var(--pine);padding:11px 12px;border-radius:999px;white-space:nowrap;cursor:pointer;list-style:none}.nav-group>summary::-webkit-details-marker{display:none}.nav-inner>a:hover,.nav-group>summary:hover,.nav-group[open]>summary{background:#eef3e7;text-decoration:none}.nav-group{position:relative}.dropdown{position:absolute;top:calc(100% + 2px);left:0;z-index:10;min-width:240px;max-width:340px;padding:10px;background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 16px 38px rgba(23,63,53,.13)}.dropdown a{display:block;padding:8px 10px;border-radius:8px;font-size:13px;line-height:1.4}.dropdown a:hover{background:#f1f5eb;text-decoration:none}.mobile-nav{display:none;padding:0 0 12px}.mobile-nav summary{list-style:none;cursor:pointer;background:var(--pine);color:white;padding:10px 15px;border-radius:999px;text-align:center;font-size:14px;font-weight:700}.mobile-nav summary::-webkit-details-marker{display:none}.mobile-links{padding:12px 4px 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px}.mobile-links a{padding:8px 6px;border-bottom:1px solid var(--line);font-size:14px}
main{padding:0 0 82px}.hero{display:grid;grid-template-columns:.86fr 1.14fr;min-height:400px;margin:24px auto 58px;background:var(--pine);border-radius:var(--radius);overflow:hidden;color:white}.hero-copy{padding:clamp(32px,5vw,70px);display:flex;flex-direction:column;justify-content:center;align-items:flex-start}.eyebrow{display:flex;align-items:center;gap:9px;color:var(--leaf);font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;margin:0 0 16px}.eyebrow:before{content:"";width:25px;height:2px;background:var(--leaf)}h1{font-size:clamp(38px,5vw,68px);letter-spacing:-.06em;line-height:1.01;margin:0 0 18px;font-weight:800;overflow-wrap:anywhere}.hero-copy p{max-width:52ch;color:#e5eee7;margin:0;font-size:16px;line-height:1.72}.hero-photo{position:relative;min-height:300px;background:#78916c}.hero-photo img{width:100%;height:100%;position:absolute;inset:0;object-fit:cover}.hero-photo:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(23,63,53,.18),transparent 38%)}.hero.no-photo{grid-template-columns:1fr;min-height:230px}.hero.no-photo .hero-copy{max-width:900px}.hero.no-photo .hero-copy p{max-width:70ch}.quote-line{font-size:15px;font-weight:600;color:#e5eee7;margin:4px 0 0}.page-grid{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:68px;align-items:start}.article{min-width:0}.content-body{color:#34433b;font-size:17px;line-height:1.8;overflow-wrap:anywhere}.content-body>*:first-child{margin-top:0}.content-body h1,.content-body h2,.content-body h3,.content-body h4{color:var(--pine);line-height:1.2;letter-spacing:-.035em;margin:2.1em 0 .7em}.content-body h1{font-size:clamp(28px,3.5vw,40px)}.content-body h2{font-size:clamp(27px,3vw,36px)}.content-body h3{font-size:clamp(23px,2.5vw,30px)}.content-body h4{font-size:21px}.content-body p{margin:0 0 1.35em}.content-body ul,.content-body ol{padding-left:1.35em;margin:0 0 1.4em}.content-body li{padding-left:.2em;margin:.32em 0}.content-body a{color:var(--pine2);text-decoration:underline;text-decoration-color:#a4b89f;text-underline-offset:3px}.content-body blockquote{margin:1.6em 0;padding:8px 0 8px 22px;border-left:3px solid var(--leaf);color:var(--pine);font-size:1.1em}.content-body figure{margin:1.5em 0}.content-body figure img{width:100%;height:auto;border-radius:12px}.content-body figcaption{font-size:13px;color:var(--muted);margin-top:7px}.content-body table{display:block;max-width:100%;overflow:auto;border-collapse:collapse;font-size:15px;margin:1.5em 0}.content-body th,.content-body td{border:1px solid var(--line);padding:9px 12px;text-align:left}.content-body th{background:#eaf0e4;color:var(--pine)}.content-body hr{border:0;border-top:1px solid var(--line);margin:2.2em 0}.content-body video,.content-body iframe{max-width:100%;width:100%;border:0;border-radius:12px}.content-body iframe{min-height:360px}.content-body .document-embed iframe{min-height:540px}.content-body .map-placeholder,.content-body .media-placeholder{min-height:190px;display:grid;place-items:center;background:#e7eee1;color:var(--pine);border:1px solid var(--line);border-radius:14px;font-weight:700;text-align:center;padding:18px;margin:1.4em 0}.content-body .media-placeholder{min-height:130px;background:#edf1e8;color:var(--muted)}.content-body .strava-embed-placeholder{min-height:80px;margin:18px 0}.article-meta{display:flex;gap:8px 16px;flex-wrap:wrap;color:var(--muted);font-size:13px;font-weight:600;margin:0 0 28px}.article-meta a{color:var(--pine2)}.featured-inline{width:100%;max-height:490px;object-fit:cover;border-radius:14px;margin:0 0 30px}.related-pages{padding-top:24px;margin-top:34px;border-top:1px solid var(--line)}.related-pages h2,.section-heading{font-size:27px;color:var(--pine);letter-spacing:-.04em;margin:0 0 16px}.link-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 22px}.link-grid a{padding:12px 14px;background:white;border-radius:10px;color:var(--pine);font-weight:700;border:1px solid var(--line)}.link-grid a:hover{background:#eef3e7;text-decoration:none}
.sidebar{border-left:1px solid var(--line);padding-left:28px}.widget{padding:0 0 25px;margin:0 0 25px;border-bottom:1px solid var(--line)}.widget h2,.widget h3{font-size:17px;letter-spacing:-.02em;color:var(--pine);margin:0 0 14px;line-height:1.25}.search-form label{display:block;font-size:13px;font-weight:700;color:var(--pine);margin-bottom:7px}.search-line{display:flex;gap:7px}.search-line input{min-width:0;flex:1;border:1px solid #cbd7cb;border-radius:9px;padding:10px 11px;background:white;color:var(--ink);font:inherit;font-size:14px}.search-line button{border:0;border-radius:9px;background:var(--pine);color:white;padding:10px 13px;font:inherit;font-size:13px;font-weight:700;cursor:pointer}.link-list,.activity-list{list-style:none;padding:0;margin:0;display:grid;gap:10px}.link-list li{font-size:14px;line-height:1.45;color:#3a4a41}.muted{color:var(--muted);font-size:14px;margin:0}.activity-list li{padding-bottom:12px;border-bottom:1px solid #e3e9e0}.activity-list li:last-child{border:0;padding:0}.activity-list a{display:block;font-size:14px;line-height:1.4;font-weight:700;color:var(--pine)}.activity-list p{font-size:12px;color:var(--muted);line-height:1.55;margin:5px 0 0}.map-block{min-height:145px;border-radius:14px;background:#e7eee1;display:grid;place-items:center;padding:16px;text-align:center;color:var(--pine);font-size:13px;font-weight:700}.product-images{display:grid;grid-template-columns:1fr 1fr;gap:10px}.product-images img{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:11px;background:#e5e9e2}.archive-columns{display:grid;grid-template-columns:1fr 1fr;gap:5px 15px}.archive-columns a{font-size:13px;color:#43554b}
.post-list{display:grid;gap:0}.post-feature{display:grid;grid-template-columns:1.05fr .95fr;background:white;border-radius:var(--radius);overflow:hidden;margin:0 0 28px;border:1px solid var(--line)}.post-feature img{width:100%;height:100%;min-height:300px;object-fit:cover}.post-feature-copy{padding:28px 30px;align-self:center}.post-feature h2{font-size:clamp(25px,3vw,34px);letter-spacing:-.045em;line-height:1.13;color:var(--pine);margin:0 0 12px}.post-feature p,.post-row p{color:#526158;margin:0 0 14px;font-size:15px;line-height:1.65}.post-row{display:grid;grid-template-columns:160px minmax(0,1fr);gap:23px;padding:23px 0;border-bottom:1px solid var(--line);align-items:center}.post-row img{width:160px;height:118px;object-fit:cover;border-radius:11px;background:#e5e9e2}.post-row h2{font-size:23px;line-height:1.2;letter-spacing:-.035em;color:var(--pine);margin:0 0 8px}.post-meta{font-size:12px;color:var(--muted);font-weight:700;margin-bottom:8px}.read-more{display:inline-flex;align-items:center;gap:7px;color:var(--pine);font-weight:800;font-size:14px}.read-more:after{content:"→";transition:transform .18s ease}.read-more:hover:after{transform:translateX(3px)}.pagination{display:flex;justify-content:space-between;gap:18px;margin-top:28px;color:var(--pine);font-weight:700}.search-results{display:grid;gap:14px}.search-result{padding:16px 0;border-bottom:1px solid var(--line)}.search-result h2{font-size:21px;color:var(--pine);margin:0 0 5px}.search-result p{margin:0;color:var(--muted);font-size:14px}
.site-footer{background:#173f35;color:#e8f0e9;padding:42px 0}.footer-inner{display:flex;justify-content:space-between;align-items:flex-start;gap:40px}.footer-brand{font-size:18px;font-weight:800;letter-spacing:-.03em}.footer-quote{font-size:13px;color:#c8d5ca;margin:5px 0 0}.footer-links{display:flex;gap:18px;align-items:center;font-size:13px;flex-wrap:wrap}.footer-links span{font-weight:800}.copyright{font-size:12px;color:#c8d5ca;margin-top:23px}.empty-note{padding:24px;border:1px solid var(--line);background:white;border-radius:12px;color:var(--muted)}
@media(max-width:1100px){.nav-inner{gap:0}.nav-inner>a,.nav-group>summary{padding:10px 8px;font-size:12px}.page-grid{gap:38px;grid-template-columns:minmax(0,1fr) 280px}.hero{grid-template-columns:.95fr 1.05fr}}
@media(max-width:850px){.desktop-nav{display:none}.mobile-nav{display:block}.brand-row{min-height:76px}.slogan{display:none}.hero{grid-template-columns:1fr;margin-top:16px;margin-bottom:46px;min-height:0}.hero-photo{grid-row:1;min-height:300px}.hero-copy{grid-row:2;padding:34px}.hero.no-photo .hero-copy{grid-row:1}.page-grid{grid-template-columns:1fr;gap:42px}.sidebar{border-left:0;border-top:1px solid var(--line);padding:30px 0 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px 30px}.widget{margin:0;padding-bottom:22px}.footer-inner{display:block}.footer-links{margin-top:18px}.post-feature{grid-template-columns:1fr}.post-feature img{height:280px;min-height:0}.post-feature-copy{padding:24px}.hero.no-photo{min-height:220px}}
@media(max-width:540px){.wrap{width:min(var(--max),calc(100% - 30px))}.brand{font-size:18px}.brand-mark{width:34px;height:34px}.hero{border-radius:14px}.hero-photo{min-height:240px}.hero-copy{padding:28px 23px 32px}h1{font-size:clamp(36px,12vw,52px)}.content-body{font-size:16px}.page-grid{gap:34px}.sidebar{grid-template-columns:1fr;gap:20px}.mobile-links{grid-template-columns:1fr}.post-row{grid-template-columns:1fr;gap:12px}.post-row img{width:100%;height:210px}.post-row h2{font-size:21px}.link-grid{grid-template-columns:1fr}.article-meta{margin-bottom:20px}.hero.no-photo{min-height:190px}.hero.no-photo .hero-copy{padding:29px 23px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.read-more:after{transition:none}}
'''

JS = r'''document.addEventListener('click',event=>{document.querySelectorAll('.nav-group[open]').forEach(menu=>{if(!menu.contains(event.target))menu.removeAttribute('open')})});
const form=document.querySelector('[data-search-form]');
if(form){form.addEventListener('submit',event=>{const input=form.querySelector('input[name="s"]');if(!input||!input.value.trim()){event.preventDefault();input?.focus()}})}
if(document.body.dataset.searchPage==='true'){
 const query=new URLSearchParams(location.search).get('s')||'';
 const input=document.querySelector('#search-query'); if(input)input.value=query;
 const status=document.querySelector('#search-status'); const results=document.querySelector('#search-results');
 if(query&&status&&results){fetch(window.SITE_BASE+'/assets/search-index.json').then(r=>r.json()).then(items=>{const q=query.toLocaleLowerCase('de');const found=items.filter(x=>(x.title+' '+x.text).toLocaleLowerCase('de').includes(q));status.textContent=found.length+' Treffer';for(const item of found){const box=document.createElement('article');box.className='search-result';const h=document.createElement('h2');const a=document.createElement('a');a.href=window.SITE_BASE+item.path;a.textContent=item.title;h.appendChild(a);const p=document.createElement('p');p.textContent=item.text.slice(0,260);box.append(h,p);results.appendChild(box)}if(!found.length)status.textContent='Keine Treffer';}).catch(()=>{status.textContent='Die Suche ist momentan nicht verfügbar.'})}
}
'''


def esc(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def site_url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return SITE_BASE + path


def local_asset(path: str | None) -> str:
    if not path:
        return ""
    return site_url("/" + path.lstrip("/"))


def clean_text(markup: str) -> str:
    class TextOnly(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.bits = []
            self.skip = False
        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style"}:
                self.skip = True
        def handle_endtag(self, tag):
            if tag in {"script", "style"}:
                self.skip = False
        def handle_data(self, data):
            if not self.skip:
                self.bits.append(data)
    parser = TextOnly()
    parser.feed(markup or "")
    return re.sub(r"\s+", " ", " ".join(parser.bits)).strip()


class ContentCleaner(HTMLParser):
    allowed = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "b", "em", "i", "u", "s", "del", "ins", "blockquote", "a", "figure", "figcaption", "img", "table", "thead", "tbody", "tfoot", "tr", "th", "td", "br", "hr", "div", "span", "iframe", "video", "audio", "source", "details", "summary", "dl", "dt", "dd", "code", "pre", "sup", "sub"}
    void = {"img", "br", "hr", "source"}
    skip_tags = {"script", "style"}
    def __init__(self, media: dict, site_base: str):
        super().__init__(convert_charrefs=True)
        self.media = media
        self.site_base = site_base
        self.out: list[str] = []
        self.stack: list[str] = []
        self.blocked: str | None = None
        self.blocked_depth = 0

    def mapped_url(self, raw: str) -> str:
        raw = html.unescape(raw.strip())
        if not raw:
            return ""
        if raw in self.media:
            return local_asset(self.media[raw])
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host in {"harsche.com", "www.harsche.com", "fahrradtouren.online", "www.fahrradtouren.online"}:
            if "/wp-content/uploads/" in parsed.path:
                return raw
            return self.site_base + (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "") + (("#" + parsed.fragment) if parsed.fragment else "")
        return raw

    def _push(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag not in self.allowed:
            return
        values = dict(attrs)
        safe: list[tuple[str, str]] = []
        class_value = values.get("class") or ""
        if class_value:
            classes = re.findall(r"[A-Za-z0-9_-]+", class_value)
            if classes:
                safe.append(("class", " ".join(classes)))
        id_value = values.get("id") or ""
        if id_value and re.fullmatch(r"[A-Za-z0-9_:-]+", id_value):
            safe.append(("id", id_value))
        title_value = values.get("title") or ""
        if title_value:
            safe.append(("title", title_value))
        aria_label = values.get("aria-label") or ""
        if aria_label:
            safe.append(("aria-label", aria_label))
        if tag == "a":
            raw_href = values.get("href") or ""
            parsed_href = urlparse(html.unescape(raw_href))
            if parsed_href.hostname in {"harsche.com", "www.harsche.com"} and "/wp-content/uploads/" in parsed_href.path and raw_href not in self.media:
                href = ""
            else:
                href = self.mapped_url(raw_href)
            if href.startswith(("https://", "http://", "mailto:", "tel:", "#", SITE_BASE)):
                safe.append(("href", href))
            if values.get("target") == "_blank":
                safe.extend([("target", "_blank"), ("rel", "noopener noreferrer")])
            if "download" in values:
                safe.append(("download", ""))
        elif tag == "img":
            raw = values.get("src") or values.get("data-src") or ""
            parsed = urlparse(html.unescape(raw))
            if parsed.hostname == "maps.googleapis.com":
                self.out.append('<div class="map-placeholder" role="img" aria-label="Kartenansicht aus der Originalseite">Kartenmodul der Originalseite hier wieder einbinden</div>')
                return
            if parsed.hostname in {"harsche.com", "www.harsche.com"} and "/wp-content/uploads/" in parsed.path and raw not in self.media:
                missing_alt = values.get("alt") or ""
                label = missing_alt or "Bild der Originalseite ist nicht verfügbar"
                self.out.append(f'<div class="media-placeholder" role="img" aria-label="{esc(label)}">{esc(label)}</div>')
                return
            src = self.mapped_url(raw)
            if src:
                safe.append(("src", src))
            safe.append(("alt", values.get("alt") or ""))
            safe.append(("loading", "lazy"))
            for dimension in ("width", "height"):
                dimension_value = values.get(dimension) or ""
                if dimension_value.isdigit():
                    safe.append((dimension, dimension_value))
        elif tag == "iframe":
            src = self.mapped_url(values.get("src") or "")
            host = (urlparse(src).hostname or "").lower()
            if host not in {"stadtradeln.de", "www.stadtradeln.de"}:
                return
            safe.append(("src", src))
            safe.append(("title", values.get("title") or "Eingebetteter Inhalt"))
            safe.append(("loading", "lazy"))
            safe.append(("referrerpolicy", "strict-origin-when-cross-origin"))
            safe.append(("allowfullscreen", ""))
        elif tag in {"video", "audio"}:
            if "controls" in values:
                safe.append(("controls", ""))
            poster = values.get("poster") or ""
            if poster:
                safe.append(("poster", self.mapped_url(poster)))
        elif tag == "source":
            src = values.get("src") or ""
            if src:
                safe.append(("src", self.mapped_url(src)))
            source_type = values.get("type") or ""
            if source_type:
                safe.append(("type", source_type))
        elif tag in {"th", "td"}:
            for name in ("colspan", "rowspan", "scope"):
                value = values.get(name) or ""
                if value:
                    safe.append((name, value))
        elif tag == "ol":
            start_value = values.get("start") or ""
            if start_value.isdigit():
                safe.append(("start", start_value))
        attrs_text = "".join(f' {name}="{esc(value)}"' for name, value in safe)
        self.out.append(f"<{tag}{attrs_text}>")
        if tag not in self.void:
            self.stack.append(tag)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if self.blocked:
            if tag == self.blocked:
                self.blocked_depth += 1
            return
        if tag in self.skip_tags:
            if tag == "script" and values.get("src") == "https://strava-embeds.com/embed.js":
                self.out.append('<script src="https://strava-embeds.com/embed.js" async></script>')
                return
            self.blocked, self.blocked_depth = tag, 1
            return
        if tag == "object":
            src = self.mapped_url(values.get("data") or "")
            if src and src.endswith(".pdf"):
                self.out.append(f'<div class="document-embed"><iframe src="{esc(src)}" title="PDF Dokument" loading="lazy"></iframe></div>')
            self.blocked, self.blocked_depth = tag, 1
            return
        if tag == "div" and values.get("class") == "strava-embed-placeholder":
            safe = [("class", "strava-embed-placeholder")]
            for key in ("data-embed-type", "data-embed-id", "data-style", "data-from-embed"):
                value = values.get(key) or ""
                if value:
                    safe.append((key, value))
            self.out.append("<div" + "".join(f' {k}="{esc(v)}"' for k, v in safe) + ">")
            self.stack.append("div")
            return
        self._push(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void and self.stack and self.stack[-1] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked:
                self.blocked_depth -= 1
                if self.blocked_depth <= 0:
                    self.blocked = None
            return
        if tag in self.skip_tags:
            return
        if tag in self.stack:
            while self.stack:
                current = self.stack.pop()
                self.out.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data):
        if not self.blocked:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitized(markup: str, media: dict) -> str:
    parser = ContentCleaner(media, SITE_BASE)
    parser.feed(markup or "")
    return parser.result()


def page_path(path: str) -> Path:
    safe = Path(path.strip("/")) if path != "/" else Path()
    if any(part == ".." for part in safe.parts):
        raise ValueError(f"Unsafe route: {path}")
    return DOCS / safe / "index.html" if safe.parts else DOCS / "index.html"


def write_route(path: str, markup: str):
    target = page_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup, encoding="utf-8")


def nav_html(current_path: str) -> tuple[str, str]:
    desktop = []
    mobile = []
    for item in NAV:
        url = site_url(item["path"])
        if item["items"]:
            links = [(f"Übersicht: {item['label']}", item["path"])] + item["items"]
            dlinks = "".join(f'<a href="{site_url(path)}">{esc(label)}</a>' for label, path in links)
            desktop.append(f'<details class="nav-group"><summary>{esc(item["label"])}</summary><div class="dropdown">{dlinks}</div></details>')
            mobile.extend(f'<a href="{site_url(path)}">{esc(label)}</a>' for label, path in links)
        else:
            desktop.append(f'<a href="{url}"{(" aria-current=\"page\"" if current_path == item["path"] else "")}>{esc(item["label"])}</a>')
            mobile.append(f'<a href="{url}">{esc(item["label"])}</a>')
    desktop_markup = '<nav class="desktop-nav" aria-label="Hauptnavigation"><div class="wrap nav-inner">' + "".join(desktop) + "</div></nav>"
    mobile_markup = '<div class="wrap mobile-nav"><details><summary>Menü</summary><div class="mobile-links">' + "".join(mobile) + "</div></details></div>"
    return desktop_markup, mobile_markup


def sidebar_html(data: dict) -> str:
    media = data["media"]
    posts = data["posts"][:5]
    latest = "".join(f'<li><a href="{site_url(p["path"])}">{esc(p["title"])}</a></li>' for p in posts)
    activity_rows = "".join(f'<li><a href="{esc(url)}">{esc(title)}</a><p>{esc(text)}</p></li>' for title, url, text in ACTIVITIES)
    months = sorted({p["date"][:7] for p in data["posts"] if len(p["date"]) >= 7}, reverse=True)
    month_labels = {"01":"Januar","02":"Februar","03":"März","04":"April","05":"Mai","06":"Juni","07":"Juli","08":"August","09":"September","10":"Oktober","11":"November","12":"Dezember"}
    archive = "".join(f'<a href="{site_url("/"+month[:4]+"/"+month[5:7]+"/")}">{month_labels.get(month[5:7],month[5:7])} {month[:4]}</a>' for month in months)
    cats = "".join(f'<a href="{site_url("/category/"+c["slug"]+"/")}">{esc(c["name"])}</a>' for c in data["categories"])
    product = []
    for marker in ("81Yuisb", "OIP.jpeg"):
        asset = next((local_asset(path) for url,path in media.items() if marker in url), "")
        if asset:
            product.append(f'<img src="{asset}" alt="" loading="lazy">')
    return f'''<aside class="sidebar" aria-label="Weitere Inhalte">
<section class="widget"><form class="search-form" data-search-form action="{site_url('/search/')}" method="get"><label for="site-search">Suchen</label><div class="search-line"><input id="site-search" type="search" name="s" aria-label="Suchen"><button type="submit">Suchen</button></div></form></section>
<section class="widget"><h2>Aktuelle Posts</h2><ul class="link-list">{latest}</ul></section>
<section class="widget"><h2>Aktuelle Kommentare</h2><p class="muted">Es sind keine Kommentare vorhanden.</p></section>
<section class="widget"><h3>Meine letzten Ausfahrten</h3><ul class="activity-list">{activity_rows}</ul></section>
<section class="widget"><h3>Letzte Aktivität auf der Karte</h3><div class="map-block" role="img" aria-label="Platzhalter für die bestehende Aktivitätskarte">Kartenmodul der Originalseite hier wieder einbinden</div></section>
<section class="widget"><h2>Der ultimative Powerriegel:</h2><div class="product-images">{"".join(product)}</div></section>
<section class="widget"><h2>Archiv</h2><div class="archive-columns">{archive}</div></section>
<section class="widget"><h2>Kategorien</h2><div class="archive-columns">{cats}</div></section>
</aside>'''


def shell(title: str, main: str, data: dict, current_path: str, body_attr: str = "") -> str:
    desktop, mobile = nav_html(current_path)
    title_text = esc(title + " | Radfahren an der Bergstraße")
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(clean_text(main)[:190])}"><title>{title_text}</title><link rel="stylesheet" href="{site_url('/assets/site.css')}"><script>window.SITE_BASE={json.dumps(SITE_BASE)};</script><script defer src="{site_url('/assets/site.js')}"></script></head><body {body_attr}><a class="skip" href="#inhalt">Zum Inhalt springen</a><header class="site-head"><div class="wrap brand-row"><a class="brand" href="{site_url('/')}" aria-label="Radfahren an der Bergstraße, Startseite"><span class="brand-mark" aria-hidden="true">↗</span><span>Radfahren an der Bergstraße</span></a><div class="slogan">„Keine Gnade für die Wade“ (Louis J. Halle)</div></div>{desktop}{mobile}</header><main id="inhalt" class="wrap">{main}</main><footer class="site-footer"><div class="wrap"><div class="footer-inner"><div><div class="footer-brand">Radfahren an der Bergstraße</div><p class="footer-quote">„Keine Gnade für die Wade“ (Louis J. Halle)</p></div><div class="footer-links"><span>Rechtliches</span><a href="{site_url('/datenschutzerklaerung/')}">Datenschutzerklärung</a><a href="{site_url('/impressum/')}">Impressum</a></div></div><div class="copyright">© {CURRENT_YEAR}</div></div></footer></body></html>'''


def hero(title: str, *, eyebrow: str = "", image: str = "", image_alt: str = "", description: str = "", quote: str = "") -> str:
    label = f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    desc = f'<p>{esc(description)}</p>' if description else ""
    quote_html = f'<p class="quote-line">{esc(quote)}</p>' if quote else ""
    if image:
        return f'<section class="hero" aria-label="{esc(title)}"><div class="hero-copy">{label}<h1>{esc(title)}</h1>{desc}{quote_html}</div><div class="hero-photo"><img src="{esc(image)}" alt="{esc(image_alt)}" fetchpriority="high"></div></section>'
    return f'<section class="hero no-photo" aria-label="{esc(title)}"><div class="hero-copy">{label}<h1>{esc(title)}</h1>{desc}{quote_html}</div></section>'


def render_page(record: dict, data: dict, pages_by_path: dict) -> str:
    title = record["title"] or "Radfahren an der Bergstraße"
    body = sanitized(record["content_html"], data["media"])
    featured = record.get("featured_image") or {}
    img = local_asset(data["media"].get(featured.get("url", "")))
    image_alt = featured.get("alt", "")
    if not img and record["path"] == "/touren/":
        img = site_url("/assets/bergstrasse-cycling.png")
        image_alt = "Zwei Radfahrende unterwegs durch die Landschaft der Bergstraße"
    meta = ""
    if record["kind"] == "post":
        categories = record.get("categories") or []
        bits = []
        if record.get("author"):
            bits.append(esc(record["author"]))
        date = record.get("date", "")
        if date:
            try:
                bits.append(datetime.fromisoformat(date).strftime("%d.%m.%Y"))
            except ValueError:
                bits.append(date[:10])
        bits.extend(f'<a href="{site_url("/category/"+c["slug"]+"/")}">{esc(c["name"])}</a>' for c in categories)
        meta = '<div class="article-meta">' + "<span> / </span>".join(bits) + "</div>"
    eyebrow = (record.get("categories") or [{}])[0].get("name", "") if record["kind"] == "post" else ""
    content = f'<article class="article">{meta}'
    if body:
        content += f'<div class="content-body">{body}</div>'
    else:
        children = direct_children(record["path"], pages_by_path)
        if children:
            items = "".join(f'<a href="{site_url(p["path"])}">{esc(p["title"])}</a>' for p in children)
            content += f'<section class="related-pages"><h2>Weitere Seiten</h2><div class="link-grid">{items}</div></section>'
        elif record["kind"] == "page":
            content += '<p class="empty-note">' + esc(title) + '</p>'
    content += '</article>'
    top = hero(title, eyebrow=eyebrow, image=img, image_alt=image_alt)
    content = f'<div class="page-grid">{content}{sidebar_html(data)}</div>'
    return shell(title, top + content, data, record["path"])


def direct_children(path: str, pages_by_path: dict) -> list[dict]:
    parent = path.strip("/").split("/") if path.strip("/") else []
    output = []
    for candidate in pages_by_path.values():
        parts = candidate["path"].strip("/").split("/") if candidate["path"].strip("/") else []
        if len(parts) == len(parent) + 1 and parts[:len(parent)] == parent:
            output.append(candidate)
    return sorted(output, key=lambda x: x["title"].lower())


def listing_excerpt(post: dict, media: dict) -> str:
    excerpt = sanitized(post.get("excerpt_html", ""), media)
    if excerpt:
        return excerpt
    words = clean_text(post.get("content_html", "")).split()
    return esc(" ".join(words[:45]))


def post_rows(posts: list[dict], data: dict) -> str:
    if not posts:
        return '<p class="empty-note">Keine Beiträge vorhanden.</p>'
    blocks = []
    for index, post in enumerate(posts):
        image_url = (post.get("featured_image") or {}).get("url", "")
        image = local_asset(data["media"].get(image_url))
        categories = post.get("categories") or []
        category = f'<a href="{site_url("/category/"+categories[0]["slug"]+"/")}">{esc(categories[0]["name"])}</a>' if categories else ""
        date = post.get("date", "")
        try:
            date = datetime.fromisoformat(date).strftime("%d.%m.%Y")
        except ValueError:
            date = date[:10]
        meta = " · ".join(x for x in [esc(post.get("author", "")), esc(date), category] if x)
        excerpt = listing_excerpt(post, data["media"])
        if index == 0 and image:
            blocks.append(f'<article class="post-feature"><img src="{esc(image)}" alt="{esc((post.get("featured_image") or {}).get("alt", ""))}" loading="lazy"><div class="post-feature-copy"><div class="post-meta">{meta}</div><h2><a href="{site_url(post["path"])}">{esc(post["title"])}</a></h2><div class="post-excerpt">{excerpt}</div><a class="read-more" href="{site_url(post["path"])}">Weiterlesen</a></div></article>')
        else:
            img_html = f'<a href="{site_url(post["path"])}"><img src="{esc(image)}" alt="{esc((post.get("featured_image") or {}).get("alt", ""))}" loading="lazy"></a>' if image else ""
            blocks.append(f'<article class="post-row">{img_html}<div><div class="post-meta">{meta}</div><h2><a href="{site_url(post["path"])}">{esc(post["title"])}</a></h2><div class="post-excerpt">{excerpt}</div><a class="read-more" href="{site_url(post["path"])}">Weiterlesen</a></div></article>')
    return '<div class="post-list">' + "".join(blocks) + "</div>"


def pagination(base_path: str, page_number: int, page_count: int) -> str:
    if page_count <= 1:
        return ""
    if base_path == "/":
        target = lambda n: "/" if n == 1 else f"/page/{n}/"
    else:
        target = lambda n: base_path.rstrip("/") + ("/" if n == 1 else f"/page/{n}/")
    left = f'<a href="{site_url(target(page_number-1))}">← Neuere Beiträge</a>' if page_number > 1 else "<span></span>"
    right = f'<a href="{site_url(target(page_number+1))}">Ältere Beiträge →</a>' if page_number < page_count else "<span></span>"
    return f'<nav class="pagination" aria-label="Seitennavigation">{left}<span>Seite {page_number} von {page_count}</span>{right}</nav>'


def render_listing(title: str, posts: list[dict], data: dict, route: str, page_number: int = 1, *, description: str = "") -> str:
    page_size = 10
    count = max(1, (len(posts) + page_size - 1) // page_size)
    selected = posts[(page_number - 1) * page_size:page_number * page_size]
    lead_image = ""
    lead_alt = ""
    if route == "/":
        lead_image = local_asset(data["media"].get(HOMEPAGE_IMAGE_URL))
        if lead_image:
            lead_alt = "Radfahren an der Bergstraße"
        else:
            first = posts[0] if posts else None
            if first and first.get("featured_image"):
                lead_image = local_asset(data["media"].get(first["featured_image"]["url"]))
                lead_alt = (first.get("featured_image") or {}).get("alt", "")
        if not lead_image and (DOCS / "assets" / "bergstrasse-cycling.png").exists():
            lead_image = site_url("/assets/bergstrasse-cycling.png")
            lead_alt = "Zwei Radfahrende unterwegs durch die Landschaft der Bergstraße"
    top = hero(title, image=lead_image, image_alt=lead_alt, description=description, quote='„Keine Gnade für die Wade“ (Louis J. Halle)' if route == "/" else "")
    main = f'{top}<div class="page-grid"><section class="article"><h2 class="section-heading">Aktuelle Posts</h2>{post_rows(selected, data)}{pagination(route, page_number, count)}</section>{sidebar_html(data)}</div>'
    return shell(title, main, data, route)


def render_search(data: dict) -> str:
    main = f'''<section class="hero no-photo"><div class="hero-copy"><div class="eyebrow">Suche</div><h1>Suchergebnisse</h1><p id="search-status">Suchbegriff eingeben.</p></div></section><div class="page-grid"><section class="article"><form class="search-form" data-search-form action="{site_url('/search/')}" method="get"><label for="search-query">Suchen</label><div class="search-line"><input id="search-query" type="search" name="s"><button type="submit">Suchen</button></div></form><div id="search-results" class="search-results"></div></section>{sidebar_html(data)}</div>'''
    return shell("Suche", main, data, "/search/", 'data-search-page="true"')


def make_archive_records(posts: list[dict]) -> tuple[dict, dict]:
    by_category: dict[str, list[dict]] = defaultdict(list)
    by_month: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        for cat in post.get("categories", []):
            by_category[cat["slug"]].append(post)
        if len(post.get("date", "")) >= 7:
            by_month[post["date"][:7]].append(post)
    for values in by_category.values():
        values.sort(key=lambda x: x.get("date", ""), reverse=True)
    for values in by_month.values():
        values.sort(key=lambda x: x.get("date", ""), reverse=True)
    return by_category, by_month


def build(data: dict):
    if DOCS.exists():
        for child in DOCS.iterdir():
            if child.name == "assets":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        DOCS.mkdir(parents=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    (DOCS / "assets" / "site.js").write_text(JS, encoding="utf-8")
    generated_hero = ROOT / "bergstrasse-cycling.png"
    if generated_hero.exists():
        shutil.copy2(generated_hero, DOCS / "assets" / "bergstrasse-cycling.png")

    posts = sorted(data["posts"], key=lambda x: x.get("date", ""), reverse=True)
    pages = data["pages"]
    pages_by_path = {p["path"]: p for p in pages}
    for record in pages + posts:
        write_route(record["path"], render_page(record, data, pages_by_path))

    page_count = max(1, (len(posts) + 9) // 10)
    for n in range(1, page_count + 1):
        route = "/" if n == 1 else f"/page/{n}/"
        write_route(route, render_listing("Radfahren an der Bergstraße", posts, data, "/", n))

    by_category, by_month = make_archive_records(posts)
    for category in data["categories"]:
        group = by_category.get(category["slug"], [])
        title = category["name"]
        route = "/category/" + category["slug"] + "/"
        count = max(1, (len(group) + 9) // 10)
        for n in range(1, count + 1):
            target = route if n == 1 else route.rstrip("/") + f"/page/{n}/"
            label = title if n == 1 else f"{title}, Seite {n}"
            write_route(target, render_listing(label, group, data, route, n))
    month_labels = {"01":"Januar","02":"Februar","03":"März","04":"April","05":"Mai","06":"Juni","07":"Juli","08":"August","09":"September","10":"Oktober","11":"November","12":"Dezember"}
    for month, group in by_month.items():
        route = f"/{month[:4]}/{month[5:7]}/"
        title = f"{month_labels.get(month[5:7], month[5:7])} {month[:4]}"
        write_route(route, render_listing(title, group, data, route))

    write_route("/search/", render_search(data))
    base_for_json = [{"title":p["title"],"path":p["path"],"text":clean_text(p.get("excerpt_html", "")) or clean_text(p.get("content_html", ""))} for p in pages + posts]
    (DOCS / "assets" / "search-index.json").write_text(json.dumps(base_for_json, ensure_ascii=False), encoding="utf-8")

    routes = {p["path"] for p in pages + posts} | {"/"}
    routes |= {"/page/2/", "/page/3/"} if page_count >= 3 else set()
    routes |= {"/category/" + c["slug"] + "/" for c in data["categories"]}
    routes |= {"/"+m[:4]+"/"+m[5:7]+"/" for m in by_month}
    routes.add("/search/")
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f'<url><loc>{SITE_ORIGIN}{site_url(route)}</loc></url>' for route in sorted(routes)) + '</urlset>'
    (DOCS / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_ORIGIN}{site_url('/sitemap.xml')}\n", encoding="utf-8")
    write_route("/404/", shell("Seite nicht gefunden", '<section class="hero no-photo"><div class="hero-copy"><h1>Seite nicht gefunden</h1><p>Diese Seite konnte leider nicht gefunden werden.</p><a class="read-more" href="'+site_url('/')+'">Zur Startseite</a></div></section>', data, "/404/"))
    (DOCS / "404.html").write_text(shell("Seite nicht gefunden", '<section class="hero no-photo"><div class="hero-copy"><h1>Seite nicht gefunden</h1><p>Diese Seite konnte leider nicht gefunden werden.</p><a class="read-more" href="'+site_url('/')+'">Zur Startseite</a></div></section>', data, "/404/"), encoding="utf-8")
    print(json.dumps({"pages":len(pages),"posts":len(posts),"content_routes":len(pages)+len(posts),"categories":len(data['categories']),"month_archives":len(by_month),"homepage_pages":page_count,"total_html_routes":len(list(DOCS.rglob('index.html')))+1,"docs":str(DOCS)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    build(json.loads(DATA_PATH.read_text(encoding="utf-8")))
