# CANVAS WOMAN — canvaswoman.com

Original & Commissioned Art by Sreeparna Poddar. A static website generated from two content files. No cart, no checkout, no database — every enquiry opens WhatsApp with a pre-written message.

## Folder map

```
build.py                 site generator (Python 3.11+, Pillow)
requirements.txt
content/
  paintings.toml         ← THE PAINTING INVENTORY (currently 12 SAMPLE entries)
  site.toml              ← contact details, WhatsApp messages, biography, page copy, categories
  images/
    paintings/<slug>/    ← one folder per painting: primary.jpg, detail-1.jpg, room-1.jpg …
    artist/              ← portrait of Sreeparna (optional)
src/
  css/site.css           design system and all page styles
  js/site.js             menu, filters, gallery, lightbox, floating enquiry, contact composer
  fonts/                 Noto Serif Display + Albert Sans (self-hosted, OFL licences included)
  img/                   favicon, touch icon, logo used in structured data
tools/
  fonts/                 static fonts used to draw the social-share images
  placeholder-art/       the scripts that generated the sample paintings (delete once real work is in)
.github/workflows/deploy.yml   optional automatic build + GitHub Pages deploy
dist/                    ← the finished website. This is what gets published.
```

## Build and preview

```bash
pip install -r requirements.txt
python3 build.py            # writes dist/
python3 build.py --serve    # builds, then preview at http://localhost:8000
```

The build checks the inventory before writing anything (missing fields, duplicate slugs, unknown categories, missing image files) and stops with a plain list of what to fix.

## Adding a real painting

1. Make a folder `content/images/paintings/<slug>/` — the slug is the URL, e.g. `ocean-memory` → `canvaswoman.com/paintings/ocean-memory/`.
2. Put the photographs in it:
   - `primary.jpg` — the whole painting, straight on, cropped exactly to the canvas edge. Long side 2000–3000 px.
   - `detail-1.jpg`, `detail-2.jpg` … (optional) — close-ups of texture and brushwork.
   - `room-1.jpg` … (optional) — the painting in an interior. These are captioned as interior images on the site, separately from the artwork photos.
3. Add an entry to `content/paintings.toml` (copy an existing block; every field is explained at the top of that file):

```toml
[[painting]]
id = "CW-001"
slug = "ocean-memory"
title = "Ocean Memory"
category = "abstract"            # abstract | texture | landscape | pop
width = 36
height = 48
unit = "in"
price = 95000                    # rupees, no commas; 0 = Price on Request
currency = "INR"
medium = "Acrylic on canvas"
availability = "available"       # available | sold | commission | made-to-order
framing = "Gallery-wrapped canvas, ready to hang."
customizable = true
featured = true
order = 1
primary_image = "paintings/ocean-memory/primary.jpg"
detail_images = ["paintings/ocean-memory/detail-1.jpg"]
room_images = []
description = """
First paragraph.

Second paragraph."""
```

4. Run `python3 build.py`. The painting page, its card in the gallery and category filters, the WhatsApp messages (title + page link), the structured data, the social-share image and the sitemap entry are all generated from that entry. Images are resized to WebP (480/960/1600 px) plus a JPEG fallback automatically.

## Removing the sample data

The 12 entries in `paintings.toml` are placeholders (`sample = true`) with procedurally generated images. They are not Sreeparna Poddar's work. While any entry still has `sample = true`, the build runs in **preview mode**: a thin notice appears at the top of every page, sample listings are tagged "Sample", every page carries `noindex`, and sample paintings are left out of the sitemap.

To go live: delete the sample entries and their image folders (`azure-reverie`, `saffron-hour`, `quiet-monsoon`, `ivory-tide`, `sandstone-lines`, `terrain-in-gold`, `himalayan-morning`, `fields-after-rain`, `riverside-dusk`, `marigold-pop`, `city-signals`, `pink-monsoon`), add the real paintings, update the four category `cover` images and `home.hero_painting` in `site.toml` to point at real work, then rebuild. Preview mode switches off by itself.

## Copy to confirm before launch

In `content/site.toml`, lines marked `# CONFIRM` were written from the facts in the brief but are not the approved wording: the home page SEO title and description, the six-paragraph biography, the two philosophy paragraphs on The Art page, and the "Make it your own" text. Paste the verbatim copy over them.

The portrait: put a photo in `content/images/artist/` and set `portrait = "artist/<file>.jpg"`. Until then a labelled placeholder panel is shown.

## Publishing on GitHub Pages

**Upload (simplest):** upload the *contents* of `dist/` to the root of the Pages repository. `CNAME` (canvaswoman.com) and `.nojekyll` are already included. All URLs are clean (`/about/`, `/paintings/azure-reverie/`) — no `.html` anywhere.

**Automatic:** push this whole project to a repository, set Settings → Pages → Source to "GitHub Actions", and `.github/workflows/deploy.yml` builds and publishes on every push to `main`.

**Preview on a project URL** (e.g. `norvixhq.github.io/canvaswoman/`): `python3 build.py --base-path /canvaswoman` and upload `dist/`. Canonical URLs still point at canvaswoman.com. Rebuild without `--base-path` for the real domain.
