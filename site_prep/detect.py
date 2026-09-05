"""Find the individual photos on a yearbook page.

Photos are solid mid-to-dark rectangular blocks on white paper, while
text is made of thin strokes. Blurring the ink map dissolves text into
faint gray but leaves photos as strong blobs, which connected-component
analysis then picks out. Coordinates are returned in full-resolution
page space.

Each detection is a dict: {"bbox": (left, top, right, bottom),
"confidence": float 0..1}. Confidence reflects how rectangular and
solid the region is — low-confidence detections are kept but flagged
so they can be reviewed.
"""

import numpy as np
from PIL import Image

WORK_HEIGHT = 800          # detection runs at this page height
MIN_AREA_FRAC = 0.012      # ignore blobs smaller than 1.2% of the page
MIN_SIDE_FRAC = 0.07       # ...or thinner than 7% of the page side
EDGE_TRIM_FRAC = 0.02      # ignore the outermost 2% (capture edge smears)
BBOX_PAD_FRAC = 0.006      # pad final boxes slightly


def detect_photos(page: Image.Image) -> list[dict]:
    from skimage.filters import gaussian
    from skimage.measure import label, regionprops

    full_w, full_h = page.size
    scale = WORK_HEIGHT / full_h
    small = page.convert("L").resize((round(full_w * scale), WORK_HEIGHT),
                                     Image.BILINEAR)
    g = np.asarray(small, dtype=np.float32)
    h, w = g.shape

    # ink map: how far below paper brightness each pixel sits
    paper = np.percentile(g, 85)
    ink = np.clip(paper - g, 0, None)

    # kill the capture's smeared edges
    ty, tx = int(h * EDGE_TRIM_FRAC), int(w * EDGE_TRIM_FRAC)
    ink[:ty], ink[-ty:], ink[:, :tx], ink[:, -tx:] = 0, 0, 0, 0

    # text dissolves under a wide blur; photo blocks survive
    blurred = gaussian(ink, sigma=4, preserve_range=True)
    mask = blurred > 32
    # sever thin bridges (gutters between stacked portraits)
    from skimage.morphology import opening
    mask = opening(mask, np.ones((9, 9), dtype=bool))

    labels = label(mask)
    detections = []
    for r in regionprops(labels):
        y0, x0, y1, x1 = r.bbox
        bw, bh = x1 - x0, y1 - y0
        if r.area < MIN_AREA_FRAC * h * w:
            continue
        if bw < MIN_SIDE_FRAC * w or bh < MIN_SIDE_FRAC * h:
            continue
        fill = r.area / (bw * bh)
        # low bar: high-key photos (white dresses, uniforms) leave big
        # holes in the ink blob; text rejection is handled by OCR later
        if fill < 0.28:
            continue
        interior = g[y0:y1, x0:x1]
        # photos (halftones) are full of midtone grays; text blocks and
        # solid graphics are bimodal — near-paper or near-black. Measure
        # against the region's own paper level so dim corners don't read
        # as midtones.
        # minimal tonal screen — must not reject high-contrast photos
        # (flash shots are nearly as bimodal as text); the real text
        # rejection is the OCR-based is_text_block() check in the caller
        midtone_frac = float(((interior < paper - 25) &
                              (interior > paper - 110)).mean())
        if midtone_frac < 0.05:
            continue
        # solid, rectangular, and meaningfully dark inside -> confident
        darkness = float(np.clip((paper - np.median(interior)) / 60.0, 0, 1))
        confidence = round(min(1.0, 0.5 * fill + 0.3 * darkness + 0.2), 2)

        pad_x, pad_y = int(w * BBOX_PAD_FRAC), int(h * BBOX_PAD_FRAC)
        box = (max(0, x0 - pad_x), max(0, y0 - pad_y),
               min(w, x1 + pad_x), min(h, y1 + pad_y))
        detections.append({"bbox": box, "confidence": confidence})

    detections = _merge_overlaps(detections)
    # back to full-resolution coordinates
    for d in detections:
        x0, y0, x1, y1 = d["bbox"]
        d["bbox"] = (round(x0 / scale), round(y0 / scale),
                     round(x1 / scale), round(y1 / scale))
    detections.sort(key=lambda d: (d["bbox"][1], d["bbox"][0]))  # reading order
    return detections


def _merge_overlaps(dets: list[dict]) -> list[dict]:
    """Merge boxes that overlap substantially (photo split into blobs)."""
    merged = True
    while merged and len(dets) > 1:
        merged = False
        out = []
        used = [False] * len(dets)
        for i, a in enumerate(dets):
            if used[i]:
                continue
            ax0, ay0, ax1, ay1 = a["bbox"]
            for j in range(i + 1, len(dets)):
                if used[j]:
                    continue
                bx0, by0, bx1, by1 = dets[j]["bbox"]
                ix = max(0, min(ax1, bx1) - max(ax0, bx0))
                iy = max(0, min(ay1, by1) - max(ay0, by0))
                inter = ix * iy
                smaller = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
                # one photo split into stacked parts: strong horizontal
                # alignment with any vertical overlap
                aligned = ix > 0.6 * min(ax1 - ax0, bx1 - bx0) and iy > 0
                if inter > 0.4 * smaller or aligned:
                    ax0, ay0 = min(ax0, bx0), min(ay0, by0)
                    ax1, ay1 = max(ax1, bx1), max(ay1, by1)
                    used[j] = True
                    merged = True
            out.append({"bbox": (ax0, ay0, ax1, ay1),
                        "confidence": a["confidence"]})
            used[i] = True
        dets = out
    return dets
