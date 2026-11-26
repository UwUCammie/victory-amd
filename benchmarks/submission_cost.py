"""Compare a submission helper from two Git revisions using the same synthetic workload."""
import argparse
from pathlib import Path
import statistics
import subprocess
import tempfile


def build(revision, output, workload):
    if workload == "queue":
        path = "crates/victory-gpu/src/queue/behind.rs"
        start, stop, fixture_name = "use std::collections::VecDeque;", "type Recordings =", "queue_front.rs"
    else:
        path = "crates/victory-gpu/src/host.rs"
        start, stop, fixture_name = "fn join_ranges(", "/// Whether anything is in the air.", "submission_ranges.rs"
    source = subprocess.check_output(["git", "show", f"{revision}:{path}"], text=True)
    begin = source.index(start)
    method = source[begin:source.index(stop, begin)].replace("use super::This;", "")
    fixture = Path(__file__).with_name(fixture_name).read_text(encoding="utf-8")
    target = output.with_suffix(".rs")
    target.write_text(fixture.replace("// MEASURED_SOURCE", method), encoding="utf-8", newline="\n")
    subprocess.run(["rustc", "--edition=2024", "-Awarnings", "-O", target, "-o", output], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("candidate")
    parser.add_argument("--workload", choices=("queue", "ranges"), default="queue")
    parser.add_argument("--pairs", type=int, default=8)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("at least one pair is required")
    with tempfile.TemporaryDirectory() as tmp:
        bins = [Path(tmp) / (name + ".exe") for name in ("base", "candidate")]
        for ref, output in zip((args.base, args.candidate), bins):
            build(ref, output, args.workload)
        times = {}
        for pair in range(args.pairs):
            order = (0, 1) if pair % 2 == 0 else (1, 0)
            for index in order:
                for line in subprocess.check_output([bins[index]], text=True).splitlines():
                    case, ns = line.split()
                    times.setdefault(case, [[], []])[index].append(int(ns))
        for name, (base, candidate) in times.items():
            faster = sum(c < b for b, c in zip(base, candidate))
            print(f"{name}: {statistics.median(base):.0f} to {statistics.median(candidate):.0f} ns "
                  f"per batch; candidate faster in {faster}/{args.pairs} pairs")
            print(f"  base {base}\n  candidate {candidate}")


if __name__ == "__main__":
    main()
