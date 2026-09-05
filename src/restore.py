"""Geometry and lighting restoration passes for page scans.

Three passes, run before the tonal cleanup in cleanup.py:

1. fix_orientation — detects page content that is sideways (rotated a
   quarter turn inside a portrait capture) by comparing how strongly
   text lines register in the horizontal vs vertical direction, and
   rotates it upright. Conservative: only acts on a strong signal, and
   the caller logs every rotation for review.
2. detect_skew / rotate_fill — finds the small tilt of a page (within
   +/- max_skew degrees) by maximizing the sharpness of the horizontal
   projection profile, then rotates to square, filling corners with the
   page's own border color.
3. flatten_lighting — removes glare and uneven illumination by
   estimating the paper brightness field (morphological closing wipes
   out dark ink/photos, leaving the lighting) and dividing it out.
"""

import numpy as np
from PIL import Image


# ---------- shared helpers ----------

def _line_score(a: np.ndarray) -> float:
    """How strongly horizontal text lines / layout rows register.

    Rows of text create sharp light-dark alternation down the page, so
    the derivative of the row-mean profile has high variance when the
    content is upright.
    """
    prof = a.mean(axis=1)
    return float(np.var(np.diff(prof)))


def _small_gray(img: Image.Image, max_side: int = 600) -> np.ndarray:
    g = img.convert("L")
    g.thumbnail((max_side, max_side))
    return np.asarray(g, dtype=np.float32)


# ---------- 1. sideways content ----------

def fix_orientation(img: Image.Image, ratio: float = 1.6) -> tuple[Image.Image, int]:
    """Return (image, degrees rotated). Detects content lying on its side."""
    a = _small_gray(img)
    upright = _line_score(a)
    sideways = _line_score(a.T)
    if sideways > upright * ratio:
        # content is on its side; pick the quarter turn that reads best
        ccw = _line_score(np.rot90(a, 1))
        cw = _line_score(np.rot90(a, 3))
        deg = 90 if ccw >= cw else -90
        return img.rotate(deg, expand=True), deg
    return img, 0


# ---------- 2. small skew ----------

def detect_skew(img: Image.Image, max_angle: float = 3.0,
                step: float = 0.25) -> float:
    """Angle (degrees, CCW-positive) that best squares the page content."""
    g = Image.fromarray(_small_gray(img).astype(np.uint8))
    h, w = g.height, g.width
    y0, y1 = int(0.08 * h), int(0.92 * h)
    x0, x1 = int(0.08 * w), int(0.92 * w)

    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-max_angle, max_angle + step / 2, step):
        r = g.rotate(float(angle), resample=Image.BILINEAR, fillcolor=255)
        score = _line_score(np.asarray(r, dtype=np.float32)[y0:y1, x0:x1])
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def rotate_fill(img: Image.Image, angle: float) -> Image.Image:
    """Rotate without expanding, filling corners with the border color."""
    a = np.asarray(img)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    if border.ndim == 2:  # RGB
        fill = tuple(int(np.median(border[:, c])) for c in range(border.shape[1]))
    else:
        fill = int(np.median(border))
    return img.rotate(angle, resample=Image.BICUBIC, fillcolor=fill)


# ---------- 3. glare / uneven lighting ----------

def flatten_lighting(img_l: Image.Image, grid: tuple[int, int] = (16, 12),
                     max_darken: float = 0.62, max_brighten: float = 1.18) -> Image.Image:
    """Even out page illumination (glare hot spots, shadowed corners).

    The lighting field is sampled from *paper* pixels only — the
    brightest fraction of each grid cell — so photos and ink never get
    mistaken for lighting and flattened away. Cells that contain no
    paper (full-bleed photo areas) inherit the page-wide level, i.e. no
    correction. The multiplicative correction is clamped so it can dim
    glare firmly but only brighten shadows gently.
    """
    from skimage.filters import gaussian

    g = np.asarray(img_l, dtype=np.float32)
    h, w = g.shape
    gh, gw = grid
    paper_thresh = np.percentile(g, 70)

    cells = np.full((gh, gw), np.nan, dtype=np.float32)
    for i in range(gh):
        for j in range(gw):
            cell = g[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw]
            paper = cell[cell >= paper_thresh]
            if paper.size >= 0.02 * cell.size:
                cells[i, j] = np.median(paper)

    if np.isnan(cells).all():
        return img_l
    target = float(np.nanmedian(cells))
    cells = np.where(np.isnan(cells), target, cells)
    cells = gaussian(cells, sigma=1.0, preserve_range=True)

    bg = np.asarray(
        Image.fromarray(cells).resize((w, h), Image.BILINEAR), dtype=np.float32)
    corr = np.clip(target / np.maximum(bg, 20.0), max_darken, max_brighten)
    return Image.fromarray(np.clip(g * corr, 0, 255).astype(np.uint8))
