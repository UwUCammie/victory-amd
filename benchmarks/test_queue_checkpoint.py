import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from queue_checkpoint import RELOAD_EXIT, check_queue_revision


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
