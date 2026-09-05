"""Discover and order the yearbook scans.

Scan filenames encode capture time plus an L/R suffix for the left and
right page of each spread, e.g. IMG_2026_08_30_16_46_22L.jpg. Sorting by
name therefore yields book order: the cover (captured earlier, no L/R
suffix) sorts first, and L sorts before R within each spread.
"""

from dataclasses import dataclass
from pathlib import Path

SCAN_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


@dataclass
class Spread:
    """One video 'slide': a single page (cover, lone page) or an L+R pair."""
    pages: list[Path]

    @property
    def name(self) -> str:
        return " + ".join(p.name for p in self.pages)


def find_scans(scans_dir: Path) -> list[Path]:
    """Return scan files in book order (filename sort)."""
    scans = [
        p for p in scans_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SCAN_EXTENSIONS
    ]
    return sorted(scans, key=lambda p: p.name.lower())


def find_spreads(scans_dir: Path, layout: str = "spread") -> list[Spread]:
    """Group scans into spreads.

    layout="spread": an L scan followed by its matching R scan (same
    timestamp stem) becomes one two-page spread; anything else (cover,
    unpaired pages) stands alone. layout="single": every scan alone.
    """
    scans = find_scans(scans_dir)
    if layout == "single":
        return [Spread([s]) for s in scans]

    spreads: list[Spread] = []
    i = 0
    while i < len(scans):
        s = scans[i]
        if (s.stem.endswith("L") and i + 1 < len(scans)
                and scans[i + 1].stem == s.stem[:-1] + "R"):
            spreads.append(Spread([s, scans[i + 1]]))
            i += 2
        else:
            spreads.append(Spread([s]))
            i += 1
    return spreads
