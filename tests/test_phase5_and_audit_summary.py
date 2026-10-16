"""Regression tests for confirmed final-review failure modes."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from contextlib import contextmanager
import uuid
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from completed_audit_summary import render, refreshed, checked_results

spec = importlib.util.spec_from_file_location('comparison_test', ROOT/'scripts/run_phase5_compare.py')
compare = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'db_config': SimpleNamespace(DB_PARAMS={})}):
    spec.loader.exec_module(compare)


def cursor(**overrides):
    values = dict(eval_rows=50000, binary_rows=40000, has_vader=50000,
                  has_nb_binary=40000, has_svm_binary=40000, has_nb_5class=50000,
                  has_svm_5class=50000, has_bert=50000, has_bert_forced=50000)
    values.update(overrides)
    cur = MagicMock()
    cur.description = [SimpleNamespace(name=k) for k in values]
    cur.fetchone.return_value = list(values.values())
    return cur


@contextmanager
def workspace_fixture():
    base = ROOT / '.final-review-tests'
    base.mkdir(exist_ok=True)
    target = base / uuid.uuid4().hex
    target.mkdir()
    try:
        yield target
    finally:
        if target.resolve().parent != base.resolve():
            raise ValueError('Unsafe test cleanup path')
        shutil.rmtree(target)
        if not any(base.iterdir()):
            base.rmdir()


class FinalReviewTests(unittest.TestCase):
    def test_three_star_binary_abstention_is_expected(self):
        self.assertEqual(compare.validate_coverage(cursor())['binary_rows'], 40000)

    def test_missing_predictions_stop_before_truncating_existing_report(self):
        for field, count in [('has_vader', 50000), ('has_svm_binary', 40000),
                             ('has_nb_binary', 40000), ('has_nb_5class', 50000),
                             ('has_svm_5class', 50000), ('has_bert', 50000),
                             ('has_bert_forced', 50000)]:
            with self.subTest(field=field), workspace_fixture() as d:
                report = Path(d)/'existing.txt'
                report.write_text('preserve this report', encoding='utf-8')
                conn = MagicMock()
                conn.cursor.return_value = cursor(**{field: count-1})
                with patch.object(compare.psycopg2, 'connect', return_value=conn), \
                     patch.object(compare, 'REPORT_PATH', report):
                    with self.assertRaisesRegex(ValueError, field):
                        compare.main()
                self.assertEqual(report.read_text(), 'preserve this report')

    def test_empty_evaluation_fails(self):
        with self.assertRaisesRegex(ValueError, 'Empty'):
            compare.validate_coverage(cursor(eval_rows=0, binary_rows=0))

    def test_human_summary_repairs_wrong_rate_and_is_idempotent(self):
        block = render(ROOT)
        damaged = block.replace('13.6%', '3.6%')
        self.assertNotEqual(damaged, block)
        self.assertEqual(refreshed(damaged, block), block)
        self.assertEqual(refreshed(block, block), block)

    def test_duplicate_human_summary_is_rejected(self):
        block = render(ROOT)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            refreshed(block+'\n'+block, block)

    def test_modified_archived_analysis_is_rejected(self):
        with workspace_fixture() as d:
            relative = Path('results/audit_v2/analysis_20260927')
            destination = Path(d)/relative
            shutil.copytree(ROOT/relative, destination)
            path = destination/'analysis_results.json'
            data = json.loads(path.read_text())
            data['probability_sample']['vader']['disagreements'] = 0
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'archive changed'):
                checked_results(d)


if __name__ == '__main__':
    unittest.main()
