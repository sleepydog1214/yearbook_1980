"""Extract individual photos + captions from the 1980 yearbook scans.

For each page (in book order, reusing the video pipeline's cleaned-page
cache — deskewed, glare-flattened, contrast-fixed):

  1. detect the photos on the page (detect.py)
  2. crop each one, colorize it individually, upscale 2x (enhance.py)
  3. OCR the caption next to it and the page's full text (ocr.py)
  4. record everything in output/site/catalog.json

Output layout (ready for a static web app):
  output/site/photos/p012_1.jpg     extracted, enhanced photos
  output/site/pages/p012.jpg        full page images for a page browser
  output/site/debug/p012.jpg        detection overlay (--debug only)
  output/site/catalog.json          the index: every photo's file, page,
                                    source scan, bbox, confidence, caption;
                                    every page's file and OCR text

Usage:
  python site_prep/extract.py              # whole book
  python site_prep/extract.py --limit 5    # first 5 pages
  python site_prep/extract.py --pages 40-60 --debug
  python site_prep/extract.py --no-colorize   # keep photos black & white
"""

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Settings          # noqa: E402  (src/)
from cleanup import get_cleaned      # noqa: E402  (src/)
from pages import find_scans         # noqa: E402  (src/)
from detect import detect_photos     # noqa: E402
from enhance import enhance_photo    # noqa: E402
from ocr import caption_for, is_text_block, page_text  # noqa: E402

PAGE_JPG_HEIGHT = 1600


def parse_args():
    p = argparse.ArgumentParser(description="Extract yearbook photos for the web site.")
    p.add_argument("--limit", type=int, default=None, help="only first N pages")
    p.add_argument("--pages", type=str, default=None, help='page range, e.g. "40-60"')
    p.add_argument("--no-colorize", action="store_true")
    p.add_argument("--debug", action="store_true", help="save detection overlays")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    site = settings.paths["output"] / "site"
    for sub in ("photos", "pages"):
        (site / sub).mkdir(parents=True, exist_ok=True)
    if args.debug:
        (site / "debug").mkdir(exist_ok=True)

    scans = find_scans(settings.paths["scans"])
    first, last = 1, len(scans)
    if args.pages:
        a, _, b = args.pages.partition("-")
        first, last = int(a), int(b or a)
    if args.limit:
        last = min(last, first + args.limit - 1)

    catalog = {"book": "Clarion 1980", "pages": [], "photos": []}
    catalog_path = site / "catalog.json"
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        done = {p["page"] for p in catalog["pages"]}
    else:
        done = set()

    t0 = time.time()
    for page_no in range(first, last + 1):
        if page_no in done:
            continue
        scan = scans[page_no - 1]
        page = get_cleaned(scan, settings,
                           keep_color=page_no in settings.keep_color_pages)
        dets = [d for d in detect_photos(page)
                if not is_text_block(page, d["bbox"])]
        print(f"[{page_no}/{last}] {scan.name}: {len(dets)} photos")

        page_file = f"pages/p{page_no:03d}.jpg"
        scale = PAGE_JPG_HEIGHT / page.height
        page.resize((round(page.width * scale), PAGE_JPG_HEIGHT),
                    Image.LANCZOS).save(site / page_file, quality=88)

        if args.debug:
            overlay = page.convert("RGB").copy()
            draw = ImageDraw.Draw(overlay)
            for d in dets:
                draw.rectangle(d["bbox"], outline=(255, 0, 0), width=8)
            overlay.thumbnail((1200, 1200))
            overlay.save(site / "debug" / f"p{page_no:03d}.jpg", quality=85)

        for i, d in enumerate(dets, 1):
            crop = page.crop(d["bbox"])
            photo = enhance_photo(crop, colorize=not args.no_colorize)
            photo_file = f"photos/p{page_no:03d}_{i}.jpg"
            photo.save(site / photo_file, quality=90)
            catalog["photos"].append({
                "id": f"p{page_no:03d}_{i}",
                "file": photo_file,
                "page": page_no,
                "scan": scan.name,
                "bbox": list(d["bbox"]),
                "confidence": d["confidence"],
                "width": photo.width,
                "height": photo.height,
                "caption": caption_for(page, d["bbox"],
                                       [o["bbox"] for o in dets if o is not d]),
            })

        catalog["pages"].append({
            "page": page_no,
            "file": page_file,
            "scan": scan.name,
            "photo_count": len(dets),
            "text": page_text(page),
        })
        # checkpoint every page so an interrupted run resumes where it left off
        catalog["pages"].sort(key=lambda p: p["page"])
        catalog["photos"].sort(key=lambda p: (p["page"], p["id"]))
        catalog_path.write_text(json.dumps(catalog, indent=1), encoding="utf-8")

    n = len(catalog["photos"])
    print(f"\nDone: {n} photos across {len(catalog['pages'])} pages "
          f"in {time.time() - t0:.0f}s -> {catalog_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
