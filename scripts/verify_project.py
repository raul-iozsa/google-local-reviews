"""Read-only consistency checks of saved outputs, corrections, charts and the audit.

It checks that outputs agree with each other, not that the statistics are valid."""
import argparse
import ast
import csv
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True

from append_corrections import MAPPING, boundaries, marker_of, render_report
from artifact_values import (CHART_INPUTS, METRIC_DOCUMENTS, bert_effects, digest,
                             metric_pattern, metric_row, readme_values,
                             reliability_rows)

ROOT = Path(__file__).resolve().parents[1]


def active_report(text):
    """The report without its correction blocks, which keep historical wording on purpose."""
    return re.sub(r"\[\[CORRECTION:([^:\n]+):BEGIN\]\].*?\[\[CORRECTION:\1:END\]\]",
                  "", text, flags=re.S)


def run_checks(root=ROOT):
    root = Path(root).resolve()
    checks = []

    def check(name, action):
        try:
            ok = bool(action())
            detail = "" if ok else "condition not met"
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        checks.append((name, ok, detail))

    def read(relative):
        return (root / relative).read_text(encoding="utf-8")

    for correction, report in MAPPING.items():
        def current(c=correction, r=report):
            body = read("results/" + r)
            correction_text = read("results/corrections/" + c)
            begin, end = boundaries(c)
            return (body.count(begin) == body.count(end) == 1
                    and len(re.findall(r"^" + re.escape(marker_of(correction_text)) + r"\s*$", body, re.M)) == 1
                    and render_report(body, correction_text, c) == body)
        check("current complete correction: " + correction, current)

    def helper_succeeds():
        process = subprocess.run([sys.executable, "-B", str(root / "scripts/append_corrections.py"),
                                  "--root", str(root), "--check"],
                                 capture_output=True, timeout=30)
        return process.returncode == 0
    check("correction helper succeeds in read-only check mode", helper_succeeds)

    def current_labels():
        text = active_report(read("results/06_phase6_gap_report.txt"))
        forbidden = (r"^EXTREME DISAGREEMENTS -- and who is actually wrong\s*$",
                     r"->\s*the REVIEW contradicts its own rating",
                     r"reviewer contradicts self", r"\(VADER misread\)")
        return (text.count("EXTREME DISAGREEMENTS -- where the two models land") == 1
                and not any(re.search(p, text, flags=re.M | re.I) for p in forbidden)
                and "both models read it as POSITIVE (NOT proof the reviewer erred)" in text)
    check("Phase 6 active headings and labels are current", current_labels)
    check("Phase 6 language limitation included once", lambda:
          read("results/06_phase6_gap_report.txt").count("Status: INCONCLUSIVE.") == 1)
    check("Phase 5 active report does not claim training adds nothing", lambda:
          not re.search(r"TRAINING BUYS NOTHING|in-corpus training does not help|not competing fairly",
                        active_report(read("results/05_phase5_sentiment_comparison_report.txt")), re.I))
    check("closure report has current predictive wording", lambda:
          "alike. But" not in read("results/04a_phase4_closure_report.txt")
          and "YES in the average, NO in the individual case" not in read("results/04a_phase4_closure_report.txt"))
    for filename, marker in (("03_phase3_state_comparison_report.txt", "RELIABILITY CHECK"),
                             ("06_phase6_gap_report.txt", "STATE GAP -- does the text"),
                             ("06_phase6_gap_report.txt", "BERT CHECK --"),
                             ("04a_phase4_closure_report.txt", "A6 --")):
        check("single generated section: " + marker, lambda f=filename, m=marker: read("results/" + f).count(m) == 1)

    for document, counts in METRIC_DOCUMENTS.items():
        label = "README" if document == "README.md" else document
        for key, count in counts.items():
            def field_current(d=document, k=key, n=count):
                matches = metric_pattern(k).findall(read(d))
                expected = readme_values(root)[k]
                return len(matches) == n and all(m[1] == expected for m in matches)
            check(f"{label} labeled metric: {key}", field_current)
        check(f"{label} has no unexpected metric fields", lambda d=document, c=counts:
              all(not metric_pattern(k).search(read(d)) for k in readme_values(root) if k not in c))
        # A line starting with "<!--" begins a raw HTML block in Markdown and breaks lists.
        check(f"{label} has no line starting with a metric field", lambda d=document:
              not re.search(r"^[ \t]*<!-- metric:", read(d), re.M))

    check("state-gap spread in report matches saved state table", lambda:
          re.findall(r"Standardized gap spread \(max-min\):\s*([\d.]+)",
                     active_report(read("results/06_phase6_gap_report.txt")))
          == [readme_values(root)["state_range"]])

    def combined_current():
        with (root / "results/csv/reliability_contrast.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.reader(f)) == reliability_rows(root / "results/csv")
    check("combined reliability CSV matches source metrics", combined_current)

    def bert_report_current():
        text = active_report(read("results/06_phase6_gap_report.txt"))
        effects = bert_effects(root)
        for test, key in (("A", "A_grim_minus_reference"), ("B", "B_cold10_minus_warm10")):
            rows = re.findall(r"TEST " + test + r"\s+[^\n]*?VADER\s+([+\-\d.]+)\s+BERT\s+([+\-\d.]+)", text)
            if len(rows) != 1 or tuple(float(v) for v in rows[0]) != effects[key]:
                return False
        return True
    check("BERT report contrasts match CSV", bert_report_current)

    def reliability_report_current(phase):
        filename = "03_phase3_state_comparison_report.txt" if phase == 3 else "06_phase6_gap_report.txt"
        body = active_report(read("results/" + filename))
        metrics = metric_row(root, phase)
        patterns = {
            "split_half_observed": r"median rho(?: over \d+ splits)?\s*[:=]\s*([+\-\d.]+)",
            "spearman_brown_full": r"Spearman-Brown[^\n]*:\s*([+\-\d.]+)",
            "noise_only_expected": (r"expected from sampling noise alone[^\n]*:\s*([+\-\d.]+)" if phase == 3
                                    else r"expected if sampling noise were all\s*:\s*([+\-\d.]+)"),
        }
        for key, pattern in patterns.items():
            found = re.findall(pattern, body)
            if len(found) != 1 or float(found[0]) != float(f"{float(metrics[key]):.3f}"):
                return False
        return True
    for phase in (3, 6):
        check(f"Phase {phase} reliability report matches CSV", lambda p=phase: reliability_report_current(p))

    for name, inputs in CHART_INPUTS.items():
        def chart_current(n=name, expected=inputs):
            manifest = json.loads(read("results/charts/manifest.json"))
            record = manifest["charts"][n]
            return (manifest["schema"] == 1
                    and set(manifest["charts"]) == set(CHART_INPUTS)
                    and manifest["renderer_sha256"] == digest(root / "scripts/make_charts.py")
                    and record["inputs"] == {i: digest(root / f"results/csv/{i}.csv") for i in expected}
                    and record["png_sha256"] == digest(root / f"results/charts/{n}.png")
                    and record["title_subtitle_overlap"] is False)
        check("chart input/output hashes and layout: " + name, chart_current)

    def reference_valid():
        with (root / "results/state_review_totals.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        states = [r['state'] for r in rows]
        return len(rows) == len(set(states)) == 52 and sum(int(r['total_reviews_full_corpus']) for r in rows) == 666324103
    check("reference CSV has 52 unique entries and expected total", reference_valid)

    def scripts_parse():
        for path in (root / "scripts").glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.name)
        return True
    check("all Python scripts parse", scripts_parse)
    check("project scripts do not point at original Desktop outputs", lambda:
          all(not re.search(r"[A-Za-z]:\\+Users\\+[^\\]+\\+Desktop\\+google_local_project", p.read_text(encoding="utf-8"))
              for p in (root / "scripts").glob("*.py")))
    audit = root / 'results/audit_v2'
    if audit.exists():
        def completed_audit_current():
            from completed_audit_summary import documents_current
            return documents_current(root)
        check('completed human-audit archive and summaries agree', completed_audit_current)
        def audit_valid():
            from audit_common import validate_package
            validate_package(audit)
            return True
        def audit_predictions_valid():
            from audit_common import validate_package
            from analyze_audit_sample import validate_predictions
            manifest, sheets, _ = validate_package(audit)
            validate_predictions(audit, manifest, sheets)
            return True
        check('human audit sample integrity and matched pairs', audit_valid)
        check('human audit complete model predictions', audit_predictions_valid)
        if (root / 'results/audit_v2/addendum_20260928').exists():
            def addendum_current():
                from audit_addendum import is_current
                return is_current(root)
            check('human-audit addendum recomputes and documents match', addendum_current)
    return checks


def format_checks(checks):
    lines = ["SAVED-OUTPUT CONSISTENCY CHECKS (not statistical certification)"]
    lines.extend(("PASS  " if ok else "FAIL  ") + name + (" -- " + detail if not ok else "")
                 for name, ok, detail in checks)
    lines.append(f"{sum(ok for _, ok, _ in checks)}/{len(checks)} passed")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    checks = run_checks(args.root)
    print(format_checks(checks), end="")
    return int(any(not ok for _, ok, _ in checks))


if __name__ == "__main__":
    raise SystemExit(main())
