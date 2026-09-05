"""Central settings for the yearbook video pipeline.

Everything tunable lives here so future features (new transitions,
soundtrack, Ken Burns pans, chapter titles) only need new fields.
"""

from dataclasses import dataclass, field
from pathlib import Path

# Project layout: this file lives in <project>/src/
PROJECT_DIR = Path(__file__).resolve().parent.parent
SCANS_DIR = PROJECT_DIR                      # raw scans sit in the project root
OUTPUT_DIR = PROJECT_DIR / "output"
CLEANED_DIR = OUTPUT_DIR / "cleaned"         # cached cleaned pages
COLORIZED_DIR = OUTPUT_DIR / "colorized"     # cached colorized pages
VIDEO_PATH = OUTPUT_DIR / "yearbook_1980.mp4"


@dataclass
class Settings:
    # --- video frame ---
    width: int = 1920
    height: int = 1080
    fps: int = 30
    background: tuple = (12, 12, 12)         # near-black letterbox

    # --- timing ---
    page_seconds: float = 3.0                # hold time per page
    transition_seconds: float = 1.4          # length of transition between pages (1979 + 0.3s)

    # --- layout ---
    layout: str = "spread"                   # "spread" = L+R pairs side by side, "single" = one page per slide
    gutter: int = 6                          # px between the two pages of a spread

    # --- transitions (see transitions.py registry) ---
    transition: str = "pageturn"             # "cut" | "crossfade" | "pageturn"

    # --- cleanup ---
    autocontrast_cutoff: float = 1.0         # % of histogram clipped per side
    sharpen: bool = True
    grayscale: bool = True                   # pages are B&W; kills scanner color casts
    flatten_lighting: bool = True            # remove glare/uneven lighting from pages
    deskew: bool = True                      # straighten slightly rotated pages
    max_skew: float = 3.0                    # degrees searched either way by deskew
    # Manual rotation for sideways pages: {page_no: degrees CCW}, e.g. {12: 90}.
    # (Automatic detection was tried and false-positived on art-heavy layouts.)
    rotate_pages: dict = field(default_factory=dict)

    # --- AI colorization (see colorize.py) ---
    colorize_pages: set = field(default_factory=set)  # page numbers (1 = cover) to colorize
    colorize_strength: float = 1.45          # saturation boost on the model output
    colorize_tiles: int = 2                  # NxN tiled second pass (small faces/hair get
                                             # real color); 0 or 1 = single whole-page pass
    keep_color_pages: set = field(default_factory=lambda: {1})  # real-color scans (red cover)
    uniform_pages: set = field(default_factory=set)  # pages where reds -> burnt orange (girls' uniforms)

    # --- soundtrack ---
    # Audio files (mp3/m4a/wav) played in order under the video; the
    # sequence loops if it's shorter than the video and fades out at the end.
    soundtrack: list[Path] = field(default_factory=list)

    # --- encoding ---
    crf: int = 20                            # H.264 quality (lower = better/larger)

    # --- debugging ---
    limit: int | None = None                 # only render first N pages

    paths: dict = field(default_factory=lambda: {
        "scans": SCANS_DIR,
        "output": OUTPUT_DIR,
        "cleaned": CLEANED_DIR,
        "colorized": COLORIZED_DIR,
        "video": VIDEO_PATH,
    })
