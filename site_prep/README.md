# Site Prep — Yearbook Photo Extraction

Turns the 1980 yearbook page scans into structured material for an
interactive web site: every photo cut out, enhanced, colorized, and
upscaled, with its caption and location recorded in a catalog file.

## Usage

Run from the project folder (`1980 yearbook`):

```
python site_prep/extract.py              # whole book
python site_prep/extract.py --limit 5    # first 5 pages
python site_prep/extract.py --pages 40-60
python site_prep/extract.py --debug      # also save detection overlays
python site_prep/extract.py --no-colorize
```

Progress is checkpointed into the catalog after every page, so an
interrupted run resumes where it stopped (delete `catalog.json` for a
fresh start).

Needs the video pipeline's dependencies (`../src`) plus Tesseract OCR
(`winget install UB-Mannheim.TesseractOCR`) and `pip install pytesseract`.

## Output (`output/site/`)

| Path | Contents |
|---|---|
| `catalog.json` | The index. `photos[]`: id, file, page, source scan, bbox on the page, detection confidence, size, caption. `pages[]`: page image, scan name, photo count, full OCR text for search. |
| `photos/p012_1.jpg` | Extracted photos: cleaned, individually AI-colorized, 2x upscaled |
| `pages/p012.jpg` | Full cleaned pages (1600px tall) for a page-browser view |
| `debug/p012.jpg` | Detection overlays (`--debug` only) |

## How it works

| File | Role |
|---|---|
| `extract.py` | Main loop: page -> detect -> crop -> enhance -> caption -> catalog |
| `detect.py` | Photo detection: blur dissolves text, photos survive as blobs; components filtered by size/fill and merged; permissive on purpose — semantic text rejection happens in ocr.is_text_block |
| `ocr.py` | Tesseract captions (strip below/beside each photo, gated by paper brightness and word confidence), page text, and text-block rejection |
| `enhance.py` | Per-photo autocontrast, individual AI colorization (better than page-level: the model sees just this photo), 2x Lanczos upscale + unsharp. Swap in a neural super-resolution model here later. |

## The web site

`webapp/index.html` is the app (vanilla JS single page, no build tools);
`build_site.py` assembles the deployable site:

```
python site_prep/extract.py       # if not already done
python site_prep/build_site.py    # thumbs + enriched catalog + copy app
```

`build_site.py` generates gallery thumbnails (`thumbs/`, 420px), adds
`bbox_rel` (each photo's position on its page, 0..1) and `spreads`
(open-book page pairs) to the catalog, and copies in `index.html`.
After it runs, **`output/site/` is the whole site**:

- **Book view**: open-book spreads, arrow keys / buttons / slider;
  photos on the page are clickable hotspots
- **Photos view**: masonry gallery of all extracted photos with captions
- **Search**: filters by caption and full-page OCR text
- **Lightbox**: full-size photo, caption, link back to its page
- Shareable URLs: `#page/12`, `#photo/p012_1`

Preview locally:

```
python -m http.server 8123 --directory "output/site"
```

Deploy: push `output/site/` to a Git repo (or use Render's static-site
manual deploy) and point a Render Static Site at it — no build command,
publish directory = the folder itself. If the ~450 MB of images is too
heavy for the repo, move `photos/`, `pages/`, `thumbs/` to object
storage (Cloudflare R2 / Backblaze B2 free tiers) and prefix those
paths in `catalog.json` with the bucket's public base URL.
