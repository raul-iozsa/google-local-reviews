"""Refresh corrections, README values, charts and audit summaries from saved results, then verify.

Needs no database access."""
import csv
from pathlib import Path
import subprocess
import sys

from append_corrections import apply_corrections
from artifact_values import METRIC_DOCUMENTS, readme_values, refresh_document, reliability_rows
from completed_audit_summary import refresh_documents
from audit_addendum import write as refresh_addendum
from verify_project import format_checks, run_checks

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        changed = apply_corrections(ROOT)
        print("Corrections updated:", ", ".join(changed) or "none", flush=True)
        with (ROOT / "results/csv/reliability_contrast.csv").open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(reliability_rows(ROOT / "results/csv"))
        refresh_documents(ROOT)
        refresh_addendum(ROOT)
        values = readme_values(ROOT)
        for name, counts in METRIC_DOCUMENTS.items():
            document = ROOT / name
            before = document.read_text(encoding="utf-8")
            after = refresh_document(before, values, counts, name)
            if before != after:
                document.write_text(after, encoding="utf-8")
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/make_charts.py")], check=True)
        checks = run_checks(ROOT)
        result = format_checks(checks)
        (ROOT / "results/verification_checklist.txt").write_text(result, encoding="utf-8")
        print(result, end="")
        return int(any(not ok for _, ok, _ in checks))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        message = f"FINALIZATION FAILED: {exc}\n"
        (ROOT / "results/verification_checklist.txt").write_text(message, encoding="utf-8")
        print(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
