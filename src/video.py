"""Render cleaned pages into an MP4, with an optional soundtrack mux."""

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np

from cleanup import compose_frame, get_page
from config import Settings
from pages import Spread
from transitions import TRANSITIONS


def render(spreads: list[Spread], settings: Settings, reclean: bool = False) -> Path:
    hold_frames = max(1, round(settings.page_seconds * settings.fps))
    trans_frames = round(settings.transition_seconds * settings.fps)
    transition = TRANSITIONS[settings.transition]

    video_path = settings.paths["video"]
    video_path.parent.mkdir(parents=True, exist_ok=True)

    # With a soundtrack, render silent video to a temp file and mux into
    # the real name afterwards.
    target = video_path
    if settings.soundtrack:
        video_path = video_path.with_name(video_path.stem + "_silent.mp4")

    writer = imageio_ffmpeg.write_frames(
        str(video_path),
        (settings.width, settings.height),
        fps=settings.fps,
        codec="libx264",
        quality=None,
        macro_block_size=1,  # 1920x1080 is already a standard size; don't pad to 1088
        output_params=["-crf", str(settings.crf), "-preset", "medium",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    writer.send(None)  # prime the generator

    prev_frame: np.ndarray | None = None
    total_frames = 0
    page_no = 0
    try:
        for i, spread in enumerate(spreads, 1):
            pages = []
            for src in spread.pages:
                page_no += 1
                pages.append(get_page(src, page_no, settings, reclean=reclean))
            frame = compose_frame(pages, settings)
            print(f"  [{i}/{len(spreads)}] {spread.name}")

            if prev_frame is not None:
                for tframe in transition(prev_frame, frame, trans_frames):
                    writer.send(np.ascontiguousarray(tframe))
                    total_frames += 1
            for _ in range(hold_frames):
                writer.send(frame)
            total_frames += hold_frames
            prev_frame = frame
    finally:
        writer.close()

    if settings.soundtrack:
        duration = total_frames / settings.fps
        mux_soundtrack(video_path, settings.soundtrack, target, duration)
        video_path.unlink()          # drop the silent temp file
        return target
    return video_path


def audio_duration(path: Path) -> float:
    """Length of an audio file in seconds, read from ffmpeg's info output."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run([ffmpeg, "-i", str(path)],
                          capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def mux_soundtrack(video_path: Path, audio_paths: list[Path], out: Path,
                   duration: float) -> Path:
    """Lay the songs under the video in order, looping the whole sequence
    if it's shorter than the video and fading it out over the last few
    seconds."""
    fade = min(3.0, duration)
    total = sum(audio_duration(p) for p in audio_paths)
    reps = max(1, -(-int(duration) // max(1, int(total))))  # ceil, at least once
    playlist = list(audio_paths) * reps

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-i", str(video_path)]
    for p in playlist:
        cmd += ["-i", str(p)]
    chain = "".join(f"[{i}:a]" for i in range(1, len(playlist) + 1))
    filt = (f"{chain}concat=n={len(playlist)}:v=0:a=1[cat];"
            f"[cat]afade=t=out:st={duration - fade:.2f}:d={fade:.2f}[aout]")
    cmd += ["-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out
