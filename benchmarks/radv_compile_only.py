"""Run a compiler fixture on RADV with Mesa's no-op amdgpu DRM device."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shim", type=Path, required=True, help="libamdgpu_noop_drm_shim.so")
    parser.add_argument("--work", type=Path, required=True, help="private writable fixture directory")
    parser.add_argument("--family", default="navi31", help="device name from Mesa's amdgpu device list")
    parser.add_argument("--icd", type=Path, default=Path("/usr/share/vulkan/icd.d/radeon_icd.json"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply a compiler fixture command")
    if not args.shim.is_file() or not args.icd.is_file():
        parser.error("the shim and RADV ICD manifest must exist")
    if not args.work.is_dir():
        parser.error("the private working directory must exist")
    directory = args.work.resolve()
    if directory in (Path("/"), Path("/tmp")) or any(directory.is_relative_to(tree) for tree in ("/dev", "/proc")):
        parser.error("choose a dedicated working directory outside the device and process trees")
    work = str(directory)

    # Do not pass through any real render nodes, the desktop display, or the
    # caller's Wine server sockets. Apply the preload only inside this namespace.
    bwrap = [
        "bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
        "--bind", work, work, "--chdir", work, "--unshare-net", "--unshare-pid", "--die-with-parent",
        "--unsetenv", "DISPLAY", "--unsetenv", "WAYLAND_DISPLAY", "--unsetenv", "LD_PRELOAD",
        "--unsetenv", "VK_INSTANCE_LAYERS", "--unsetenv", "VK_LAYER_PATH",
        "--setenv", "XDG_RUNTIME_DIR", "/tmp", "--setenv", "VK_DRIVER_FILES", str(args.icd.resolve()),
        "--setenv", "MESA_SHADER_CACHE_DISABLE", "true", "--setenv", "AMDGPU_GPU_ID", args.family,
        "--setenv", "DRM_SHIM_DEBUG", "1", "--",
        "/bin/sh", "-c", 'test ! -e /dev/dri && exec env LD_PRELOAD="$0" "$@"',
        str(args.shim.resolve()), *command,
    ]
    os.execvp(bwrap[0], bwrap)


if __name__ == "__main__":
    main()
