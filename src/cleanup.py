"""Clean up raw scans and compose them into video-sized frames.

Cleanup steps (per page):
  1. Convert to grayscale — the book is B&W, so this removes any color
     cast from the camera/scanner in one step.
  2. Auto-contrast with a small histogram clip — evens out lighting
     differences between captures and makes the paper read as white.
  3. Mild unsharp mask to crisp up halftone photos and text.

Cleaned pages are cached as PNGs in output/cleaned/ so re-renders with
different video settings don't redo the image work. Delete that folder
(or pass --reclean) to force a redo.

compose_frame() letterboxes a cleaned page onto the video canvas; a
future Ken Burns / zoom effect would replace that function.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from config import Settings


def clean_page(src: Path, settings: Settings, keep_color: bool = False,
               rotate: int = 0) -> Image.Image:
    from restore import detect_skew, flatten_lighting, rotate_fill

    img = Image.open(src)
    img = ImageOps.exif_transpose(img)

    if rotate:
        print(f"    rotated {src.name} by {rotate:+d} deg (--rotate)")
        img = img.rotate(rotate, expand=True)

    if settings.deskew:
        angle = detect_skew(img, max_angle=settings.max_skew)
        if abs(angle) >= 0.3:
            print(f"    deskewed {src.name} by {angle:+.2f} deg")
            img = rotate_fill(img, angle)

    if settings.grayscale and not keep_color:
        img = img.convert("L")
        if settings.flatten_lighting:
            img = flatten_lighting(img)
        img = ImageOps.autocontrast(img, cutoff=settings.autocontrast_cutoff)
    else:
        # page scanned in real color (e.g. the green cover): keep its hues
        img = img.convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=settings.autocontrast_cutoff,
                                    preserve_tone=True)

    if settings.sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))

    return img.convert("RGB")


def cleaned_path(src: Path, settings: Settings, keep_color: bool = False) -> Path:
    suffix = "_color" if keep_color else ""
    return settings.paths["cleaned"] / (src.stem + suffix + ".png")


def get_cleaned(src: Path, settings: Settings, reclean: bool = False,
                keep_color: bool = False, rotate: int = 0) -> Image.Image:
    """Return the cleaned page, using the on-disk cache when possible."""
    cache = cleaned_path(src, settings, keep_color=keep_color)
    if cache.exists() and not reclean:
        return Image.open(cache).convert("RGB")
    img = clean_page(src, settings, keep_color=keep_color, rotate=rotate)
    cache.parent.mkdir(parents=True, exist_ok=True)
    img.save(cache)
    return img


def get_page(src: Path, page_no: int, settings: Settings,
             reclean: bool = False) -> Image.Image:
    """Fully processed page.

    - keep_color_pages: real-color scans (the cover) skip both grayscale
      and AI colorization.
    - colorize_pages: cleaned B&W page goes through the AI colorizer;
      the raw model output is cached in output/colorized/, and the taste
      adjustments (saturation strength, burnt-orange uniform steering)
      are applied afterwards so changing them never re-runs the model.
    """
    rotate = settings.rotate_pages.get(page_no, 0)
    if page_no in settings.keep_color_pages:
        return get_cleaned(src, settings, reclean=reclean, keep_color=True,
                           rotate=rotate)

    img = get_cleaned(src, settings, reclean=reclean, rotate=rotate)
    if settings.colorize_pages and page_no in settings.colorize_pages:
        from colorize import boost_saturation, steer_reds_to_burnt_orange
        cache = settings.paths["colorized"] / (src.stem + ".png")
        if cache.exists() and not reclean:
            img = Image.open(cache).convert("RGB")
        else:
            from colorize import colorize_image
            img = colorize_image(img, tiles=settings.colorize_tiles)
            cache.parent.mkdir(parents=True, exist_ok=True)
            img.save(cache)
        img = boost_saturation(img, settings.colorize_strength)
        if page_no in settings.uniform_pages:
            img = steer_reds_to_burnt_orange(img)
    return img


def compose_frame(pages: list[Image.Image], settings: Settings) -> np.ndarray:
    """Compose one or two pages onto the video canvas; returns HxWx3 uint8.

    Two pages sit side by side with a thin gutter, like an open book.
    A single page (cover, unpaired page) is centered.
    """
    canvas = Image.new("RGB", (settings.width, settings.height), settings.background)
    gutter = settings.gutter if len(pages) > 1 else 0
    gutter_total = gutter * (len(pages) - 1)

    # scale every page to a common height, then fit the row to the canvas
    ref_h = max(p.height for p in pages)
    widths = [p.width * ref_h / p.height for p in pages]
    scale = min((settings.width - gutter_total) / sum(widths), settings.height / ref_h)

    row_w = round(sum(widths) * scale) + gutter_total
    x = (settings.width - row_w) // 2
    for page, w in zip(pages, widths):
        new_size = (round(w * scale), round(ref_h * scale))
        resized = page.resize(new_size, Image.LANCZOS)
        canvas.paste(resized, (x, (settings.height - new_size[1]) // 2))
        x += new_size[0] + gutter
    return np.asarray(canvas, dtype=np.uint8)
