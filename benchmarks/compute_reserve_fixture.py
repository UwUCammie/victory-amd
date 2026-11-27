"""Compile pipeline scheduling tests without a Windows target."""

import argparse
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


TESTS = (
    "draws_promote_early_pipelines_without_claiming_them_twice",
    "pipelines_known_to_take_long_leave_workers_for_the_others",
    "passes_over_the_screen_go_first",
    "waiting_compute_dispatches_go_first",
    "a_pipeline_a_dispatch_waits_for_is_made_next",
    "the_last_worker_is_kept_for_a_waited_for_pipeline",
    "strict_reserve_leaves_the_screen_job_to_a_dedicated_worker",
)

HARNESS = """
extern crate self as tracing;
#[macro_export]
macro_rules! info { ($($arg:tt)*) => {} }
mod library {
    pub fn slow(_: &str) -> bool { false }
}
mod queue {
    use std::collections::VecDeque;
    use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
    use std::sync::{Arc, Condvar, OnceLock};
    static AVAILABLE: Condvar = Condvar::new();
    static SCREEN_USED_RESERVE: AtomicBool = AtomicBool::new(false);
    fn compute_waits() -> bool { true }
    fn screens_first() -> bool { true }
    fn slow_limit() -> usize { 1 }

    struct Pending {
        queue_state: AtomicU8,
        was_slow: AtomicBool,
        made: OnceLock<Option<()>>,
        key: String,
        screen: bool,
        compute: bool,
    }
    impl Pending {
        fn new(_: Vec<()>, _: Option<()>) -> Self {
            Self {
                queue_state: AtomicU8::new(NOT_QUEUED),
                was_slow: AtomicBool::new(false),
                made: OnceLock::new(),
                key: String::new(),
                screen: false,
                compute: false,
            }
        }
    }
"""


def test_function(source, name):
    start = source.index(f"    fn {name}()")
    end = source.index("\n    }", start) + len("\n    }")
    return "    #[test]\n" + source[start:end]


def queue_fixture(source):
    constants = source[source.index("const NOT_QUEUED:"):source.index("/// How many workers may make pipelines")]
    queue = source[source.index("struct Queue {"):source.index("static QUEUE:")]
    workers = source[source.index("fn worker_count("):source.index("/// Starts the workers")]
    tests = [test_function(source, name) for name in TESTS]
    return HARNESS + constants + queue + workers + "\n" + "\n\n".join(tests) + "\n}\n"


def budget_fixture(source):
    start = source.index("fn reserve_wait(")
    end = source.index("\n}", start) + len("\n}")
    test = test_function(source, "late_pipeline_wait_keeps_newer_frame_budget")
    return "use std::time::Duration;\n" + source[start:end] + "\nmod tests {\n    use super::*;\n" + test + "\n}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="checkout containing the pipeline scheduler patch")
    parser.add_argument("--graphics-budget", action="store_true", help="test the late graphics wait budget instead of the queue")
    parser.add_argument("--scratch", type=Path, help="existing directory for the temporary native test executable")
    args = parser.parse_args()
    source = (args.checkout / "crates/victory-gpu/src/pipeline/make.rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="compute-reserve-", dir=args.scratch) as directory:
        root = Path(directory)
        generated = root / "queue.rs"
        binary = root / ("queue.exe" if os.name == "nt" else "queue")
        with generated.open("w", encoding="utf-8", newline="\n") as output:
            output.write(budget_fixture(source) if args.graphics_budget else queue_fixture(source))
        subprocess.run(["rustc", "--edition=2024", "--test", str(generated), "-o", str(binary)], check=True)
        environment = dict(os.environ, VICTORY_PIPELINE_WORKERS="16")
        subprocess.run([str(binary), "--nocapture", "--test-threads=1"], env=environment, check=True)


if __name__ == "__main__":
    main()
