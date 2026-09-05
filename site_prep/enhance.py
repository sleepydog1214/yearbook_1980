"""Per-photo enhancement: colorize the crop, then upscale it.

Colorizing each extracted photo individually gives far better color
than the page-level pass: the model's 256px view covers just this one
photo instead of a whole page, so faces and details get full attention.

Upscaling is 2x Lanczos plus adaptive unsharp — clean and artifact-free.
The stage is a single function so a neural super-resolution model
(e.g. Real-ESRGAN) can be swapped in later without touching callers.
"""

import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

UPSCALE = 2


def enhance_photo(crop: Image.Image, colorize: bool = True) -> Image.Image:
    """Clean up, colorize, and upscale one extracted photo."""
    img = crop.convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.convert("RGB")

    if colorize:
        from colorize import boost_saturation, colorize_image
        img = colorize_image(img, tiles=0)      # crop is small; one pass is right
        img = boost_saturation(img, 1.35)

    img = img.resize((img.width * UPSCALE, img.height * UPSCALE), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=65, threshold=3))
    return img
