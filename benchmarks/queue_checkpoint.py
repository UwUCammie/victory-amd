"""Let an idle benchmark launcher reload its serial queue before another attempt."""

import hashlib
import os
from pathlib import Path


RELOAD_EXIT = 75


def check_queue_revision():
    """Call only while no renderer or compilation belongs to this launcher."""
    path = os.environ.get('GOAL30_QUEUE_PATH')
    revision = os.environ.get('GOAL30_QUEUE_REVISION')
    if path and revision and hashlib.sha256(Path(path).read_bytes()).hexdigest() != revision:
        raise SystemExit(RELOAD_EXIT)
