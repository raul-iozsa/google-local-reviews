"""Regression tests for output-consistency failures. Each runs on a disposable copy."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from append_corrections import apply_corrections, boundaries, render_report
from artifact_values import metric_pattern
from verify_project import run_checks


class OutputConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / ".test-runs"
        self.base.mkdir(exist_ok=True)
        self.fixture = self.base / uuid.uuid4().hex
        self.fixture.mkdir()
        for name in ("scripts", "results", "docs"):
            shutil.copytree(ROOT / name, self.fixture / name,
                            ignore=shutil.ignore_patterns("__pycache__", ".audit-incomplete-*"))
        shutil.copy2(ROOT / "README.md", self.fixture / "README.md")

    def tearDown(self):
        # Verify the resolved target is this test's child before recursive cleanup.
        target = self.fixture.resolve()
        self.assertEqual(target.parent, self.base.resolve())
        self.assertNotEqual(target, ROOT.resolve())
        shutil.rmtree(target)
        if not any(self.base.iterdir()):
            self.base.rmdir()

    def edit(self, relative, old, new):
        path = self.fixture / relative
        before = path.read_text(encoding="utf-8")
        self.assertIn(old, before)
        path.write_text(before.replace(old, new), encoding="utf-8")

    def failures(self):
        return {name for name, ok, _ in run_checks(self.fixture) if not ok}

    def snapshot(self):
        return {p.relative_to(self.fixture).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.fixture.rglob("*") if p.is_file()}

    def test_clean_project_passes_and_verifier_is_read_only(self):
        before = self.snapshot()
        self.assertEqual(self.failures(), set())
        self.assertEqual(self.snapshot(), before)

    def test_wrong_readme_reliability_fails(self):
        self.edit("README.md", "≈0.90", "≈0.20")
        self.assertIn("README labeled metric: p6_full", self.failures())

    def test_unrelated_number_cannot_mask_wrong_labeled_value(self):
        path = self.fixture / "README.md"
        text = metric_pattern("p3_full").sub(lambda m: m[1] + "0.100" + m[3], path.read_text(encoding="utf-8"))
        path.write_text(text + "\nHistorical unrelated number: 0.616.\n", encoding="utf-8")
        self.assertIn("README labeled metric: p3_full", self.failures())

    def test_wrong_summary_value_fails_even_if_finding_is_right(self):
        path = self.fixture / "README.md"
        text = path.read_text(encoding="utf-8")
        summary, rest = text.split("## Findings", 1)
        summary = metric_pattern("closure_auc_range").sub(lambda m: m[1] + "0.73–0.78" + m[3], summary)
        path.write_text(summary + "## Findings" + rest, encoding="utf-8")
        self.assertIn("README labeled metric: closure_auc_range", self.failures())

    def test_wrong_or_extra_number_in_docs_fails(self):
        path = self.fixture / "docs/FINDINGS.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(metric_pattern("p3_split").sub(lambda m: m[1] + "0.999" + m[3], text), encoding="utf-8")
        self.assertIn("docs/FINDINGS.md labeled metric: p3_split", self.failures())
        path.write_text(text + "\n<!-- metric:bert_grim -->+0.10<!-- /metric:bert_grim -->\n", encoding="utf-8")
        self.assertIn("docs/FINDINGS.md has no unexpected metric fields", self.failures())

    def test_metric_field_at_line_start_fails(self):
        path = self.fixture / "README.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("Vermont falls from <!-- metric:vermont_shift -->",
                                     "Vermont falls from\n  <!-- metric:vermont_shift -->", 1), encoding="utf-8")
        self.assertIn("README has no line starting with a metric field", self.failures())

    def test_old_active_heading_fails_despite_nearby_caveat(self):
        self.edit("results/06_phase6_gap_report.txt",
                  "EXTREME DISAGREEMENTS -- where the two models land",
                  "EXTREME DISAGREEMENTS -- and who is actually wrong")
        self.assertIn("Phase 6 active headings and labels are current", self.failures())

    def test_helper_failure_is_not_idempotence(self):
        (self.fixture / "scripts/append_corrections.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
        self.assertIn("correction helper succeeds in read-only check mode", self.failures())

    def test_changed_correction_same_heading_is_detected_and_replaced(self):
        path = self.fixture / "results/corrections/04a_correction.txt"
        path.write_text(path.read_text(encoding="utf-8") + "\nNew test qualification.\n", encoding="utf-8")
        self.assertIn("current complete correction: 04a_correction.txt", self.failures())
        self.assertEqual(apply_corrections(self.fixture), ["04a_phase4_closure_report.txt"])
        self.assertEqual(self.failures(), set())
        before = self.snapshot()
        self.assertEqual(apply_corrections(self.fixture), [])
        self.assertEqual(self.snapshot(), before)

    def test_equal_length_correction_edit_is_detected(self):
        path = self.fixture / "results/04a_phase4_closure_report.txt"
        original = path.read_text(encoding="utf-8")
        self.assertIn("Within year of last review", original)
        changed = original.replace("Within year of last review", "Within YEAR of last review")
        self.assertEqual(len(original), len(changed))
        path.write_text(changed, encoding="utf-8")
        self.assertIn("current complete correction: 04a_correction.txt", self.failures())

    def test_missing_language_correction_fails(self):
        self.edit("results/06_phase6_gap_report.txt", "Status: INCONCLUSIVE.", "Status: OMITTED.")
        self.assertIn("Phase 6 language limitation included once", self.failures())

    def test_duplicate_generated_section_fails(self):
        path = self.fixture / "results/06_phase6_gap_report.txt"
        path.write_text(path.read_text(encoding="utf-8") + "\nSTATE GAP -- does the text\n", encoding="utf-8")
        self.assertIn("single generated section: STATE GAP -- does the text", self.failures())

    def test_duplicate_unbounded_correction_fails(self):
        path = self.fixture / "results/04a_phase4_closure_report.txt"
        correction = (self.fixture / "results/corrections/04a_correction.txt").read_text(encoding="utf-8")
        path.write_text(path.read_text(encoding="utf-8") + "\n" + correction, encoding="utf-8")
        self.assertIn("current complete correction: 04a_correction.txt", self.failures())

    def test_changed_chart_input_requires_regeneration(self):
        path = self.fixture / "results/csv/p6_bert_check.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertIn("chart input/output hashes and layout: 12_bert_check", self.failures())

    def test_png_change_is_detected(self):
        path = self.fixture / "results/charts/12_bert_check.png"
        path.write_bytes(path.read_bytes() + b"stale")
        self.assertIn("chart input/output hashes and layout: 12_bert_check", self.failures())

    def test_renderer_change_requires_regeneration(self):
        path = self.fixture / "scripts/make_charts.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# changed renderer\n", encoding="utf-8")
        self.assertIn("chart input/output hashes and layout: 12_bert_check", self.failures())

    def test_stale_combined_metrics_fail(self):
        self.edit("results/csv/reliability_contrast.csv", "0.8956", "0.8971")
        self.assertIn("combined reliability CSV matches source metrics", self.failures())

    def test_stale_bert_report_fails(self):
        self.edit("results/06_phase6_gap_report.txt", "BERT -0.289", "BERT -0.349")
        self.assertIn("BERT report contrasts match CSV", self.failures())

    def test_invalid_totals_fail(self):
        path = self.fixture / "results/state_review_totals.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        self.assertIn("reference CSV has 52 unique entries and expected total", self.failures())

    def test_cli_returns_failure_for_bad_readme(self):
        self.edit("README.md", "≈0.90", "≈0.20")
        result = subprocess.run([sys.executable, "-B", str(self.fixture / "scripts/verify_project.py")], capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_finalizer_repairs_outputs_and_second_run_is_identical(self):
        self.edit("README.md", "≈0.90", "≈0.20")
        self.edit("results/csv/reliability_contrast.csv", "0.8956", "0.8971")
        # Finalization must repair the addendum before reading its derived metrics.
        self.edit("docs/HUMAN_AUDIT.md", "28/233", "27/233")
        addendum = self.fixture / 'results/audit_v2/addendum_20260928/addendum_results.json'
        data = json.loads(addendum.read_text(encoding='utf-8'))
        data['models']['vader']['per_class']['negative']['agreed'] = 0
        addendum.write_text(json.dumps(data), encoding='utf-8')
        correction = self.fixture / "results/corrections/04a_correction.txt"
        correction.write_text(correction.read_text(encoding="utf-8") + "\nUpdated qualification.\n", encoding="utf-8")
        command = [sys.executable, "-B", str(self.fixture / "scripts/finalize_outputs.py")]
        first = subprocess.run(command, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stdout.decode(errors="replace") + first.stderr.decode(errors="replace"))
        self.assertEqual(self.failures(), set())
        before = self.snapshot()
        second = subprocess.run(command, capture_output=True)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(self.snapshot(), before)


class CorrectionMigrationTests(unittest.TestCase):
    def test_first_append_and_repeated_append(self):
        once = render_report("Generated results\n", "===\nCorrection heading\n===\nNote\n", "sample")
        self.assertEqual(render_report(once, "===\nCorrection heading\n===\nNote\n", "sample"), once)

    def test_legacy_heading_does_not_hide_revised_body(self):
        old = "Generated results\n\n===\nCorrection heading\n===\nOld text\n"
        after = render_report(old, "===\nCorrection heading\n===\nNew text\n", "sample")
        self.assertNotIn("Old text", after)
        self.assertIn("New text", after)
        self.assertIn("Generated results", after)

    def test_duplicate_or_incomplete_boundaries_fail(self):
        begin, end = boundaries("sample")
        for bad in (begin, end, begin + begin + end, end + begin):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                render_report(bad, "Correction heading\nBody", "sample")

    def test_embedded_generated_legacy_data_is_not_silently_deleted(self):
        with self.assertRaises(ValueError):
            render_report("Generated\nCorrection heading\nSTATE GAP -- generated table", "Correction heading\nNew", "sample")


if __name__ == "__main__":
    unittest.main()
