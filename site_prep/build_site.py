"""Assemble the deployable web site in output/site/.

Takes the extraction results (catalog.json, photos/, pages/) and:
  1. generates gallery thumbnails (thumbs/, 420px wide) so the grid
     loads fast — full images load only in the lightbox
  2. enriches the catalog for the front-end:
       - each photo gets bbox_rel (position on its page as 0..1
         fractions, for clickable hotspots in the page browser)
       - a spreads[] list groups pages into open-book pairs (an L scan
         with its R partner), matching how the book reads
  3. copies the app (webapp/index.html) in

After this, output/site/ is self-contained: serve it locally with
`python -m http.server` or deploy it to any static host (Render).

Usage:  python site_prep/build_site.py
"""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from config import Settings  # noqa: E402

THUMB_WIDTH = 420


BOOK_DIR = "1980"   # this book's subfolder in the multi-book site


def main() -> int:
    settings = Settings()
    site = settings.paths["output"] / "site" / BOOK_DIR
    catalog_path = site / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    # --- page dimensions (for relative bboxes) ---
    dims = {}
    for entry in catalog["pages"]:
        cleaned = settings.paths["cleaned"] / (Path(entry["scan"]).stem + ".png")
        if not cleaned.exists():  # keep-color pages (the cover)
            cleaned = settings.paths["cleaned"] / (Path(entry["scan"]).stem + "_color.png")
        with Image.open(cleaned) as im:
            dims[entry["page"]] = im.size

    # --- enrich photos: relative bbox + thumbnail ---
    thumbs = site / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for photo in catalog["photos"]:
        w, h = dims[photo["page"]]
        x0, y0, x1, y1 = photo["bbox"]
        photo["bbox_rel"] = [round(x0 / w, 4), round(y0 / h, 4),
                             round(x1 / w, 4), round(y1 / h, 4)]
        thumb_file = f"thumbs/{photo['id']}.jpg"
        if not (site / thumb_file).exists():
            with Image.open(site / photo["file"]) as im:
                im.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 3))
                im.convert("RGB").save(site / thumb_file, quality=80)
        photo["thumb"] = thumb_file

    # --- spreads: cover/singles alone, L+R pairs together ---
    spreads = []
    pages = sorted(catalog["pages"], key=lambda p: p["page"])
    i = 0
    while i < len(pages):
        stem = Path(pages[i]["scan"]).stem
        if (stem.endswith("L") and i + 1 < len(pages)
                and Path(pages[i + 1]["scan"]).stem == stem[:-1] + "R"):
            spreads.append([pages[i]["page"], pages[i + 1]["page"]])
            i += 2
        else:
            spreads.append([pages[i]["page"]])
            i += 1
    catalog["spreads"] = spreads

    catalog_path.write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    shutil.copy(Path(__file__).parent / "webapp" / "index.html", site / "index.html")

    n_thumbs = len(list(thumbs.glob("*.jpg")))
    print(f"site built: {len(catalog['photos'])} photos, {n_thumbs} thumbs, "
          f"{len(spreads)} spreads -> {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
