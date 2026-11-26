"""Classify a saved visual test after the renderer exits, without assigning an FPS."""
import argparse
import json
import math
from pathlib import Path

from cold_boot import TRACE
from first_room import DeviceLost, SessionFailed, session_lines


def classify(lines, *, interrupted, exit_code, elapsed, target):
    if interrupted:
        return "interrupted"
    if not math.isfinite(target) or not math.isfinite(elapsed) or target <= 0 or elapsed < 0:
        raise ValueError("invalid saved-route duration")
    presented = False
    try:
        for line in session_lines(lines):
            if not presented and TRACE.search(line):
                presented = True
    except DeviceLost:
        return "device-failure"
    except SessionFailed:
        return "renderer-failure"
    if exit_code != 124 or elapsed < target or not presented:
        return "incomplete"
    return "finished"


def route_outcome(run, overlap, elapsed, target):
    if overlap.exists():
        return "interrupted"
    try:
        code = (run / "exit-code").read_text().strip()
        with (run / "run.log").open(encoding="utf-8", errors="replace") as log:
            return classify(log, interrupted=overlap.exists(), exit_code=int(code) if code.isdecimal() else None,
                            elapsed=elapsed, target=target)
    except FileNotFoundError:
        return "incomplete"


def scene_samples(run, seconds):
    """Fraction of the central half of the image with all RGB channels at 6 or below."""
    from PIL import Image, ImageChops

    samples = []
    for second in seconds:
        if second < 0:
            raise ValueError("sample times must be nonnegative")
        path = run / "cap" / f"private-{second}.png"
        if not path.exists():
            samples.append({"second": second, "near_black_fraction": None})
            continue
        with Image.open(path) as frame:
            w, h = frame.size
            left, top = w // 4, h // 4
            box = (left, top, max(left + 1, 3 * w // 4), max(top + 1, 3 * h // 4))
            crop = frame.crop(box).convert("RGB")
            red, green, blue = crop.split()
            brightest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
            near_black = sum(brightest.histogram()[:7])
            samples.append({"second": second, "near_black_fraction": near_black / (crop.width * crop.height)})
    return samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory containing run.log and exit-code")
    parser.add_argument("--elapsed", type=float, required=True, help="seconds measured by the launcher")
    parser.add_argument("--target", type=float, required=True, help="configured timeout in seconds")
    parser.add_argument("--overlap", type=Path, required=True, help="this attempt's foreground-overlap marker")
    parser.add_argument("--sample-seconds", type=int, nargs="+", help="measure the center of these private captures (requires Pillow)")
    args = parser.parse_args()
    result = {"outcome": route_outcome(args.run, args.overlap, args.elapsed, args.target)}
    if args.sample_seconds:
        result["scene_samples"] = scene_samples(args.run, args.sample_seconds)
    print(json.dumps(result))
