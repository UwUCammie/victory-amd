"""Run an offline Wine/game command with private cold graphics caches on Linux."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def launch(dest, profile, seconds, command):
    dest = dest.resolve()
    if profile:
        profile = profile.resolve(strict=True)
        if dest.is_relative_to(profile):
            raise ValueError("choose a run directory outside the profile")
    dest.mkdir(parents=True, exist_ok=False)
    data = dest / "data"
    if profile:
        shutil.copytree(profile, data, ignore=shutil.ignore_patterns("SARC*", "temp", "crashes.log"))
    else:
        data.mkdir()
    caches = ("cache", "vkd3dcache", "mesa", "xdg", "dxvk")
    for name in caches:
        (dest / name).mkdir()
    env = dict(os.environ, VICTORY_FRAME_TRACE="1", VICTORY_OUTPUT="1280x720",
               VICTORY_DATA_DIR="Z:" + str(data), VICTORY_CACHE_DIR="Z:" + str(dest / "cache"),
               VKD3D_SHADER_CACHE_PATH=str(dest / "vkd3dcache"), MESA_SHADER_CACHE_DIR=str(dest / "mesa"),
               DXVK_STATE_CACHE_PATH="Z:" + str(dest / "dxvk"), XDG_CACHE_HOME=str(dest / "xdg"))
    metadata = {"empty_cache_directories": {k:len(list((dest / k).iterdir())) for k in caches},
                "story_slots": sum(1 for _ in data.rglob("SARC*")), "timeout": seconds}
    def save():
        (dest / "launch.json").write_text(json.dumps(metadata) + "\n", encoding="utf-8")
    with (dest / "run.log").open("wb") as log:
        metadata["start_utc"] = utc()
        save()
        proc = subprocess.run(["timeout", "--kill-after=5s", str(seconds), *command],
                              env=env, stdout=log, stderr=subprocess.STDOUT)
        metadata["end_utc"] = utc()
        (dest / "exit-code").write_text(f"{proc.returncode}\n", encoding="utf-8")
        save()
    return proc.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="new private output directory")
    parser.add_argument("--profile", type=Path, help="copy a completed player's setup but omit story saves")
    parser.add_argument("--seconds", type=int, default=308)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- followed by the offline Wine launch command")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.seconds < 1:
        parser.error("supply a command and positive duration")
    try:
        code = launch(args.run, args.profile, args.seconds, command)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    sys.exit(0 if code == 124 else code if code > 0 else 1)
