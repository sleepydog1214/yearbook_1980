"""Caption and page-text OCR via Tesseract.

Captions on these pages usually sit directly below a photo (sometimes
numbered "(1) ..."), occasionally beside it. caption_for() OCRs the
strip under a photo box and falls back to the strip to its right.
page_text() OCRs the whole page for the site's search index.
"""

import os
import shutil

import pytesseract
from PIL import Image

# winget's Tesseract lands here and isn't on PATH for this session
_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if shutil.which("tesseract") is None and os.path.exists(_DEFAULT):
    pytesseract.pytesseract.tesseract_cmd = _DEFAULT

CAPTION_STRIP_FRAC = 0.09   # how far below/beside a photo to look


def _clean(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) > 2 and any(c.isalpha() for c in ln)]
    return " ".join(lines).strip()


def _ocr(img: Image.Image) -> str:
    if img.width < 20 or img.height < 12:
        return ""
    import numpy as np
    # captions sit on paper; skip strips that are mostly photo
    if np.median(np.asarray(img.convert("L"))) < 165:
        return ""
    # gate on Tesseract's own word confidences: real text scores high,
    # OCR of photo texture and edge fragments scores low
    data = pytesseract.image_to_data(img, config="--psm 6",
                                     output_type=pytesseract.Output.DICT)
    good = [w for w, c in zip(data["text"], data["conf"])
            if int(c) > 60 and sum(ch.isalpha() for ch in w) >= 2]
    if len(good) < 4:
        return ""
    return _clean(pytesseract.image_to_string(img, config="--psm 6"))


def _clip_against(strip: tuple[int, int, int, int],
                  boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    """Shrink a below-strip so it stops at the next photo underneath."""
    x0, y0, x1, y1 = strip
    for bx0, by0, bx1, by1 in boxes:
        if by0 >= y0 and min(x1, bx1) - max(x0, bx0) > 0.3 * (x1 - x0):
            y1 = min(y1, by0)
    return x0, y0, x1, y1


def caption_for(page: Image.Image, bbox: tuple[int, int, int, int],
                others: list[tuple[int, int, int, int]] = ()) -> str:
    """OCR the paper strip below the photo; fall back to the right side."""
    x0, y0, x1, y1 = bbox
    strip_h = int(page.height * CAPTION_STRIP_FRAC)

    strip = _clip_against((x0, min(y1, page.height),
                           x1, min(y1 + strip_h, page.height)), others)
    if strip[3] - strip[1] >= 12:
        text = _ocr(page.crop(strip))
        if text:
            return text

    beside = (min(x1, page.width), y0,
              min(x1 + int(page.width * CAPTION_STRIP_FRAC), page.width), y1)
    return _ocr(page.crop(beside))


def page_text(page: Image.Image) -> str:
    """Full-page OCR for the search index."""
    return _clean(pytesseract.image_to_string(page))


def is_text_block(page: Image.Image, bbox: tuple[int, int, int, int]) -> bool:
    """True if a detected region is a text block, not a photo.

    A text block reads as many high-confidence words AND sits on paper.
    The paper test keeps photo-backed graphics (e.g. a score table over
    a photo) classified as photos.
    """
    import numpy as np

    crop = page.crop(bbox).convert("L")
    crop.thumbnail((700, 700))
    a = np.asarray(crop)
    paperish = float((a > np.percentile(a, 75) - 20).mean())
    if paperish < 0.45:
        return False

    data = pytesseract.image_to_data(crop, config="--psm 6",
                                     output_type=pytesseract.Output.DICT)
    words = [w for w, c in zip(data["text"], data["conf"])
             if int(c) > 70 and sum(ch.isalpha() for ch in w) >= 3]
    return len(words) >= 6
