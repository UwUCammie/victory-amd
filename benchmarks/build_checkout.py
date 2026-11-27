"""Run a build at a pinned revision while keeping its checkout path stable."""

import argparse
import fcntl
from pathlib import Path
import subprocess


def git(repo, *args):
    return subprocess.check_output(["git", "-C", repo, *args], text=True).strip()


def require_clean(repo):
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError(f"path is not a checkout root: {repo}")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"checkout has local changes: {repo}")


def build_in_worktree(source, worktree, command):
    source = source.resolve(strict=True)
    worktree = worktree.resolve()
    if source.is_relative_to(worktree) or worktree.is_relative_to(source):
        raise ValueError("choose a separate build worktree")

    lock_path = worktree.with_name(worktree.name + ".build-lock")
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        require_clean(source)
        revision = git(source, "rev-parse", "--verify", "HEAD")
        if not worktree.exists():
            git(source, "worktree", "add", "--detach", str(worktree), revision)
        else:
            require_clean(worktree)
            common = git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
            if git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir") != common:
                raise ValueError("the build path belongs to another repository")
            if git(worktree, "rev-parse", "--abbrev-ref", "HEAD") != "HEAD":
                raise ValueError("the build worktree must be detached")
            if git(worktree, "rev-parse", "--verify", "HEAD") != revision:
                git(worktree, "switch", "--detach", revision)
        print(f"Build checkout is pinned at {revision[:12]} in {worktree}", flush=True)
        # Keep the checkout pinned if the wrapper is interrupted before the build exits.
        return subprocess.run(command, cwd=worktree, pass_fds=(lock.fileno(),)).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="clean checkout with the revision to build")
    parser.add_argument("worktree", type=Path, help="separate detached worktree to reuse")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply a build command")
    try:
        return build_in_worktree(args.source, args.worktree, command)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
