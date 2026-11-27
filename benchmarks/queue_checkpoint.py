"""Let an idle benchmark launcher reload its serial queue before another attempt."""

import hashlib
import os
from pathlib import Path


RELOAD_EXIT = 75
OVERLAP_EXIT = 76


def check_queue_revision():
    """Call only while no renderer or compilation belongs to this launcher."""
    path = os.environ.get('GOAL30_QUEUE_PATH')
    revision = os.environ.get('GOAL30_QUEUE_REVISION')
    if path and revision and hashlib.sha256(Path(path).read_bytes()).hexdigest() != revision:
        raise SystemExit(RELOAD_EXIT)


def rotate_trials(queue, trials, launch_root, tag_prefix):
    """Keep other queue entries in place and try the least recently launched trial first."""
    def last_launch(mode):
        prefix = tag_prefix + mode + '-'
        times = []
        for attempt in launch_root.glob(prefix + '*'):
            if not attempt.name.removeprefix(prefix).isdigit():
                continue
            try:
                times.append((attempt / 'launch.json').stat().st_mtime_ns)
            except FileNotFoundError:
                continue
        return max(times, default=0)

    rotated = iter(sorted((row for row in queue if row[0] in trials), key=lambda row: last_launch(row[0])))
    return [next(rotated) if row[0] in trials else row for row in queue]
