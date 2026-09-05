# 1980 Yearbook Video

Turns the yearbook page scans in the project folder into an MP4 slideshow.
Defaults carry over the 1979 render (3s page holds, pageturn transitions —
lengthened again to 1.4s here, L+R spreads) and add new restoration passes
(see `restore.py`): glare/lighting flattening, sideways-content detection,
and per-page deskew — plus tiled multi-pass colorization for stronger
faces, hair, and background color.

## Usage

Run from the project folder (`1980 yearbook`):

```
python src/main.py                    # full video -> output/yearbook_1980.mp4
python src/main.py --limit 10         # quick test with the first 10 pages
python src/main.py --page-seconds 3   # hold each page longer
python src/main.py --transition cut   # hard cuts instead of page turns
python src/main.py --transition crossfade  # crossfades instead of page turns
python src/main.py --layout single    # one page per slide instead of L+R spreads
python src/main.py --colorize         # AI-colorize every page
python src/main.py --colorize 1,20-40 # colorize only these pages (1 = cover)
python src/main.py --color-strength 1.6    # more vivid colors (default 1.45)
python src/main.py --uniforms         # steer red clothing to burnt orange (girls' uniforms)
python src/main.py --uniforms 2-60    # ...only on these pages (spare red sports jerseys)
python src/main.py --keep-color 1     # pages scanned in real color, kept as-is (default: the cover)
python src/main.py --soundtrack a.mp3 b.mp3  # songs in order, looped to fit, faded out at the end
python src/main.py --output my_video.mp4   # custom name in the output folder
python src/main.py --reclean          # redo image cleanup from the raw scans
```

Requires Python 3.10+ with `Pillow`, `numpy`, and `imageio-ffmpeg`
(`pip install Pillow numpy imageio-ffmpeg` — ffmpeg itself is bundled).
Colorization additionally needs `pip install torch scikit-image`; the
model weights (~130 MB) download automatically on first use.

## How it works

| File | Role |
|---|---|
| `main.py` | CLI entry point |
| `config.py` | All tunable settings (resolution, timing, cleanup, encoding) |
| `pages.py` | Finds scans, sorts into book order, groups L+R pairs into spreads |
| `cleanup.py` | Per-page cleanup: grayscale, auto-contrast, unsharp mask; composes 1- or 2-page spreads on the 1920x1080 canvas |
| `restore.py` | Restoration passes: sideways-content fix, deskew (squares each page), glare/lighting flattening from paper-pixel sampling |
| `colorize.py` | AI colorization (SIGGRAPH'17 model, Zhang et al.); whole-page pass + NxN tiled passes blended for small faces/hair/backgrounds |
| `colorizers/` | Vendored model code from github.com/richzhang/colorization |
| `transitions.py` | Transition registry (`cut`, `crossfade`, `pageturn`) |
| `video.py` | Streams frames to ffmpeg (H.264), muxes soundtrack if given |

Cleaned pages are cached in `output/cleaned/` and raw AI-colorized pages
in `output/colorized/`, so tweaking video settings doesn't redo the image
work — and because `--color-strength` and `--uniforms` are applied *after*
the colorized cache, changing them re-renders in a couple of minutes with
no model inference. Use `--reclean` (or delete those folders) only after
changing the base cleanup (contrast/sharpen) settings.

## Future ideas (where they'd go)

- **More transitions** (slide, wipe): add a generator function
  in `transitions.py` and register it in `TRANSITIONS`.
- **Fancier audio** (multiple songs, per-section music): extend
  `video.mux_soundtrack` — looping and end fade-out are already in.
- **Ken Burns pan/zoom**: replace the static hold loop in `video.render`
  with a per-page camera path over a higher-res composed frame.
- **Title/chapter cards**: generate text frames in `cleanup.py` and insert
  them into the scan list in `main.py`.
