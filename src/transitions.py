"""Page transitions.

A transition is a generator that yields the in-between frames from one
page frame to the next. To add a new transition (slide, wipe, page-turn):
write a function with the same signature and add it to TRANSITIONS.
"""

from collections.abc import Iterator

import numpy as np


def cut(a: np.ndarray, b: np.ndarray, n_frames: int) -> Iterator[np.ndarray]:
    """No transition frames — hard cut."""
    return iter(())


def crossfade(a: np.ndarray, b: np.ndarray, n_frames: int) -> Iterator[np.ndarray]:
    af = a.astype(np.float32)
    bf = b.astype(np.float32)
    for i in range(1, n_frames + 1):
        t = i / (n_frames + 1)
        yield (af * (1.0 - t) + bf * t).astype(np.uint8)


def pageturn(a: np.ndarray, b: np.ndarray, n_frames: int) -> Iterator[np.ndarray]:
    """Book-style page turn: the old page folds over from right to left,
    revealing the new page underneath. The turned-over part shows a
    paper-white 'back of page' with a faint mirrored ghost of the front,
    and the fold casts a soft shadow on the page being revealed."""
    h, w = a.shape[:2]
    shadow_w = max(8, w // 48)
    for i in range(1, n_frames + 1):
        t = i / (n_frames + 1)
        te = t * t * (3.0 - 2.0 * t)          # smoothstep easing
        f = int(round(w * (1.0 - te)))        # fold line sweeps right -> left
        frame = b.copy()
        if f > 0:
            frame[:, :f] = a[:, :f]           # not-yet-turned part of old page
        # the folded-over part lies left of the fold, mirrored around it
        left = max(0, 2 * f - w)
        if f > left:
            back = a[:, f:2 * f - left][:, ::-1].astype(np.float32)
            frame[:, left:f] = np.clip(back * 0.15 + 217.0, 0, 255).astype(np.uint8)
        # shadow cast by the lifted page onto the newly revealed page
        s1 = min(w, f + shadow_w)
        if s1 > f:
            grad = np.linspace(0.55, 1.0, s1 - f, dtype=np.float32)[None, :, None]
            frame[:, f:s1] = (frame[:, f:s1].astype(np.float32) * grad).astype(np.uint8)
        yield frame


TRANSITIONS = {
    "cut": cut,
    "crossfade": crossfade,
    "pageturn": pageturn,
}
