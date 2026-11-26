"""Locate one-frame brightness reversals in a fixed region of a private recording."""
import argparse
import subprocess
from collections import deque
from pathlib import Path

import numpy as np


def reversals(frames, change=24, tolerance=6):
    """Yield (decoded frame index, fraction of region) for each distinct middle frame."""
    last = deque(maxlen=3)
    for index, image in enumerate(frames):
        if last and np.array_equal(image, last[-1][1]):
            continue
        last.append((index, image.astype(np.int16)))
        if len(last) == 3:
            (_, before), (middle, now), (_, after) = last
            mask = (np.abs(before - after) <= tolerance) & (np.abs(now - before) >= change)
            mask &= np.abs(now - after) >= change
            yield middle, float(np.mean(mask))


def region_frames(video, region, start=0, stop=None):
    x, y, w, h = region
    # Crop in grayscale at full resolution to preserve odd pixel coordinates.
    trim = f"trim=start_frame={start}"
    if stop is not None:
        trim += f":end_frame={stop}"
    vf = f"{trim},format=gray,crop={w}:{h}:{x}:{y}:exact=1"
    command = ["ffmpeg", "-nostdin", "-loglevel", "error", "-threads", "1", "-noautorotate", "-i", str(video), "-map", "0:v:0",
               "-an", "-sn", "-vf", vf, "-filter_threads", "1", "-threads", "1",
               "-fps_mode", "passthrough", "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        try:
            while chunk := proc.stdout.read(w * h):
                if len(chunk) != w * h:
                    raise ValueError("incomplete grayscale frame")
                yield np.frombuffer(chunk, dtype=np.uint8)
        finally:
            proc.stdout.close()
        if proc.wait() != 0:
            raise ValueError("could not decode the selected region")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("region", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"))
    parser.add_argument("--start-frame", type=int, default=0, help="first decoded frame of the fixed-camera interval")
    parser.add_argument("--stop-frame", type=int, help="exclusive end of that interval")
    args = parser.parse_args()
    if args.start_frame < 0 or (args.stop_frame is not None and args.stop_frame <= args.start_frame):
        parser.error("expected a nonnegative start frame before the stop frame")
    x, y, w, h = args.region
    if min(x, y) < 0 or min(w, h) < 1:
        parser.error("region needs a nonnegative origin and positive dimensions")
    # FFmpeg crops an out-of-range origin to the nearest valid one.
    dimensions = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(args.video)], text=True).strip()
    width, height = map(int, dimensions.split("x"))
    if x + w > width or y + h > height:
        parser.error(f"region outside {width}x{height} video")
    scores = list(reversals(region_frames(args.video, args.region, args.start_frame, args.stop_frame)))
    if not scores:
        parser.exit(1, "Need three distinct region frames.\n")
    print(f"{len(scores)} distinct middle frames; highest fractions of reversing pixels:")
    for index, score in sorted(scores, key=lambda item: -item[1])[:5]:
        print(f"frame {args.start_frame + index}: {score:.2%}")
