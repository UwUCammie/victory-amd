"""Find the first sustained match to a private reference image in timed screenshots."""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def thumbnail(path):
    with Image.open(path) as frame:
        return frame.convert("RGB").resize((32, 20), Image.Resampling.BOX)


def distance(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def first_window(samples, *, threshold, duration, max_gap):
    start = previous = None
    for at, error in samples:
        if previous is not None and at <= previous:
            raise ValueError("Sample times must increase")
        if error > threshold:
            start = None
        else:
            if start is None or at - previous > max_gap:
                start = at
            if at - start >= duration:
                return start, at
        previous = at
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("captures", type=Path, help="directory containing private-SECONDS.png images")
    parser.add_argument("--threshold", type=float, required=True, help="maximum mean RGB difference on the 0–255 scale")
    parser.add_argument("--duration", type=float, default=35)
    parser.add_argument("--max-gap", type=float, default=6)
    args = parser.parse_args()
    if not (0 <= args.threshold <= 255 and args.max_gap > 0 and args.duration > 0):
        parser.error("expected threshold 0–255 and positive duration and max-gap")
    target = thumbnail(args.reference)
    files = sorted((float(f.stem.removeprefix("private-")), f) for f in args.captures.glob("private-*.png"))
    window = first_window(((at, distance(target, thumbnail(f))) for at, f in files),
                          threshold=args.threshold, duration=args.duration, max_gap=args.max_gap)
    if window is None:
        parser.exit(1, "No qualifying scene window.\n")
    print(f"--start {window[0]:g} --stop {window[1]:g}")
