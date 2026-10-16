"""Insert or replace the maintained correction block in each report.

--check verifies without writing."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {
    "01_correction.txt": "01_load_and_verify_report.txt",
    "04a_correction.txt": "04a_phase4_closure_report.txt",
    "04b_correction.txt": "04b_phase4_responses_report.txt",
    "05_correction.txt": "05_phase5_sentiment_comparison_report.txt",
    "06_correction.txt": "06_phase6_gap_report.txt",
}


def marker_of(text):
    return next((line.strip() for line in text.splitlines()
                 if line.strip() and not set(line.strip()) <= {"=", "-"}), None)


def boundaries(name):
    return f"[[CORRECTION:{name}:BEGIN]]", f"[[CORRECTION:{name}:END]]"


def render_report(report, correction, name):
    """Pure transformation, also used by the read-only verifier."""
    heading = marker_of(correction)
    if not heading:
        raise ValueError(f"Empty correction: {name}")
    start, end = boundaries(name)
    block = start + "\n" + correction.strip() + "\n" + end
    if start in report or end in report:
        if report.count(start) != 1 or report.count(end) != 1:
            raise ValueError(f"Duplicated or incomplete correction boundaries: {name}")
        lo, hi = report.index(start), report.index(end)
        if hi < lo:
            raise ValueError(f"Reversed correction boundaries: {name}")
        return report[:lo] + block + report[hi + len(end):]
    matches = list(re.finditer(r"^" + re.escape(heading) + r"\s*$", report, re.M))
    if len(matches) > 1:
        raise ValueError(f"Multiple legacy corrections: {name}")
    if matches:
        lo = matches[0].start()
        prefix = re.sub(r"(?:\n[=\-]+\s*)$", "", report[:lo])
        if re.search(r"^STATE GAP --|^Q\d+ --", report[lo:], re.M):
            raise ValueError(f"Legacy correction includes generated results: {name}")
        report = prefix
    return report.rstrip() + "\n\n" + block + "\n"


def apply_corrections(root=ROOT, check=False):
    root = Path(root)
    pending = []
    # Validate all inputs before writing any output.
    for name, report_name in MAPPING.items():
        correction = (root / "results/corrections" / name).read_text(encoding="utf-8")
        path = root / "results" / report_name
        before = path.read_text(encoding="utf-8")
        after = render_report(before, correction, name)
        if before != after:
            pending.append((path, after))
    if not check:
        for path, after in pending:
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(after, encoding="utf-8")
            temp.replace(path)
    return [path.name for path, _ in pending]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        changed = apply_corrections(args.root, args.check)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(("Outdated: " if args.check else "Updated: ") + (", ".join(changed) or "none"))
    return int(args.check and bool(changed))


if __name__ == "__main__":
    raise SystemExit(main())
