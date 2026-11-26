"""Measure visible luminance changes in the center of an X11 window without saving images."""
import argparse
import os
import re
import subprocess


def summarize(output):
    samples = [(float(t), float(diff)) for t, diff in re.findall(
        r"pts_time:([^\s]+)[^\n]*\n[^\n]*lavfi\.signalstats\.YDIF=([^\s]+)", output
    )]
    if len(samples) < 2:
        raise ValueError("FFmpeg returned fewer than two frames with luma statistics")
    times = [t for t, _ in samples]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Capture timestamps did not advance for every sample")
    diffs = [d for _, d in samples[1:]]
    return len(samples), times[-1] - times[0], sum(d > 0 for d in diffs), sum(d >= 1 for d in diffs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("window", help="X11 id of the game window")
    parser.add_argument("--display", default=os.environ.get("DISPLAY"))
    parser.add_argument("--seconds", type=int, default=5)
    parser.add_argument("--rate", type=int, default=30)
    args = parser.parse_args()
    if not args.display or args.seconds < 1 or args.rate < 2:
        parser.error("supply an X11 display, a positive duration and a sample rate of at least two")
    geometry = subprocess.check_output([
        "ffprobe", "-v", "error", "-f", "x11grab", "-framerate", "30", "-window_id", args.window,
        "-probesize", "32", "-analyzeduration", "0", "-i", args.display,
        "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
    ], text=True, timeout=5)
    width, height = map(int, geometry.strip().split("x"))
    w, h = min(width, 256), min(height, 144)
    frames = args.rate * args.seconds
    filters = f"trim=end_frame={frames},format=yuv444p,signalstats,metadata=mode=print:key=lavfi.signalstats.YDIF:file=-"
    output = subprocess.check_output([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-f", "x11grab", "-framerate", str(args.rate), "-draw_mouse", "0", "-window_id", args.window,
        "-video_size", f"{w}x{h}", "-grab_x", str((width - w) // 2), "-grab_y", str((height - h) // 2),
        "-i", args.display, "-frames:v", str(frames), "-vf", filters,
        "-fps_mode", "passthrough", "-f", "null", "-",
    ], text=True, timeout=args.seconds * 3 + 10)
    samples, span, changes, larger = summarize(output)
    print(f"{samples} samples over {span:.2f} s, {w}x{h} center crop: "
          f"{changes} changed ({changes/span:.2f}/s), {larger} with mean luma difference >= 1")


if __name__ == "__main__":
    main()
