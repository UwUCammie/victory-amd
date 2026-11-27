"""Keep a shared build checkout pinned until the build process exits."""

import fcntl
from pathlib import Path
import select
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from build_checkout import __file__ as RUNNER


class BuildCheckoutTests(unittest.TestCase):
    def test_interrupted_wrapper_keeps_lock_with_its_running_build(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", source], check=True)
            subprocess.run(
                ["git", "-C", source, "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "source"],
                check=True,
            )
            checkout = root / "builder"
            command = [sys.executable, "-u", "-c", "print('building'); input()"]
            with subprocess.Popen(
                [sys.executable, RUNNER, source, checkout, "--", *command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                bufsize=0,
            ) as wrapper:
                for prefix in (b"Build checkout is pinned", b"building"):
                    self.assertTrue(select.select([wrapper.stdout], [], [], 5)[0])
                    self.assertTrue(wrapper.stdout.readline().startswith(prefix))

                wrapper.kill()
                wrapper.wait(timeout=5)
                with (root / "builder.build-lock").open("rb") as lock:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    wrapper.stdin.write(b"\n")
                    wrapper.stdin.flush()
                    self.assertTrue(select.select([wrapper.stdout], [], [], 5)[0])
                    self.assertEqual(wrapper.stdout.read(1), b"")
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


if __name__ == "__main__":
    unittest.main()
