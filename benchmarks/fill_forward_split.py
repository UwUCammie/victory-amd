"""Check the forwarding and submission-cut planners with generated addresses."""

from argparse import ArgumentParser
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def section(text, begin, end):
    start = text.index(begin)
    return text[start:text.index(end, start)]


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    src = args.checkout / "crates/victory-gpu/src"
    host = (src / "host.rs").read_text()
    place = (src / "host/place.rs").read_text()
    cards = (src / "host/card_steps.rs").read_text()
    submission = section(host, "late_threads();\n", "fn execute_own(")
    cut_at = submission.index("card_steps::cut_for(&runs)")
    forward_at = submission.index("place::forward_fills(&runs, &written)")
    snippets = [
        section(host, "fn touches(", "/// Whether anything is in the air."),
        section(host, "type Run<T>", "/// A fence signal on a queue"),
        section(place, "enum View {", "impl View {"),
        section(place, "fn forwards(", "/// [`forwarding`]: before"),
        section(cards, "const BEHIND_PLACED", "/// The bytes of our buffer"),
        section(cards, "const MOST:", "/// How a fill's bytes"),
        section(cards, "enum Does {", "/// Whether a refresh"),
    ]
    fixture = Path(__file__).with_suffix(".rs").read_text()
    with TemporaryDirectory(prefix="goal30-fill-forward-", dir=args.scratch) as temp:
        root = Path(temp)
        source = root / "fixture.rs"
        fixed = str(cut_at < forward_at).lower()
        source.write_text(
            f"const FORWARD_AFTER_CUT: bool = {fixed};\n" + "\n".join(snippets + [fixture]),
            encoding="utf-8", newline="\n",
        )
        exe = root / "fixture"
        subprocess.run(["rustc", "--edition=2024", "-Awarnings", "--test", str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
