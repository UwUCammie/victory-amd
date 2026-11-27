import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from queue_checkpoint import RELOAD_EXIT, check_queue_revision, rotate_trials


class QueueCheckpointTests(unittest.TestCase):
    def test_only_a_changed_queue_requests_reload(self):
        with TemporaryDirectory() as root, patch.dict(os.environ, clear=True):
            queue = Path(root) / "queue.py"
            current = b"old queue"
            queue.write_bytes(current)
            check_queue_revision()
            os.environ["GOAL30_QUEUE_PATH"] = str(queue)
            os.environ["GOAL30_QUEUE_REVISION"] = hashlib.sha256(current).hexdigest()
            check_queue_revision()
            queue.write_bytes(b"new queue")
            with self.assertRaises(SystemExit) as result:
                check_queue_revision()
            self.assertEqual(result.exception.code, RELOAD_EXIT)

    def test_rotation_preserves_other_slots_and_prefers_the_oldest_launch(self):
        rows = [('a', 'runner-a'), ('fixed', 'runner'), ('b', 'runner-b'), ('c', 'runner-c')]
        with TemporaryDirectory() as root:
            root = Path(root)
            for name, times in [('a-1', 3), ('a-2', 6), ('b-1', 4), ('c-extra-1', 9)]:
                launch = root / f'cold-{name}' / 'launch.json'
                launch.parent.mkdir()
                launch.write_text('{}')
                os.utime(launch, ns=(times, times))
            (root / 'cold-c-1').mkdir()
            trials = {'a', 'b', 'c'}
            self.assertEqual(rotate_trials(rows, trials, root, 'cold-'), [rows[3], rows[1], rows[2], rows[0]])
            launched = root / 'cold-c-1' / 'launch.json'
            launched.write_text('{}')
            os.utime(launched, ns=(10, 10))
            self.assertEqual(rotate_trials(rows, trials, root, 'cold-'), [rows[2], rows[1], rows[0], rows[3]])

    def test_untried_trials_preserve_the_configured_order(self):
        rows = [('c', 'runner-c'), ('b', 'runner-b'), ('a', 'runner-a')]
        with TemporaryDirectory() as root:
            self.assertEqual(rotate_trials(rows, {'a', 'b', 'c'}, Path(root), 'cold-'), rows)
