"""Regression cases for the post-hoc human-audit addendum."""
import json
from pathlib import Path
import shutil
import sys
import uuid
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_addendum as ad


class AddendumTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / '.addendum-test-runs'
        self.base.mkdir(exist_ok=True)
        self.root = self.base / uuid.uuid4().hex
        self.root.mkdir()
        self.addCleanup(self.cleanup_fixture)
        shutil.copytree(ROOT / ad.ARCHIVE, self.root / ad.ARCHIVE)
        shutil.copytree(ROOT / ad.OUT, self.root / ad.OUT)
        for name in ad.DOCUMENTS + ('README.md',):
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.root / name)

    def cleanup_fixture(self):
        self.assertEqual(self.root.resolve().parent, self.base.resolve())
        shutil.rmtree(self.root)
        if not any(self.base.iterdir()):
            self.base.rmdir()

    def test_saved_copy_is_current(self):
        self.assertTrue(ad.is_current(self.root))

    def test_rewrite_is_idempotent(self):
        before = {n: (self.root / n).read_text(encoding='utf-8') for n in ad.DOCUMENTS}
        ad.write(self.root)
        self.assertEqual(before, {n: (self.root / n).read_text(encoding='utf-8') for n in ad.DOCUMENTS})

    def test_altered_result_is_detected(self):
        path = self.root / ad.OUT / 'addendum_results.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['discussed']['n'] = 4
        path.write_text(json.dumps(data), encoding='utf-8')
        self.assertFalse(ad.is_current(self.root))

    def test_stale_document_block_is_detected(self):
        path = self.root / ad.DOCUMENTS[0]
        path.write_text(path.read_text(encoding='utf-8').replace('28/233', '27/233'), encoding='utf-8')
        self.assertFalse(ad.is_current(self.root))

    def test_missing_document_block_is_detected(self):
        path = self.root / ad.DOCUMENTS[0]
        text = path.read_text(encoding='utf-8')
        start, stop = text.index(ad.BEGIN), text.index(ad.END) + len(ad.END)
        path.write_text(text[:start] + text[stop:], encoding='utf-8')
        self.assertFalse(ad.is_current(self.root))

    def test_stale_or_missing_headline_is_detected(self):
        path = self.root / 'README.md'
        text = path.read_text(encoding='utf-8')
        path.write_text(text.replace('VADER agreed on 19', 'VADER agreed on 29'), encoding='utf-8')
        self.assertFalse(ad.is_current(self.root))
        start, stop = text.index(ad.HEAD_BEGIN), text.index(ad.HEAD_END) + len(ad.HEAD_END)
        path.write_text(text[:start] + text[stop:], encoding='utf-8')
        self.assertFalse(ad.is_current(self.root))

    def test_archive_tampering_stops_computation(self):
        path = self.root / ad.ARCHIVE / 'inputs/labelling_sheet.csv'
        path.write_bytes(path.read_bytes().replace(b'negative', b'positive', 1))
        with self.assertRaises(ValueError):
            ad.compute(self.root)

    def test_ambiguous_snippet_is_refused(self):
        with patch.object(ad, 'DISCUSSED', [('assistant 2', 'the', None)]):
            with self.assertRaises(ValueError):
                ad.compute(self.root)

    def test_mcnemar_exact_values(self):
        self.assertEqual(ad.mcnemar_exact(0, 0), 1.0)
        self.assertEqual(ad.mcnemar_exact(5, 5), 1.0)
        self.assertAlmostEqual(ad.mcnemar_exact(0, 6), 2 / 64)
        self.assertAlmostEqual(ad.mcnemar_exact(26, 10), 0.011330984183587134)


if __name__ == '__main__':
    unittest.main()
