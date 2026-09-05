"""AI colorization of B&W pages.

Uses the SIGGRAPH 2017 "Real-Time User-Guided Image Colorization" model
(Zhang et al.) via the author's `colorizers` package. The model predicts
the color channels at low resolution while the original scan keeps its
full-resolution detail — only color is added, sharpness is untouched.

torch/colorizers are imported lazily so the rest of the pipeline works
without them; they're only needed when colorization is requested. The
model weights (~130 MB) download automatically on first use.
"""

import numpy as np
from PIL import Image

_model = None


def _get_model():
    global _model
    if _model is None:
        import colorizers
        _model = colorizers.siggraph17(pretrained=True).eval()
    return _model


def _predict_ab(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run the model on an RGB uint8 array; return (L, ab) at full res."""
    import colorizers
    import torch
    import torch.nn.functional as F

    model = _get_model()
    tens_l_orig, tens_l_rs = colorizers.preprocess_img(rgb, HW=(256, 256))
    with torch.no_grad():
        out_ab = model(tens_l_rs).cpu()
    ab = F.interpolate(out_ab, size=tens_l_orig.shape[2:], mode="bilinear")
    return tens_l_orig[0, 0].numpy(), ab[0].numpy().transpose(1, 2, 0)


def _feather(n: int, margin: int) -> np.ndarray:
    """1D blend weight: ramps from the edges, flat in the middle."""
    ramp = (np.arange(n, dtype=np.float32) + 1.0) / max(1, margin)
    return np.minimum(1.0, np.minimum(ramp, ramp[::-1]))


def colorize_image(img: Image.Image, tiles: int = 2) -> Image.Image:
    """Return a colorized copy of a (grayscale) page image.

    Several passes: one whole-page pass for globally coherent color,
    plus an NxN grid of overlapping tile passes. The model only sees
    256x256, so on a whole yearbook page small faces are a few pixels
    and barely get colorized — each tile pass gives them several times
    the resolution, which brings out faces, hair, and background color.
    The ab (color) fields are feather-blended; the page keeps its
    original full-resolution luminance.

    Runs at full model strength; taste adjustments (saturation, hue
    steering) are cheap post-processing done at render time, so the
    cached output never needs regenerating when they change.
    """
    from skimage import color

    rgb = np.asarray(img.convert("RGB"))
    h, w = rgb.shape[:2]
    L, ab_full = _predict_ab(rgb)

    if tiles and tiles > 1:
        overlap = 0.25
        ab_acc = np.zeros((h, w, 2), dtype=np.float32)
        wt = np.zeros((h, w), dtype=np.float32)
        for r in range(tiles):
            for c in range(tiles):
                y0 = int(max(0, (r - overlap) * h / tiles))
                y1 = int(min(h, (r + 1 + overlap) * h / tiles))
                x0 = int(max(0, (c - overlap) * w / tiles))
                x1 = int(min(w, (c + 1 + overlap) * w / tiles))
                _, ab_t = _predict_ab(rgb[y0:y1, x0:x1])
                fy = _feather(y1 - y0, int(overlap * h / tiles))
                fx = _feather(x1 - x0, int(overlap * w / tiles))
                tile_w = np.outer(fy, fx).astype(np.float32)
                ab_acc[y0:y1, x0:x1] += ab_t * tile_w[..., None]
                wt[y0:y1, x0:x1] += tile_w
        ab_tiled = ab_acc / np.maximum(wt, 1e-6)[..., None]
        # tiles carry the local color detail; the full pass keeps pages coherent
        ab = 0.35 * ab_full + 0.65 * ab_tiled
    else:
        ab = ab_full

    lab = np.dstack([L, ab])
    out = color.lab2rgb(lab)
    return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8))


def boost_saturation(img: Image.Image, strength: float) -> Image.Image:
    """Scale color saturation; 1.0 = model output, >1.0 = more vivid."""
    if strength == 1.0:
        return img
    from PIL import ImageEnhance
    return ImageEnhance.Color(img).enhance(strength)


# School context: girls' uniforms were burnt orange, which the model
# tends to paint plain red. Steering constants are 8-bit HSV (PIL scale,
# hue 0-255 for 0-360deg): burnt orange sits around hue 24deg = 17/255.
_TARGET_HUE = 17          # burnt orange
_RED_HI = 11              # reds from 0..15deg
_RED_LO = 234             # ...and wrapped reds from 330..360deg
_MIN_SAT = 60             # only clearly colored pixels
_MIN_VAL = 40             # leave near-black alone (letters, dark shadows)


def steer_reds_to_burnt_orange(img: Image.Image, blend: float = 0.7) -> Image.Image:
    """Shift strongly red pixels toward burnt orange (uniform color).

    Applied per-page (see --uniforms) so genuinely red things — sports
    jerseys, for instance — can be left untouched on other pages.
    """
    hsv = np.asarray(img.convert("HSV")).copy()
    h = hsv[:, :, 0].astype(np.int16)
    s, v = hsv[:, :, 1], hsv[:, :, 2]

    signed_h = np.where(h >= _RED_LO, h - 255, h)   # wrapped reds go negative
    red = ((signed_h <= _RED_HI) & (s >= _MIN_SAT) & (v >= _MIN_VAL))
    steered = signed_h * (1.0 - blend) + _TARGET_HUE * blend
    hsv[:, :, 0] = np.where(red, steered, h).astype(np.int16).clip(0, 255).astype(np.uint8)
    return Image.fromarray(hsv, mode="HSV").convert("RGB")
