#!/usr/bin/env python3
"""
CANVAS WOMAN — static site builder

    python3 build.py                     build the site into ./dist
    python3 build.py --serve             build, then preview at http://localhost:8000
    python3 build.py --base-path /repo   build for a GitHub project-page preview

Everything a visitor reads comes from content/site.toml and content/paintings.toml.
Requires Python 3.11+ and Pillow (pip install -r requirements.txt).
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import html
import http.server
import json
import re
import shutil
import socketserver
import sys
import tomllib
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required:  pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
IMAGES = CONTENT / "images"
SRC = ROOT / "src"
DIST = ROOT / "dist"
TOOL_FONTS = ROOT / "tools" / "fonts"

WIDTHS = (480, 960, 1600)
AVAILABILITY = {
    "available": {"label": "Available", "schema": "https://schema.org/InStock"},
    "sold": {"label": "Sold", "schema": "https://schema.org/SoldOut"},
    "commission": {"label": "Private commission", "schema": None},
    "made-to-order": {"label": "Made to order", "schema": "https://schema.org/MadeToOrder"},
}
NOUNS = {"abstract": "abstract painting", "texture": "textured painting",
         "landscape": "landscape painting", "pop": "contemporary pop painting"}
RESERVED = {"index", "assets", "images", "og"}
NAV = [("Home", "/"), ("Paintings", "/paintings/"), ("Commissions", "/commissions/"),
       ("About", "/about/"), ("The Art", "/the-art/"), ("Contact", "/contact/")]
FRAMES = [("minimal", "Minimal modern"), ("float-black", "Sleek floating, black"),
          ("float-white", "Sleek floating, white"), ("wood", "Thick / vintage wooden"),
          ("gold", "Gold"), ("colour", "Coloured"), ("other", "Other styles")]

S_HERO = "(min-width: 1024px) 38vw, 88vw"
S_SALON = "(min-width: 800px) 30vw, 80vw"
S_CARD = "(min-width: 1024px) 28vw, (min-width: 600px) 44vw, 88vw"
S_WIDE = "(min-width: 800px) 56vw, 92vw"
S_GALLERY = "(min-width: 960px) 56vw, 92vw"
S_TILE = "(min-width: 800px) 16vw, 33vw"

ICON_WA = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.26-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.7.63.71.22 1.36.19 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.41-.08-.13-.28-.2-.57-.35m-5.42 7.4h-.01a9.87 9.87 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.88 9.89-9.88 2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 0 1 2.89 6.99c0 5.45-4.44 9.88-9.88 9.88m8.41-18.3A11.82 11.82 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 0 0 5.68 1.45h.01c6.55 0 11.89-5.34 11.89-11.89a11.82 11.82 0 0 0-3.48-8.41Z"/></svg>')
ICON_IG = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4.1"/><circle cx="17.4" cy="6.6" r="1.05" fill="currentColor" stroke="none"/></svg>')
ICON_PREV = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15 5l-7 7 7 7"/></svg>'
ICON_NEXT = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5l7 7-7 7"/></svg>'

SITE: dict = {}
MSG: dict = {}
CATS: list = []
CAT_BY_KEY: dict = {}
PAINTINGS: list = []
BY_SLUG: dict = {}
PREVIEW = False
BASE = ""
ASSET_V: dict = {}
PAGES: list = []
IMG = None
ARTIST = ""


class BuildError(Exception):
    pass


# ------------------------------------------------------------------ helpers
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def u(path: str) -> str:
    return BASE + path


def absolute(path: str) -> str:
    return SITE["site"]["url"].rstrip("/") + path


def wa(text: str) -> str:
    return "https://wa.me/" + SITE["contact"]["whatsapp"] + "?text=" + quote(text, safe="")


def msg(key: str, p: dict | None = None) -> str:
    text = MSG[key]
    if p:
        text = text.replace("{title}", p["title"]).replace("{url}", p["url"])
    return text


def inr(amount: int) -> str:
    s = str(int(amount))
    if len(s) <= 3:
        return "₹" + s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts) + "," + tail


def num(x) -> str:
    x = float(x)
    return str(int(x)) if x.is_integer() else f"{x:.1f}".rstrip("0").rstrip(".")


def inches(p) -> tuple[float, float]:
    f = 1 if p["unit"] == "in" else 1 / 2.54
    return p["width"] * f, p["height"] * f


def dims(p) -> tuple[str, str]:
    w, h = p["width"], p["height"]
    if p["unit"] == "in":
        return f"{num(w)} × {num(h)} in", f"{round(w * 2.54)} × {round(h * 2.54)} cm"
    return f"{num(w)} × {num(h)} cm", f"{num(round(w / 2.54, 1))} × {num(round(h / 2.54, 1))} in"


def length(value_in: float) -> str:
    return f"{num(round(value_in))} in ({round(value_in * 2.54)} cm)"


def paragraphs(text: str) -> str:
    return "".join(f"<p>{esc(block.strip())}</p>" for block in re.split(r"\n\s*\n", text.strip()) if block.strip())


def current(flag: bool) -> str:
    return ' aria-current="page"' if flag else ""


def price_short(p) -> str:
    a = p["availability"]
    if a == "sold":
        return "Sold"
    if a == "commission":
        return "Private commission"
    price = inr(p["price"]) if p["price"] else "Price on request"
    return price + ", made to order" if a == "made-to-order" else price


def alt_primary(p) -> str:
    noun = NOUNS.get(p["category"], p["cat"]["name"].lower() + " painting")
    return f"{p['title']}, {noun} by {ARTIST}, {p['medium'].lower()}, {dims(p)[0]}"


def clip(text: str, limit: int = 158) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:—") + "…"


# ------------------------------------------------------------------ images
class Images:
    def __init__(self):
        self.cache: dict = {}
        self.written: set = set()

    def get(self, rel: str) -> dict:
        if rel in self.cache:
            return self.cache[rel]
        src = IMAGES / rel
        stem = Path(rel).with_suffix("")
        out_dir = DIST / "images" / stem.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        web = "/images/" + stem.parent.as_posix() + "/"
        mtime = src.stat().st_mtime
        with Image.open(src) as opened:
            im = ImageOps.exif_transpose(opened)
            w, h = im.size
            rgb = None
            srcset = []
            for tw in sorted({min(t, w) for t in WIDTHS}):
                name = f"{stem.name}-{tw}.webp"
                out = out_dir / name
                self.written.add(out)
                if not out.exists() or out.stat().st_mtime < mtime:
                    rgb = rgb if rgb is not None else im.convert("RGB")
                    rgb.resize((tw, round(h * tw / w)), Image.LANCZOS).save(out, "WEBP", quality=82, method=5)
                srcset.append((tw, web + name))
            fw = min(1200, w)
            fname = f"{stem.name}-{fw}.jpg"
            fout = out_dir / fname
            self.written.add(fout)
            if not fout.exists() or fout.stat().st_mtime < mtime:
                rgb = rgb if rgb is not None else im.convert("RGB")
                rgb.resize((fw, round(h * fw / w)), Image.LANCZOS).save(fout, "JPEG", quality=84, optimize=True, progressive=True)
        rec = {"w": w, "h": h, "srcset": srcset, "fallback": web + fname, "largest": srcset[-1][1]}
        self.cache[rel] = rec
        return rec


def img(rel: str, alt: str, sizes: str, cls: str = "", eager: bool = False) -> str:
    r = IMG.get(rel)
    srcset = ", ".join(f"{u(path)} {w}w" for w, path in r["srcset"])
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    klass = f' class="{cls}"' if cls else ""
    ratio = r["w"] / r["h"]
    return (f'<img src="{u(r["fallback"])}" srcset="{srcset}" sizes="{sizes}" width="{r["w"]}" '
            f'height="{r["h"]}" alt="{esc(alt)}" {load} decoding="async"{klass} style="--r:{ratio:.4f}">')


@functools.lru_cache(maxsize=None)
def font(name: str, size: int):
    return ImageFont.truetype(str(TOOL_FONTS / name), size)


def tracked(draw, xy, text, fnt, fill, tracking=0.0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += fnt.getlength(ch) + tracking
    return x


def wrap(text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if fnt.getlength(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def hang_on(canvas, art_path, box):
    bx, by, bw, bh = box
    with Image.open(art_path) as opened:
        art = ImageOps.exif_transpose(opened).convert("RGB")
    scale = min(bw / art.width, bh / art.height)
    aw, ah = round(art.width * scale), round(art.height * scale)
    art = art.resize((aw, ah), Image.LANCZOS)
    ax, ay = bx + (bw - aw) // 2, by + bh - ah
    shadow = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(shadow).rectangle([ax + 8, ay + 16, ax + aw + 10, ay + ah + 20], fill=120)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.paste(Image.new("RGB", canvas.size, "#3b2f24"), (0, 0), shadow)
    canvas.paste(art, (ax, ay))


def og_image(name: str, painting: dict | None) -> str:
    out = DIST / "images" / "og" / f"{name}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    IMG.written.add(out)
    W, H = 1200, 630
    ink, taupe = "#221E1A", "#655B52"
    canvas = Image.new("RGB", (W, H), "#F5F0E7")
    d = ImageDraw.Draw(canvas)
    if painting:
        hang_on(canvas, IMAGES / painting["primary_image"], (70, 70, 520, 470))
        d = ImageDraw.Draw(canvas)
        x = 660
        tracked(d, (x, 84), SITE["site"]["brand"], font("NSD-static-400.ttf", 24), ink, 4.5)
        y = 170
        tfont = font("NSD-static-italic-400.ttf", 66)
        for line in wrap(painting["title"], tfont, 470)[:3]:
            d.text((x, y), line, font=tfont, fill=ink)
            y += 78
        y += 18
        d.text((x, y), ARTIST, font=font("AlbertSans-static-450.ttf", 28), fill=ink)
        y += 48
        sfont = font("AlbertSans-static-450.ttf", 23)
        for line in wrap(painting["medium"], sfont, 460)[:2] + [dims(painting)[0] + "  ·  " + dims(painting)[1]]:
            d.text((x, y), line, font=sfont, fill=taupe)
            y += 34
    else:
        hang_on(canvas, IMAGES / BY_SLUG[SITE["home"]["hero_painting"]]["primary_image"], (760, 70, 370, 490))
        d = ImageDraw.Draw(canvas)
        mfont = font("NSD-static-400.ttf", 118)
        d.text((72, 92), "CANVAS", font=mfont, fill=ink)
        d.text((72, 212), "WOMAN", font=mfont, fill=ink)
        d.text((76, 372), SITE["artist"]["identity"], font=font("AlbertSans-static-450.ttf", 27), fill=ink)
        d.text((76, 424), SITE["home"]["tagline"], font=font("NSD-static-italic-400.ttf", 38), fill=taupe)
    d.text((72 if not painting else 660, 548), SITE["site"]["domain"], font=font("AlbertSans-static-450.ttf", 22), fill=taupe)
    canvas.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    return f"/images/og/{name}.jpg"


# ------------------------------------------------------------------ loading
def load():
    global SITE, MSG, CATS, CAT_BY_KEY, PAINTINGS, BY_SLUG, PREVIEW, ARTIST
    SITE = tomllib.loads((CONTENT / "site.toml").read_text("utf-8"))
    inventory = tomllib.loads((CONTENT / "paintings.toml").read_text("utf-8"))
    MSG = SITE["whatsapp_messages"]
    ARTIST = SITE["artist"]["name"]
    CATS = SITE.get("category", [])
    CAT_BY_KEY = {c["key"]: c for c in CATS}
    cat_slugs = {c["slug"] for c in CATS}
    errors, seen_ids, seen_slugs, paintings = [], set(), set(), []
    required = ["id", "slug", "title", "category", "width", "height", "unit", "price",
                "medium", "availability", "primary_image"]
    for c in CATS:
        if not (IMAGES / c["cover"]).is_file():
            errors.append(f"category {c['name']}: cover image not found: content/images/{c['cover']}")
    for i, p in enumerate(inventory.get("painting", []), 1):
        where = f"painting #{i} ({p.get('slug') or p.get('title') or 'untitled'})"
        missing = [k for k in required if k not in p]
        if missing:
            errors.append(f"{where}: missing {', '.join(missing)}")
            continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(p["slug"])):
            errors.append(f"{where}: slug must use lowercase letters, numbers and single hyphens")
        if p["slug"] in seen_slugs:
            errors.append(f"{where}: slug is used twice")
        if p["id"] in seen_ids:
            errors.append(f"{where}: id is used twice")
        if p["slug"] in cat_slugs or p["slug"] in RESERVED:
            errors.append(f"{where}: slug clashes with a category or reserved URL")
        if p["category"] not in CAT_BY_KEY:
            errors.append(f"{where}: category must be one of {', '.join(CAT_BY_KEY)}")
        if p["availability"] not in AVAILABILITY:
            errors.append(f"{where}: availability must be one of {', '.join(AVAILABILITY)}")
        if p["unit"] not in ("in", "cm"):
            errors.append(f"{where}: unit must be \"in\" or \"cm\"")
        if not all(isinstance(p[k], (int, float)) and p[k] > 0 for k in ("width", "height")):
            errors.append(f"{where}: width and height must be positive numbers")
        if not isinstance(p["price"], int) or p["price"] < 0:
            errors.append(f"{where}: price must be whole rupees without commas (0 = on request)")
        p.setdefault("detail_images", [])
        p.setdefault("room_images", [])
        for rel in [p["primary_image"], *p["detail_images"], *p["room_images"]]:
            if not (IMAGES / rel).is_file():
                errors.append(f"{where}: image not found: content/images/{rel}")
        seen_slugs.add(p["slug"])
        seen_ids.add(p["id"])
        p.setdefault("currency", "INR")
        p.setdefault("framing", "")
        p.setdefault("description", "")
        p.setdefault("order", 1000 + i)
        p["customizable"] = bool(p.get("customizable", False))
        p["featured"] = bool(p.get("featured", False))
        p["sample"] = bool(p.get("sample", False))
        p["cat"] = CAT_BY_KEY.get(p["category"], {"name": p["category"], "slug": p["category"]})
        p["path"] = f"/paintings/{p['slug']}/"
        p["url"] = absolute(p["path"])
        paintings.append(p)
    if SITE["home"]["hero_painting"] not in seen_slugs:
        errors.append(f"home.hero_painting '{SITE['home']['hero_painting']}' is not a painting slug")
    portrait = SITE["artist"].get("portrait")
    if portrait and not (IMAGES / portrait).is_file():
        errors.append(f"artist.portrait not found: content/images/{portrait}")
    if errors:
        raise BuildError("\n  - " + "\n  - ".join(errors))
    PAINTINGS = sorted(paintings, key=lambda p: (p["order"], p["title"]))
    BY_SLUG = {p["slug"]: p for p in PAINTINGS}
    PREVIEW = any(p["sample"] for p in PAINTINGS)


# ------------------------------------------------------------------ schema
def org_id():
    return absolute("/#organization")


def person_id():
    return absolute("/#artist")


def ld_place():
    c = SITE["contact"]
    return {"@type": "PostalAddress", "streetAddress": c["location_parts"][0], "addressLocality": c["locality"],
            "addressRegion": c["region"], "addressCountry": c["country_code"]}


def ld_org():
    c = SITE["contact"]
    return {"@type": "Organization", "@id": org_id(), "name": SITE["site"]["name"], "url": absolute("/"),
            "logo": {"@type": "ImageObject", "url": absolute("/assets/img/logo.png"), "width": 1200, "height": 240},
            "founder": {"@id": person_id()}, "sameAs": [c["instagram_url"], c["facebook_url"]],
            "address": ld_place(),
            "contactPoint": {"@type": "ContactPoint", "contactType": "sales", "telephone": "+" + c["whatsapp"],
                             "url": wa(MSG["general"])}}


def ld_person(full=False):
    c = SITE["contact"]
    node = {"@type": "Person", "@id": person_id(), "name": ARTIST, "jobTitle": "Artist",
            "url": absolute("/about/"), "worksFor": {"@id": org_id()}, "address": ld_place(),
            "knowsAbout": [cat["name"] for cat in CATS], "sameAs": [c["instagram_url"], c["facebook_url"]]}
    if SITE["artist"].get("portrait"):
        node["image"] = absolute(IMG.get(SITE["artist"]["portrait"])["fallback"])
    if full:
        node["description"] = " ".join(SITE["artist"]["bio"][:3])
    return node


def ld_website():
    return {"@type": "WebSite", "@id": absolute("/#website"), "url": absolute("/"), "name": SITE["site"]["name"],
            "inLanguage": SITE["site"]["language"], "publisher": {"@id": org_id()}}


def ld_artwork(p):
    w_unit = "INH" if p["unit"] == "in" else "CMT"
    node = {"@type": "VisualArtwork", "@id": p["url"] + "#artwork", "name": p["title"], "url": p["url"],
            "image": absolute(IMG.get(p["primary_image"])["fallback"]),
            "description": re.sub(r"\s+", " ", p["description"]).strip(),
            "creator": {"@id": person_id()}, "artform": "Painting", "artMedium": p["medium"],
            "genre": p["cat"]["name"],
            "width": {"@type": "QuantitativeValue", "value": p["width"], "unitCode": w_unit},
            "height": {"@type": "QuantitativeValue", "value": p["height"], "unitCode": w_unit},
            "identifier": p["id"]}
    schema = AVAILABILITY[p["availability"]]["schema"]
    if p["price"] and schema:
        node["offers"] = {"@type": "Offer", "price": str(p["price"]), "priceCurrency": p["currency"],
                          "availability": schema, "url": p["url"], "seller": {"@id": org_id()}}
    return node


def crumbs(items):
    """items: [(name, path_or_None)] — last item is the current page."""
    lis = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            lis.append(f'<li><a href="{u(path)}">{esc(name)}</a></li>')
    markup = f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'
    ld = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name,
         "item": absolute(path if path else items[-1][1] or "/")}
        for i, (name, path) in enumerate(items)]}
    return markup, ld


# ------------------------------------------------------------------ layout
def header(section: str, masthead: bool = False) -> str:
    c = SITE["contact"]
    links = "".join(f'<li><a href="{u(href)}"{current(section == href)}>{label}</a></li>' for label, href in NAV)
    loc = " · ".join(c["location_parts"])
    general = esc(wa(MSG["general"]))
    extra = " has-masthead" if masthead else ""
    return f"""<header class="site-header{extra}" data-header>
  <div class="site-header__bar wrap">
    <a class="wordmark" href="{u('/')}">{esc(SITE['site']['brand'])}</a>
    <nav class="site-nav" aria-label="Main"><ul>{links}</ul></nav>
    <div class="site-header__actions">
      <a class="icon-btn" href="{esc(c['instagram_url'])}" target="_blank" rel="noopener" aria-label="Canvas Woman on Instagram">{ICON_IG}</a>
      <a class="icon-btn" href="{general}" target="_blank" rel="noopener" aria-label="Message Sreeparna on WhatsApp">{ICON_WA}</a>
      <button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-menu" aria-label="Open menu" data-menu-toggle><span></span><span></span></button>
    </div>
  </div>
  <div class="site-menu" id="site-menu" hidden>
    <div class="site-menu__inner wrap">
      <nav aria-label="Menu"><ul class="site-menu__links">{links}</ul></nav>
      <div class="site-menu__foot">
        <a class="btn btn--block" href="{general}" target="_blank" rel="noopener">{ICON_WA}<span>Enquire on WhatsApp</span></a>
        <p class="site-menu__social"><a href="{esc(c['instagram_url'])}" target="_blank" rel="noopener">Instagram</a><a href="{esc(c['facebook_url'])}" target="_blank" rel="noopener">Facebook</a></p>
        <p class="muted small">{esc(loc)}<br>{esc(c['viewings'])}</p>
      </div>
    </div>
  </div>
</header>"""


def footer() -> str:
    c = SITE["contact"]
    nav = "".join(f'<li><a href="{u(href)}">{label}</a></li>' for label, href in NAV)
    cats = "".join(f'<li><a href="{u("/paintings/" + cat["slug"] + "/")}">{esc(cat["name"])}</a></li>' for cat in CATS)
    year = dt.date.today().year
    return f"""<footer class="site-footer">
  <div class="wrap site-footer__grid">
    <div class="site-footer__brand">
      <a class="wordmark" href="{u('/')}">{esc(SITE['site']['brand'])}</a>
      <p>{esc(SITE['artist']['identity'])}</p>
    </div>
    <nav class="site-footer__col" aria-labelledby="f-nav"><h2 class="site-footer__h" id="f-nav">Navigation</h2><ul>{nav}</ul></nav>
    <div class="site-footer__col"><h2 class="site-footer__h">Categories</h2><ul>{cats}</ul></div>
    <div class="site-footer__col"><h2 class="site-footer__h">Connect</h2><ul>
      <li><a href="{esc(wa(MSG['general']))}" target="_blank" rel="noopener">WhatsApp {esc(c['whatsapp_display'])}</a></li>
      <li><a href="{esc(c['instagram_url'])}" target="_blank" rel="noopener">Instagram</a></li>
      <li><a href="{esc(c['facebook_url'])}" target="_blank" rel="noopener">Facebook</a></li></ul></div>
    <div class="site-footer__col"><h2 class="site-footer__h">Location</h2>
      <address>{'<br>'.join(esc(x) for x in c['location_parts'])}</address>
      <p class="site-footer__note">{esc(c['viewings'])}</p></div>
  </div>
  <div class="wrap site-footer__base"><a href="{u('/')}">{esc(SITE['site']['domain'])}</a><span>© {year} {esc(SITE['site']['name'])}. All rights reserved.</span></div>
</footer>"""


def layout(*, path, title, description, body, section, og=None, og_alt=None, jsonld=None,
           masthead=False, body_class="", indexable=True) -> str:
    canonical = absolute(path)
    og = og or "/images/og/site.jpg"
    og_alt = og_alt or f"{SITE['site']['brand']} — {SITE['artist']['identity']}"
    robots = "noindex, follow" if (PREVIEW or not indexable) else "index, follow, max-image-preview:large"
    ld = ""
    if jsonld:
        data = json.dumps({"@context": "https://schema.org", "@graph": jsonld}, ensure_ascii=False, separators=(",", ":"))
        ld = '<script type="application/ld+json">' + data.replace("</", "<\\/") + "</script>"
    note = ('<div class="preview-note" role="note"><p>Preview — the artworks, titles and prices shown are '
            'placeholders until the real collection is added.</p></div>') if PREVIEW else ""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="{SITE['site']['language']}">
<head>
<!-- Canvas Woman · built {stamp}{' · PREVIEW (sample data)' if PREVIEW else ''} -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="{robots}">
<meta name="theme-color" content="#F5F0E7">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE['site']['name'])}">
<meta property="og:locale" content="{SITE['site']['og_locale']}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{absolute(og)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{absolute(og)}">
<link rel="icon" href="{u('/favicon.ico')}" sizes="32x32">
<link rel="icon" href="{u('/assets/img/favicon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{u('/assets/img/apple-touch-icon.png')}">
<link rel="preload" href="{u('/assets/fonts/noto-serif-display-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{u('/assets/fonts/albert-sans-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{u('/assets/css/site.css')}?v={ASSET_V['css']}">
<script>document.documentElement.classList.add('js')</script>
<script src="{u('/assets/js/site.js')}?v={ASSET_V['js']}" defer></script>
{ld}
</head>
<body class="{body_class}">
<a class="skip-link" href="#main">Skip to content</a>
{note}
{header(section, masthead)}
<main id="main" tabindex="-1">
{body}
</main>
{footer()}
</body>
</html>
"""


def write(path: str, content: str, indexable: bool = True):
    target = DIST / path.strip("/") / "index.html" if path.endswith("/") else DIST / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, "utf-8")
    if path.endswith("/"):
        PAGES.append((path, indexable))


# ------------------------------------------------------------------ components
def section_head(title: str, hid: str, sub: str = "", extra: str = "") -> str:
    sub_html = f'<p class="section-head__sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="section-head"><h2 id="{hid}">{esc(title)}</h2>{sub_html}{extra}</div>'


def sample_tag(p, text="Sample listing") -> str:
    return f'<span class="tag-sample">{text}</span>' if p["sample"] else ""


def art_card(p, sizes=S_CARD) -> str:
    cat = p["cat"]
    status = p["availability"]
    return f"""<li class="card" data-category="{cat['slug']}">
  <a class="card__link" href="{u(p['path'])}">
    <span class="card__wall">{img(p['primary_image'], alt_primary(p), sizes, cls='hang')}</span>
    <span class="card__label">
      <span class="art-title card__title">{esc(p['title'])}</span>
      <span class="card__meta">{esc(cat['name'])}<span class="dot" aria-hidden="true"></span>{esc(dims(p)[0])}</span>
      <span class="card__price card__price--{status}">{esc(price_short(p))}</span>
      {sample_tag(p, 'Sample')}
    </span>
  </a>
</li>"""


def dim_line(x0, y0, x1, y1, cls="sd-dim"):
    tick = 1.6
    if y0 == y1:
        ends = (f'<line x1="{x0 - tick}" y1="{y0 + tick}" x2="{x0 + tick}" y2="{y0 - tick}"/>'
                f'<line x1="{x1 - tick}" y1="{y1 + tick}" x2="{x1 + tick}" y2="{y1 - tick}"/>')
    else:
        ends = (f'<line x1="{x0 - tick}" y1="{y0 + tick}" x2="{x0 + tick}" y2="{y0 - tick}"/>'
                f'<line x1="{x1 - tick}" y1="{y1 + tick}" x2="{x1 + tick}" y2="{y1 - tick}"/>')
    return f'<g class="{cls}"><line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}"/>{ends}</g>'


def sofa(cx, floor, w=84):
    x0, x1 = cx - w / 2, cx + w / 2
    return (f'<g class="sd-furniture">'
            f'<rect x="{x0 + 7}" y="{floor - 32}" width="{w - 14}" height="18" rx="3"/>'
            f'<rect x="{x0 + 5}" y="{floor - 17}" width="{w - 10}" height="12" rx="2"/>'
            f'<rect x="{x0}" y="{floor - 25}" width="8" height="21" rx="3"/>'
            f'<rect x="{x1 - 8}" y="{floor - 25}" width="8" height="21" rx="3"/>'
            f'<line x1="{x0 + 5}" y1="{floor - 4}" x2="{x0 + 5}" y2="{floor}"/>'
            f'<line x1="{x1 - 5}" y1="{floor - 4}" x2="{x1 - 5}" y2="{floor}"/></g>')


def sideboard(cx, floor, w=72):
    x0 = cx - w / 2
    return (f'<g class="sd-furniture">'
            f'<rect x="{x0}" y="{floor - 30}" width="{w}" height="24"/>'
            f'<line x1="{x0 + w / 3}" y1="{floor - 29}" x2="{x0 + w / 3}" y2="{floor - 7}"/>'
            f'<line x1="{x0 + 2 * w / 3}" y1="{floor - 29}" x2="{x0 + 2 * w / 3}" y2="{floor - 7}"/>'
            f'<line x1="{x0 + 4}" y1="{floor - 6}" x2="{x0 + 4}" y2="{floor}"/>'
            f'<line x1="{x0 + w - 4}" y1="{floor - 6}" x2="{x0 + w - 4}" y2="{floor}"/></g>')


def pct(v, total):
    return f"{v / total * 100:.3f}%"


def scale_figure(p) -> str:
    w_in, h_in = inches(p)
    vw = max(150.0, w_in * 1.9 + 20)
    top = 20.0
    floor = top + h_in + 10 + 32
    vh = floor + 14
    cx = vw * 0.42
    x0, x1, y0, y1 = cx - w_in / 2, cx + w_in / 2, top, top + h_in
    dy, dx = y0 - 8, x1 + 8
    r = IMG.get(p["primary_image"])
    svg = (f'<svg viewBox="0 0 {vw:.2f} {vh:.2f}" aria-hidden="true" focusable="false">'
           f'<line class="sd-floor" x1="0" y1="{floor}" x2="{vw:.2f}" y2="{floor}"/>'
           f'{sofa(cx, floor)}'
           f'<g class="sd-ext"><line x1="{x0}" y1="{y0 - 2}" x2="{x0}" y2="{dy - 3}"/><line x1="{x1}" y1="{y0 - 2}" x2="{x1}" y2="{dy - 3}"/>'
           f'<line x1="{x1 + 2}" y1="{y0}" x2="{dx + 3}" y2="{y0}"/><line x1="{x1 + 2}" y1="{y1}" x2="{dx + 3}" y2="{y1}"/></g>'
           f'{dim_line(x0, dy, x1, dy)}{dim_line(dx, y0, dx, y1)}</svg>')
    style = f"left:{pct(x0, vw)};top:{pct(y0, vh)};width:{pct(w_in, vw)};height:{pct(h_in, vh)}"
    small = u(r["srcset"][1][1] if len(r["srcset"]) > 1 else r["srcset"][0][1])
    return f"""<figure class="scale-drawing" style="aspect-ratio:{vw:.2f}/{vh:.2f}">
  {svg}
  <img class="sd-art" src="{small}" alt="" width="{r['w']}" height="{r['h']}" loading="lazy" decoding="async" style="{style}">
  <span class="sd-label" style="left:{pct(cx, vw)};top:{pct(dy, vh)}">{esc(length(w_in))}</span>
  <span class="sd-label sd-label--side" style="left:{pct(dx, vw)};top:{pct((y0 + y1) / 2, vh)}">{num(round(h_in))} in<br>({round(h_in * 2.54)} cm)</span>
  <figcaption class="sd-caption">{esc(p['title'])} above a three-seat sofa, 84 in (213 cm) wide, hung 10 in (25 cm) above it.</figcaption>
</figure>"""


def commission_drawing(theme="light") -> str:
    vw, vh = 160.0, 112.0
    floor = 100.0
    cx = 72.0
    aw, ah = 52.0, 38.0
    x0, x1 = cx - aw / 2, cx + aw / 2
    y1 = floor - 30 - 12
    y0 = y1 - ah
    dy, dx = y0 - 9, x1 + 9
    svg = (f'<svg viewBox="0 0 {vw} {vh}" aria-hidden="true" focusable="false">'
           f'<line class="sd-floor" x1="0" y1="{floor}" x2="{vw}" y2="{floor}"/>'
           f'{sideboard(cx, floor)}'
           f'<rect class="sd-empty" x="{x0}" y="{y0}" width="{aw}" height="{ah}"/>'
           f'<g class="sd-ext"><line x1="{x0}" y1="{y0 - 2}" x2="{x0}" y2="{dy - 3}"/><line x1="{x1}" y1="{y0 - 2}" x2="{x1}" y2="{dy - 3}"/>'
           f'<line x1="{x1 + 2}" y1="{y0}" x2="{dx + 3}" y2="{y0}"/><line x1="{x1 + 2}" y1="{y1}" x2="{dx + 3}" y2="{y1}"/></g>'
           f'{dim_line(x0, dy, x1, dy)}{dim_line(dx, y0, dx, y1)}</svg>')
    return f"""<div class="scale-drawing scale-drawing--{theme}" style="aspect-ratio:{vw}/{vh}" aria-hidden="true">
  {svg}
  <span class="sd-label" style="left:{pct(cx, vw)};top:{pct(dy, vh)}">Your width</span>
  <span class="sd-label sd-label--side" style="left:{pct(dx, vw)};top:{pct((y0 + y1) / 2, vh)}">Your<br>height</span>
  <span class="sd-empty-label" style="left:{pct(cx, vw)};top:{pct((y0 + y1) / 2, vh)}">A painting<br>for this wall</span>
</div>"""


def portrait_block(cls="") -> str:
    a = SITE["artist"]
    if a.get("portrait"):
        return f'<figure class="portrait {cls}">{img(a["portrait"], a["portrait_alt"], S_WIDE)}</figure>'
    return (f'<figure class="portrait portrait--placeholder {cls}"><div class="portrait__mat">'
            f'<p>Portrait of {esc(ARTIST)}</p><p class="muted small">Photograph to be added</p></div></figure>')


def reach_block(hid="reach-title") -> str:
    items = "".join(f"<li>{esc(c)}</li>" for c in SITE["countries"])
    return f"""<section class="section reach" aria-labelledby="{hid}">
  <div class="wrap reach__inner">
    <h2 id="{hid}" class="reach__title">From Delhi to walls around the world</h2>
    <ul class="reach__list">{items}</ul>
    <p class="reach__note">Paintings by {esc(ARTIST)} have found homes across {len(SITE['countries'])} countries.</p>
  </div>
</section>"""


def commission_band(hid="cc-title", drawing=True) -> str:
    return f"""<section class="commission-band" aria-labelledby="{hid}">
  <div class="wrap commission-band__grid">
    <div class="commission-band__text">
      <h2 id="{hid}">Some spaces call for something that doesn’t yet exist.</h2>
      <p>Share your wall, its measurements and the palette of the room. {esc(SITE['artist']['first_name'])} will create an original painting that belongs there.</p>
      <div class="actions">
        <a class="btn btn--light" href="{esc(wa(MSG['commission']))}" target="_blank" rel="noopener">{ICON_WA}<span>Start a commission on WhatsApp</span></a>
        <a class="link link--light" href="{u('/commissions/')}">How commissions work</a>
      </div>
    </div>
    {commission_drawing('dark') if drawing else ''}
  </div>
</section>"""


# ------------------------------------------------------------------ pages
def page_home():
    s, a = SITE, SITE["artist"]
    hero = BY_SLUG[s["home"]["hero_painting"]]
    featured = [p for p in PAINTINGS if p["featured"]][:4] or PAINTINGS[:4]
    cols = " ".join(f"{num(round(inches(p)[0], 2))}fr" for p in featured)
    salon = "".join(
        f"""<a class="salon__item" href="{u(p['path'])}" style="--w:{num(round(inches(p)[0], 2))};--h:{num(round(inches(p)[1], 2))}">
  <span class="salon__art" data-reveal>{img(p['primary_image'], alt_primary(p), S_SALON, cls='hang')}</span>
  <span class="salon__label"><span class="art-title">{esc(p['title'])}</span><span class="salon__meta">{esc(dims(p)[0])}<span class="dot" aria-hidden="true"></span>{esc(price_short(p))}</span></span>
</a>""" for p in featured)
    counts = {c["key"]: sum(1 for p in PAINTINGS if p["category"] == c["key"]) for c in CATS}
    cat_items = "".join(
        f"""<a class="cat cat--{i % 4 + 1}" href="{u('/paintings/' + c['slug'] + '/')}">
  <span class="cat__media">{img(c['cover'], '', S_WIDE)}</span>
  <span class="cat__row"><span class="cat__name">{esc(c['name'])}</span><span class="cat__count">{counts[c['key']]} {'work' if counts[c['key']] == 1 else 'works'}</span></span>
  <span class="cat__blurb">{esc(c['blurb'])}</span>
</a>""" for i, c in enumerate(CATS))
    room_p = next((p for p in PAINTINGS if p["room_images"] and p["slug"] != hero["slug"]), None)
    room_fig = ""
    if room_p:
        room_fig = f"""<figure class="custom__media" data-reveal>
      {img(room_p['room_images'][0], room_p['title'] + ' shown in an interior, for a sense of scale', S_WIDE)}
      <figcaption>Interior visualisation — <i>{esc(room_p['title'])}</i>, {esc(dims(room_p)[0])}, shown for scale.</figcaption>
    </figure>"""
    tiles = "".join(
        f"""<li><a href="{esc(s['contact']['instagram_url'])}" target="_blank" rel="noopener">{img(p['primary_image'], p['title'] + ' — view Canvas Woman on Instagram', S_TILE)}</a></li>"""
        for p in PAINTINGS[:6])
    bio = a["bio"]
    body = f"""
<section class="hero" aria-labelledby="hero-title">
  <div class="wrap hero__grid">
    <h1 class="masthead" id="hero-title" data-masthead><span>CANVAS</span> <span>WOMAN</span></h1>
    <p class="hero__identity">Original &amp; Commissioned Art<br>by {esc(ARTIST)}</p>
    <figure class="hero__work">
      <a class="hero__hang" href="{u(hero['path'])}">{img(hero['primary_image'], alt_primary(hero), S_HERO, cls='hang', eager=True)}</a>
      <figcaption class="wall-label"><span class="art-title">{esc(hero['title'])}</span><span>{esc(hero['medium'])}</span><span>{esc(dims(hero)[0])}</span></figcaption>
    </figure>
    <p class="hero__tagline">{esc(s['home']['tagline'])}</p>
    <div class="hero__actions actions">
      <a class="btn" href="{u('/paintings/')}">Explore the collection</a>
      <a class="btn btn--ghost" href="{u('/commissions/')}">Commission an artwork</a>
    </div>
  </div>
</section>

<section class="section featured" aria-labelledby="featured-title">
  <div class="wrap">
    {section_head('Featured works', 'featured-title', 'A selection from the collection, hung together at relative scale.')}
    <div class="salon" style="--cols:{cols}">{salon}</div>
    <p class="section-foot"><a class="link" href="{u('/paintings/')}">View all paintings</a></p>
  </div>
</section>

<section class="section section--plaster categories" aria-labelledby="cat-title">
  <div class="wrap">
    {section_head('The collection', 'cat-title', 'Four directions within ' + ARTIST + '’s practice.')}
    <div class="cats">{cat_items}</div>
  </div>
</section>

<section class="section custom" aria-labelledby="custom-title">
  <div class="wrap custom__grid">
    {room_fig}
    <div class="custom__text">
      <h2 id="custom-title">Made for your walls</h2>
      <p class="lead">Paintings from the collection can be adapted in size, colour palette and framing — or a new work can be commissioned around your room, its light and its proportions.</p>
      <ul class="custom__list">
        <li><span class="custom__k">Custom sizes</span><span>Scaled to a particular wall, alcove or piece of furniture.</span></li>
        <li><span class="custom__k">Colour palettes</span><span>Matched to the room — its walls, textiles, flooring and art.</span></li>
        <li><span class="custom__k">Adapted works</span><span>A painting from the collection, reinterpreted for your space.</span></li>
        <li><span class="custom__k">Framing</span><span>Floating, wooden, gold or coloured frames, or a clean gallery edge.</span></li>
      </ul>
      <div class="actions"><a class="btn" href="{u('/commissions/')}">Commission an artwork</a><a class="link" href="{u('/paintings/')}">Browse paintings to customise</a></div>
    </div>
  </div>
</section>

<section class="section section--plaster quote-band" aria-labelledby="quote-title">
  <h2 class="vh" id="quote-title">The art</h2>
  <figure class="wrap quote">
    <blockquote><p>“{esc(s['art']['quote'])}”</p></blockquote>
    <figcaption>{esc(ARTIST)}</figcaption>
    <p><a class="link" href="{u('/the-art/')}">About the art</a></p>
  </figure>
</section>

<section class="section about-teaser" aria-labelledby="about-title">
  <div class="wrap about-teaser__grid">
    {portrait_block()}
    <div class="about-teaser__text">
      <h2 id="about-title">{esc(ARTIST)}</h2>
      <p class="lead">{esc(bio[1] if len(bio) > 1 else bio[0])}</p>
      <p>{esc(bio[2] if len(bio) > 2 else '')}</p>
      <p><a class="link" href="{u('/about/')}">Read her story</a></p>
    </div>
  </div>
</section>

{reach_block()}

{commission_band()}

<section class="section insta" aria-labelledby="insta-title">
  <div class="wrap">
    <div class="insta__head"><h2 id="insta-title">On Instagram</h2><a class="link" href="{esc(s['contact']['instagram_url'])}" target="_blank" rel="noopener">@{esc(s['contact']['instagram_handle'])}</a></div>
    <ul class="insta__grid">{tiles}</ul>
  </div>
</section>"""
    jsonld = [ld_website(), ld_org(), ld_person()]
    write("/", layout(path="/", title=s["home"]["seo_title"], description=s["home"]["seo_description"],
                      body=body, section="/", jsonld=jsonld, masthead=True, body_class="page-home"))


def page_collection(cat=None):
    path = "/paintings/" + (cat["slug"] + "/" if cat else "")
    all_intro = (f"Original paintings by {ARTIST} across abstract, texture, landscape and contemporary work. "
                 "Enquire about any piece directly on WhatsApp.")
    brand = SITE["site"]["name"]

    def info(c):
        if c is None:
            return {"heading": "Paintings", "intro": all_intro, "title": f"Paintings by {ARTIST} | {brand}",
                    "path": "/paintings/", "key": "all"}
        return {"heading": c["name"], "intro": c["intro"], "title": f"{c['seo_title']} | {brand}",
                "path": "/paintings/" + c["slug"] + "/", "key": c["slug"]}

    me = info(cat)
    total = len(PAINTINGS)
    filters = []
    for c in [None, *CATS]:
        f = info(c)
        count = total if c is None else sum(1 for p in PAINTINGS if p["category"] == c["key"])
        label = "All" if c is None else c["name"]
        filters.append(
            f'<li><a href="{u(f["path"])}" data-filter="{f["key"]}" data-heading="{esc(f["heading"])}" '
            f'data-intro="{esc(f["intro"])}" data-title="{esc(f["title"])}"{current(f["key"] == me["key"])}>'
            f'{esc(label)}<span class="filters__count">{count}</span></a></li>')
    cards = []
    shown = 0
    for p in PAINTINGS:
        card = art_card(p)
        if cat and p["category"] != cat["key"]:
            card = card.replace('<li class="card"', '<li hidden class="card"', 1)
        else:
            shown += 1
        cards.append(card)
    crumb_items = [("Home", "/"), ("Paintings", "/paintings/")] + ([(cat["name"], path)] if cat else [])
    crumb_html, crumb_ld = crumbs(crumb_items)
    empty_hidden = " hidden" if shown else ""
    body = f"""
<div class="wrap page-head">
  {crumb_html}
  <h1 data-collection-title>{esc(me['heading'])}</h1>
  <p class="lead page-head__lead" data-collection-intro>{esc(me['intro'])}</p>
</div>
<div class="wrap collection">
  <nav class="filters" aria-label="Filter paintings by category" data-filters><ul>{''.join(filters)}</ul></nav>
  <p class="vh" role="status" aria-live="polite" data-filter-status></p>
  <ul class="card-grid" data-grid>{''.join(cards)}</ul>
  <div class="empty" data-empty{empty_hidden}><p>New work in this category is on its way.</p><p><a class="link" href="{u('/commissions/')}">Commission a painting in this style</a></p></div>
</div>
<section class="section section--plaster prompt" aria-labelledby="prompt-title">
  <div class="wrap prompt__inner">
    <h2 id="prompt-title">Not quite the right size or palette?</h2>
    <p class="lead">Ask about adapting a painting for your space, or commission a new work created around it.</p>
    <div class="actions"><a class="btn" href="{u('/commissions/')}">Commission an artwork</a><a class="btn btn--ghost" href="{esc(wa(MSG['general']))}" target="_blank" rel="noopener">{ICON_WA}<span>Ask on WhatsApp</span></a></div>
  </div>
</section>"""
    item_list = {"@type": "CollectionPage", "@id": absolute(path) + "#page", "url": absolute(path), "name": me["heading"],
                 "isPartOf": {"@id": absolute("/#website")},
                 "mainEntity": {"@type": "ItemList", "itemListElement": [
                     {"@type": "ListItem", "position": i + 1, "url": p["url"], "name": p["title"]}
                     for i, p in enumerate(x for x in PAINTINGS if not cat or x["category"] == cat["key"])]}}
    desc = me["intro"] if cat else clip(all_intro + " Custom sizes and commissions available.")
    write(path, layout(path=path, title=me["title"], description=clip(desc), body=body, section="/paintings/",
                       jsonld=[crumb_ld, item_list], body_class="page-collection"))


def cta_block(p) -> str:
    a = p["availability"]
    if a == "sold":
        primary = (msg("sold", p), "Commission something similar")
        secondary = None
    elif a == "commission":
        primary = (msg("commission_work", p), "Discuss a similar commission")
        secondary = None
    elif a == "made-to-order":
        primary = (msg("customise", p), "Customise &amp; enquire on WhatsApp")
        secondary = (msg("made_to_order", p), "Ask about ordering this painting")
    else:
        primary = (msg("customise", p), "Customise &amp; enquire on WhatsApp") if p["customizable"] else (msg("available", p), "Enquire on WhatsApp")
        secondary = (msg("available", p), "Ask if the original is available")
    out = [f'<a class="btn btn--block" href="{esc(wa(primary[0]))}" target="_blank" rel="noopener" data-float-hide>{ICON_WA}<span>{primary[1]}</span></a>']
    if secondary:
        out.append(f'<a class="btn btn--ghost btn--block" href="{esc(wa(secondary[0]))}" target="_blank" rel="noopener">{secondary[1]}</a>')
    return "".join(out)


def price_rows(p) -> str:
    a = p["availability"]
    if a == "sold":
        original = "Sold"
    elif a == "commission":
        original = "Private commission"
    else:
        original = inr(p["price"]) if p["price"] else "Price on Request"
    first = "Made to Order" if a == "made-to-order" else "Original"
    rows = [f'<div><dt>{first}</dt><dd>{esc(original)}</dd></div>']
    if p["customizable"] or a in ("sold", "commission"):
        rows.append('<div><dt>Custom Sizes &amp; Variations</dt><dd>Price on Request</dd></div>')
    return f'<dl class="price-list">{"".join(rows)}</dl>'


def customise_section(p) -> str:
    c = SITE["customise"]
    r = IMG.get(p["primary_image"])
    thumb = u(r["srcset"][0][1])
    frames = "".join(
        f"""<li class="frame frame--{key}"><span class="frame__box"><span class="frame__art" style="--r:{r['w'] / r['h']:.4f}"><img src="{thumb}" alt="" width="{r['w']}" height="{r['h']}" loading="lazy" decoding="async"></span></span><span class="frame__name">{esc(label)}</span></li>"""
        for key, label in FRAMES)
    options = [("Size &amp; Proportion", c["size"]), ("Colour Palette", c["palette"]),
               ("Artwork Details", c["details"]), ("Framing", c["framing"])]
    opts = "".join(f'<li><h3 class="option__title">{t}</h3><p>{esc(d)}</p></li>' for t, d in options)
    original = inr(p["price"]) if (p["price"] and p["availability"] in ("available", "made-to-order")) else AVAILABILITY[p["availability"]]["label"] if p["availability"] != "available" else "Price on Request"
    return f"""<section class="section section--plaster customise" id="make-it-your-own" aria-labelledby="custom-title">
  <div class="wrap">
    <div class="customise__head">
      <h2 id="custom-title">Make it your own</h2>
      <p class="lead">{esc(c['intro'])}</p>
    </div>
    <ul class="options">{opts}</ul>
    <div class="frames">
      <h3 class="frames__title">Framing options</h3>
      <ul class="frames__list">{frames}</ul>
    </div>
    <div class="customise__foot">
      <p class="price-lines"><span>Original — {esc(original)}</span><span>Custom Sizes &amp; Variations — Price on Request</span></p>
      <a class="btn" href="{esc(wa(msg('customise', p)))}" target="_blank" rel="noopener" data-float-hide>{ICON_WA}<span>Customise &amp; enquire on WhatsApp</span></a>
    </div>
  </div>
</section>"""


def page_painting(p):
    cat = p["cat"]
    brand = SITE["site"]["name"]
    primary, other = dims(p)
    figures = []
    items = [(p["primary_image"], "art")] + [(x, "detail") for x in p["detail_images"]] + [(x, "room") for x in p["room_images"]]
    for idx, (rel, kind) in enumerate(items):
        if kind == "art":
            alt, cap = alt_primary(p), "The painting"
        elif kind == "detail":
            alt, cap = f"Close-up detail of {p['title']}, showing the painted surface", "Detail"
        else:
            alt, cap = f"{p['title']} shown in an interior, for a sense of scale", "Interior visualisation, for scale"
        big = u(IMG.get(rel)["largest"])
        figures.append(f"""<figure class="gallery__item gallery__item--{kind}">
  <a class="gallery__zoom" href="{big}" data-zoom="{big}" data-caption="{esc(p['title'] + ' — ' + cap)}" data-alt="{esc(alt)}">{img(rel, alt, S_GALLERY, eager=(idx == 0))}<span class="vh"> — enlarge image</span></a>
  <figcaption>{esc(cap)}</figcaption>
</figure>""")
    controls = ""
    if len(items) > 1:
        controls = (f'<div class="gallery__controls"><button type="button" class="icon-btn" data-prev aria-label="Previous image">{ICON_PREV}</button>'
                    f'<span class="gallery__count" data-count>1 / {len(items)}</span>'
                    f'<button type="button" class="icon-btn" data-next aria-label="Next image">{ICON_NEXT}</button></div>')
    status = AVAILABILITY[p["availability"]]["label"]
    cust = "Yes — size, palette, details and framing" if p["customizable"] else "Offered as it is"
    framing = f'<div><dt>Framing</dt><dd>{esc(p["framing"])}</dd></div>' if p["framing"] else ""
    related = [x for x in PAINTINGS if x["category"] == p["category"] and x is not p]
    related += [x for x in PAINTINGS if x["category"] != p["category"]]
    related_cards = "".join(art_card(x) for x in related[:3])
    crumb_html, crumb_ld = crumbs([("Home", "/"), ("Paintings", "/paintings/"),
                                   (cat["name"], "/paintings/" + cat["slug"] + "/"), (p["title"], p["path"])])
    customise = customise_section(p) if p["customizable"] else f"""<section class="section section--plaster prompt" aria-labelledby="custom-title">
  <div class="wrap prompt__inner"><h2 id="custom-title">Looking for something similar?</h2>
  <p class="lead">This work is offered as it is. A new painting in a similar spirit can be commissioned for your space.</p>
  <div class="actions"><a class="btn" href="{esc(wa(msg('commission_work' if p['availability'] == 'commission' else 'sold', p)))}" target="_blank" rel="noopener" data-float-hide>{ICON_WA}<span>Discuss a commission</span></a></div></div>
</section>"""
    body = f"""
<div class="wrap painting">
  {crumb_html}
  <div class="painting__grid">
    <div class="gallery" data-gallery>
      <div class="gallery__track" data-track tabindex="0" role="region" aria-label="Images of {esc(p['title'])}">{''.join(figures)}</div>
      {controls}
    </div>
    <div class="painting__info">
      <div class="painting__sticky">
        {sample_tag(p)}
        <h1 class="art-title painting__title">{esc(p['title'])}</h1>
        <p class="painting__artist">{esc(ARTIST)}</p>
        <p class="status status--{p['availability']}"><span class="status__dot" aria-hidden="true"></span>{esc(status)}</p>
        {price_rows(p)}
        <div class="painting__actions">{cta_block(p)}</div>
        <p class="painting__hint">Opens WhatsApp with a message about this painting, addressed to {esc(SITE['artist']['first_name'])}.</p>
        <dl class="specs">
          <div><dt>Original size</dt><dd>{esc(primary)} <span class="muted">({esc(other)})</span></dd></div>
          <div><dt>Medium</dt><dd>{esc(p['medium'])}</dd></div>
          <div><dt>Category</dt><dd><a href="{u('/paintings/' + cat['slug'] + '/')}">{esc(cat['name'])}</a></dd></div>
          {framing}
          <div><dt>Customisable</dt><dd>{cust}</dd></div>
          <div><dt>Reference</dt><dd>{esc(p['id'])}</dd></div>
        </dl>
        <div class="painting__desc">{paragraphs(p['description'])}</div>
      </div>
    </div>
  </div>
</div>

<section class="section scale" aria-labelledby="scale-title">
  <div class="wrap scale__grid">
    <div class="scale__text">
      <h2 id="scale-title">Seen at scale</h2>
      <p>{esc(p['title'])} measures {esc(primary)} ({esc(other)}). The drawing shows it above a three-seat sofa so you can picture it on your own wall.</p>
      <p class="muted">Need it larger, smaller or in a different proportion? Sizes can be adapted.</p>
    </div>
    {scale_figure(p)}
  </div>
</section>

{customise}

<section class="section related" aria-labelledby="related-title">
  <div class="wrap">
    {section_head('More from the collection', 'related-title')}
    <ul class="card-grid">{related_cards}</ul>
  </div>
</section>

<a class="float-enquire" href="{esc(wa(msg('customise' if p['customizable'] and p['availability'] in ('available', 'made-to-order') else 'available', p)))}" target="_blank" rel="noopener" data-float>{ICON_WA}<span>Enquire on WhatsApp</span></a>

<dialog class="lightbox" data-lightbox aria-label="Image viewer">
  <button type="button" class="lightbox__close" data-lb-close>Close</button>
  <figure class="lightbox__figure"><img alt="" data-lb-img><figcaption data-lb-caption></figcaption></figure>
  <button type="button" class="icon-btn lightbox__nav lightbox__nav--prev" data-lb-prev aria-label="Previous image">{ICON_PREV}</button>
  <button type="button" class="icon-btn lightbox__nav lightbox__nav--next" data-lb-next aria-label="Next image">{ICON_NEXT}</button>
</dialog>"""
    noun = NOUNS.get(p["category"], "painting")
    title = f"{p['title']} — {noun[0].upper() + noun[1:]} by {ARTIST} | {brand}"
    price_phrase = {"sold": "Original sold", "commission": "Private commission"}.get(
        p["availability"], ("Original " + inr(p["price"])) if p["price"] else "Price on request")
    desc = clip(f"{p['title']} by {ARTIST}: {p['medium'].lower()}, {primary} ({other}). {price_phrase}. "
                f"Enquire on WhatsApp.")
    og = og_image("painting-" + p["slug"], p)
    write(p["path"], layout(path=p["path"], title=title, description=desc, body=body, section="/paintings/",
                            og=og, og_alt=f"{p['title']} by {ARTIST}", jsonld=[crumb_ld, ld_artwork(p)],
                            body_class="page-painting", indexable=not p["sample"]),
          indexable=not p["sample"])


def page_commissions():
    steps = [
        ("Share Your Space &amp; Vision", "Send photographs of the wall, its measurements and any colours, pieces or references you love. A rough idea is enough to begin."),
        ("Discuss Size, Palette &amp; Direction", "Together you settle the scale, the palette and the overall direction — leaving room for the artist’s own interpretation."),
        ("Artwork Creation", f"{esc(SITE['artist']['first_name'])} paints the work as a one-of-a-kind original for your space."),
        ("Framing &amp; Finishing", "The finished painting is prepared for hanging, with framing chosen to suit the room if you would like it framed."),
        ("Delivery", "Packing and delivery are arranged for your location once the painting is complete."),
    ]
    step_html = "".join(f'<li class="step"><span class="step__n" aria-hidden="true">{i:02d}</span><h3 class="step__title">{t}</h3><p>{d}</p></li>'
                        for i, (t, d) in enumerate(steps, 1))
    counts = {c["key"]: sum(1 for p in PAINTINGS if p["category"] == c["key"]) for c in CATS}
    styles = "".join(
        f"""<a class="cat cat--small" href="{u('/paintings/' + c['slug'] + '/')}"><span class="cat__media">{img(c['cover'], '', S_CARD)}</span><span class="cat__row"><span class="cat__name">{esc(c['name'])}</span><span class="cat__count">{counts[c['key']]} in the collection</span></span><span class="cat__blurb">{esc(c['blurb'])}</span></a>"""
        for c in CATS)
    crumb_html, crumb_ld = crumbs([("Home", "/"), ("Commissions", "/commissions/")])
    body = f"""
<section class="wrap page-hero">
  <div class="page-hero__text">
    {crumb_html}
    <h1>Art created for your space</h1>
    <p class="page-hero__sub">Some spaces call for something that doesn’t yet exist.</p>
    <p class="lead">A commission begins with the room itself — its proportions, its light, its colours and the people who live with it. From there, {esc(SITE['artist']['first_name'])} creates an original painting that belongs to that space, while remaining unmistakably her own work.</p>
    <div class="actions"><a class="btn" href="{esc(wa(MSG['commission']))}" target="_blank" rel="noopener">{ICON_WA}<span>Start a commission on WhatsApp</span></a></div>
  </div>
  {commission_drawing('light')}
</section>

<section class="section section--plaster process" aria-labelledby="process-title">
  <div class="wrap">
    {section_head('How a commission comes together', 'process-title', 'Five stages, from the first photograph of your wall to the day the painting arrives.')}
    <ol class="steps">{step_html}</ol>
  </div>
</section>

<section class="section share" aria-labelledby="share-title">
  <div class="wrap share__grid">
    <div>
      <h2 id="share-title">What to share</h2>
      <ul class="share__list">
        <li>Photographs of the wall and the room around it</li>
        <li>The wall’s width and height, and the size of any furniture below</li>
        <li>Colours, materials or pieces the painting should sit with</li>
        <li>Paintings from the collection you are drawn to</li>
        <li>Where the painting is going — city and country</li>
      </ul>
    </div>
    <div class="share__note">
      <h2 class="share__h">A collaboration with a point of view</h2>
      <p class="lead">You bring the space, the scale and the feeling you want. The composition, the brushwork and the finished painting remain {esc(SITE['artist']['first_name'])}’s.</p>
    </div>
  </div>
</section>

<section class="section section--plaster styles" aria-labelledby="styles-title">
  <div class="wrap">
    {section_head('Commission in any direction', 'styles-title', 'Browse the collection for a sense of each style, then describe what you have in mind.')}
    <div class="cats cats--four">{styles}</div>
  </div>
</section>

{commission_band('cc-title-2', drawing=False)}"""
    write("/commissions/", layout(path="/commissions/", title=f"Commission a Custom Painting | {SITE['site']['name']}",
                                  description=clip(f"Commission an original painting by {ARTIST}, created for your wall, its proportions and its palette. Share your space on WhatsApp to begin."),
                                  body=body, section="/commissions/", jsonld=[crumb_ld], body_class="page-commissions"))


def page_about():
    a = SITE["artist"]
    bio = "".join(f"<p>{esc(x)}</p>" for x in a["bio"])
    crumb_html, crumb_ld = crumbs([("Home", "/"), ("About", "/about/")])
    body = f"""
<div class="wrap page-head">
  {crumb_html}
  <h1>{esc(ARTIST)}</h1>
  <p class="lead page-head__lead">Artist · {esc(SITE['contact']['locality'])}, Delhi NCR</p>
</div>
<section class="wrap about" aria-label="Biography">
  {portrait_block('about__portrait')}
  <div class="about__bio prose">{bio}</div>
</section>
{reach_block('about-reach')}
<section class="section section--plaster prompt" aria-labelledby="about-next">
  <div class="wrap prompt__inner">
    <h2 id="about-next">See the work</h2>
    <p class="lead">Browse the collection, or begin a painting created for your own space.</p>
    <div class="actions"><a class="btn" href="{u('/paintings/')}">Explore the collection</a><a class="btn btn--ghost" href="{u('/commissions/')}">Commission an artwork</a></div>
  </div>
</section>"""
    write("/about/", layout(path="/about/", title=f"About {ARTIST} | {SITE['site']['name']}",
                            description=clip(f"{ARTIST} is the artist behind Canvas Woman, creating abstract, textured, landscape and contemporary paintings and custom commissions from Gurugram, Delhi NCR."),
                            body=body, section="/about/", jsonld=[crumb_ld, ld_person(full=True)], body_class="page-about"))


def page_art():
    art = SITE["art"]
    plates = []
    for p in ([x for x in PAINTINGS if x["featured"]][:4] or PAINTINGS[:4]):
        plates.append(f"""<figure class="plate">
  <a class="plate__wall" href="{u(p['path'])}" data-reveal>{img(p['primary_image'], alt_primary(p), S_WIDE, cls='hang')}</a>
  <figcaption class="wall-label"><span class="art-title">{esc(p['title'])}</span><span>{esc(p['medium'])}</span><span>{esc(dims(p)[0])}</span></figcaption>
</figure>""")
    phil = "".join(f"<p>{esc(x)}</p>" for x in art["philosophy"])
    counts = {c["key"]: sum(1 for p in PAINTINGS if p["category"] == c["key"]) for c in CATS}
    ways = "".join(
        f"""<li><a href="{u('/paintings/' + c['slug'] + '/')}"><span class="ways__name">{esc(c['name'])}</span><span class="ways__blurb">{esc(c['intro'])}</span><span class="ways__count">{counts[c['key']]} {'work' if counts[c['key']] == 1 else 'works'}</span></a></li>"""
        for c in CATS)
    crumb_html, crumb_ld = crumbs([("Home", "/"), ("The Art", "/the-art/")])
    body = f"""
<div class="wrap page-head">
  {crumb_html}
  <h1>The Art</h1>
</div>
<section class="wrap art-quote" aria-label="In the artist’s words">
  <figure class="quote quote--large">
    <blockquote><p>“{esc(art['quote'])}”</p></blockquote>
    <figcaption>{esc(ARTIST)}</figcaption>
  </figure>
</section>
<section class="section art-essay" aria-label="About the work">
  <div class="wrap art-essay__grid">
    <div class="prose art-essay__text">{phil}</div>
    <div class="plates">{''.join(plates)}</div>
  </div>
</section>
<section class="section section--plaster ways" aria-labelledby="ways-title">
  <div class="wrap">
    {section_head('Four ways of working', 'ways-title')}
    <ul class="ways__list">{ways}</ul>
  </div>
</section>
{commission_band('cc-title-art')}"""
    write("/the-art/", layout(path="/the-art/", title=f"The Art of {ARTIST} | {SITE['site']['name']}",
                              description=clip(f"“{art['quote']}” — {ARTIST} on painting, space and the people who live with art."),
                              body=body, section="/the-art/", jsonld=[crumb_ld], body_class="page-art"))


def page_contact():
    c = SITE["contact"]
    crumb_html, crumb_ld = crumbs([("Home", "/"), ("Contact", "/contact/")])
    body = f"""
<div class="wrap page-head">
  {crumb_html}
  <h1>Contact</h1>
  <p class="lead page-head__lead">For paintings, customisation, commissions or a private viewing, message {esc(SITE['artist']['first_name'])} directly on WhatsApp.</p>
</div>
<section class="wrap contact" aria-label="Contact options">
  <div class="contact__main">
    <a class="btn btn--large" href="{esc(wa(MSG['general']))}" target="_blank" rel="noopener">{ICON_WA}<span>Message on WhatsApp</span></a>
    <p class="contact__number">{esc(c['whatsapp_display'])}</p>
    <form class="compose" action="https://wa.me/{c['whatsapp']}" method="get" target="_blank" data-wa-form data-greeting="Hi {esc(SITE['artist']['first_name'])},">
      <h2 class="compose__title">Write your message here first</h2>
      <p class="muted small">Nothing is sent from this page. Your message opens in WhatsApp, ready to send.</p>
      <div class="field"><label for="c-name">Your name</label><input id="c-name" name="name" type="text" autocomplete="name"></div>
      <div class="field"><label for="c-interest">I’m interested in</label>
        <select id="c-interest" name="interest">
          <option value="a painting from the collection">A painting from the collection</option>
          <option value="customising a painting">Customising a painting</option>
          <option value="commissioning an artwork">Commissioning an artwork</option>
          <option value="arranging a private viewing">Arranging a private viewing</option>
          <option value="">Something else</option>
        </select></div>
      <div class="field"><label for="c-text">Message <span class="muted">(optional)</span></label><textarea id="c-text" name="text" rows="4"></textarea></div>
      <button class="btn" type="submit">{ICON_WA}<span>Continue in WhatsApp</span></button>
    </form>
  </div>
  <div class="contact__aside">
    <div class="contact__block"><h2 class="contact__h">Location</h2><address>{'<br>'.join(esc(x) for x in c['location_parts'])}</address><p>{esc(c['viewings'])}</p></div>
    <div class="contact__block"><h2 class="contact__h">Follow</h2><p><a class="link" href="{esc(c['instagram_url'])}" target="_blank" rel="noopener">Instagram @{esc(c['instagram_handle'])}</a></p><p><a class="link" href="{esc(c['facebook_url'])}" target="_blank" rel="noopener">Facebook</a></p></div>
  </div>
</section>"""
    write("/contact/", layout(path="/contact/", title=f"Contact | {SITE['site']['name']} — Gurugram, Delhi NCR",
                              description=clip(f"Contact {ARTIST} on WhatsApp about paintings, customisation, commissions or a private viewing. Golf Course Road, Gurugram, Delhi NCR."),
                              body=body, section="/contact/", jsonld=[crumb_ld, ld_org()], body_class="page-contact"))


def page_404():
    body = f"""
<div class="wrap notfound">
  <p class="muted">Page not found</p>
  <h1>This page isn’t here.</h1>
  <p class="lead">The link may be mistyped, or the page may have moved.</p>
  <div class="actions"><a class="btn" href="{u('/paintings/')}">View the paintings</a><a class="btn btn--ghost" href="{u('/')}">Go to the home page</a></div>
</div>"""
    content = layout(path="/404.html", title=f"Page not found | {SITE['site']['name']}",
                     description="This page could not be found.", body=body, section="", indexable=False)
    content = content.replace(f'<link rel="canonical" href="{absolute("/404.html")}">\n', "")
    write("/404.html", content)


def extras():
    today = dt.date.today().isoformat()
    urls = "".join(f"  <url><loc>{absolute(path)}</loc><lastmod>{today}</lastmod></url>\n" for path, ok in PAGES if ok)
    (DIST / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n', "utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {absolute('/sitemap.xml')}\n", "utf-8")
    if not BASE:
        (DIST / "CNAME").write_text(SITE["site"]["domain"] + "\n", "utf-8")
    (DIST / ".nojekyll").write_text("", "utf-8")


def copy_assets():
    assets = DIST / "assets"
    for sub in ("css", "js", "fonts"):
        shutil.copytree(SRC / sub, assets / sub, dirs_exist_ok=True)
    shutil.copytree(SRC / "img", assets / "img", dirs_exist_ok=True)
    shutil.copy2(SRC / "img" / "favicon.ico", DIST / "favicon.ico")
    for key, rel in (("css", "css/site.css"), ("js", "js/site.js")):
        ASSET_V[key] = hashlib.sha1((SRC / rel).read_bytes()).hexdigest()[:10]


def clean():
    DIST.mkdir(exist_ok=True)
    for item in DIST.iterdir():
        if item.name == "images":
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()


def prune_images():
    root = DIST / "images"
    for f in root.rglob("*"):
        if f.is_file() and f not in IMG.written:
            f.unlink()
    for d in sorted((x for x in root.rglob("*") if x.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()


def main():
    global BASE, IMG
    ap = argparse.ArgumentParser(description="Build the Canvas Woman site into ./dist")
    ap.add_argument("--base-path", default="", help="URL prefix for a project-page preview, e.g. /canvaswoman")
    ap.add_argument("--serve", action="store_true", help="preview dist/ at http://localhost:8000 after building")
    args = ap.parse_args()
    BASE = "/" + args.base_path.strip("/") if args.base_path.strip("/") else ""
    try:
        load()
    except BuildError as e:
        sys.exit(f"Build stopped — please fix content:{e}")
    IMG = Images()
    clean()
    copy_assets()
    og_image("site", None)
    page_home()
    page_collection()
    for c in CATS:
        page_collection(c)
    for p in PAINTINGS:
        page_painting(p)
    page_commissions()
    page_about()
    page_art()
    page_contact()
    page_404()
    extras()
    prune_images()
    samples = sum(1 for p in PAINTINGS if p["sample"])
    print(f"Built {len(PAGES)} pages, {len(PAINTINGS)} paintings, {len(IMG.written)} image files → {DIST}")
    if samples:
        print(f"PREVIEW MODE: {samples} sample paintings in content/paintings.toml — preview notice shown, all pages noindex.")
    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("Previewing at http://localhost:8000  (Ctrl+C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
