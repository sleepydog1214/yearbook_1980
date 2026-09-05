"""Turn 1980 yearbook scans into an MP4 slideshow.

Usage (from the project folder):
    python src/main.py                  # full video
    python src/main.py --limit 10      # quick proof with first 10 pages
    python src/main.py --transition cut --page-seconds 2
    python src/main.py --soundtrack song1.mp3 song2.mp3   # played in order

Raw scans are read from the project folder, cleaned copies are cached in
output/cleaned/, and the video is written to output/yearbook_1980.mp4.
"""

import argparse
import sys
from pathlib import Path

from config import Settings
from pages import find_spreads
from transitions import TRANSITIONS
from video import render


def parse_page_spec(spec: str, total: int) -> set[int]:
    """Parse "all" or "1,5-10,20" into a set of page numbers (1 = cover)."""
    if spec.lower() == "all":
        return set(range(1, total + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        elif part:
            pages.add(int(part))
    return pages


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the 1980 yearbook video.")
    p.add_argument("--limit", type=int, default=None,
                   help="only use the first N pages (quick test)")
    p.add_argument("--page-seconds", type=float, default=None,
                   help="seconds each page is held (default 2.5)")
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--transition", choices=sorted(TRANSITIONS), default=None,
                   help="transition between pages (default crossfade)")
    p.add_argument("--layout", choices=["spread", "single"], default=None,
                   help="spread = L+R pages side by side (default), single = one page per slide")
    p.add_argument("--colorize", nargs="?", const="all", default=None, metavar="PAGES",
                   help='AI-colorize pages: "all", or numbers/ranges like "1,5-10" (1 = cover)')
    p.add_argument("--color-strength", type=float, default=None,
                   help="saturation boost on colorized pages (default 1.3; 1.0 = model output)")
    p.add_argument("--rotate", type=str, default=None, metavar="SPEC",
                   help='manually rotate sideways pages: "12:90,57:-90" '
                        "(page number : degrees counterclockwise)")
    p.add_argument("--keep-color", type=str, default=None, metavar="PAGES",
                   help='pages scanned in real color, kept as-is (default "1", the green cover)')
    p.add_argument("--uniforms", nargs="?", const="all", default=None, metavar="PAGES",
                   help='pages where red clothing is steered to burnt orange (girls\' uniforms): "all" or ranges')
    p.add_argument("--soundtrack", type=Path, nargs="+", default=None,
                   help="audio file(s) to lay under the video, played in order")
    p.add_argument("--reclean", action="store_true",
                   help="redo image cleanup instead of using cached pages")
    p.add_argument("--output", type=str, default=None,
                   help="output filename (written to the output folder)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    if args.page_seconds is not None:
        settings.page_seconds = args.page_seconds
    if args.fps is not None:
        settings.fps = args.fps
    if args.transition is not None:
        settings.transition = args.transition
    if args.layout is not None:
        settings.layout = args.layout
    if args.soundtrack is not None:
        for song in args.soundtrack:
            if not song.exists():
                print(f"Soundtrack not found: {song}", file=sys.stderr)
                return 1
        settings.soundtrack = list(args.soundtrack)
    settings.limit = args.limit
    if args.output:
        settings.paths["video"] = settings.paths["output"] / args.output

    spreads = find_spreads(settings.paths["scans"], layout=settings.layout)
    if not spreads:
        print(f"No scans found in {settings.paths['scans']}", file=sys.stderr)
        return 1
    if settings.limit:
        spreads = spreads[: settings.limit]

    n_pages = sum(len(s.pages) for s in spreads)
    if args.colorize is not None:
        settings.colorize_pages = parse_page_spec(args.colorize, n_pages)
        print(f"Colorizing {len(settings.colorize_pages)} of {n_pages} pages "
              "(first pass is slow: model download + inference)")
    if args.color_strength is not None:
        settings.colorize_strength = args.color_strength
    if args.keep_color is not None:
        settings.keep_color_pages = parse_page_spec(args.keep_color, n_pages)
    if args.uniforms is not None:
        settings.uniform_pages = parse_page_spec(args.uniforms, n_pages)
    if args.rotate is not None:
        for part in args.rotate.split(","):
            page, _, deg = part.strip().partition(":")
            settings.rotate_pages[int(page)] = int(deg)

    total = (len(spreads) * settings.page_seconds
             + (len(spreads) - 1) * settings.transition_seconds
             * (settings.transition != "cut"))
    print(f"Rendering {len(spreads)} {settings.layout}s ({n_pages} pages) "
          f"-> ~{total:.0f}s of video "
          f"({settings.width}x{settings.height} @ {settings.fps}fps, "
          f"{settings.transition} transitions)")

    out = render(spreads, settings, reclean=args.reclean)
    print(f"\nDone: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
