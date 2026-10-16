"""Regression cases for actual sampler defects and the completed analysis path."""
import json
from pathlib import Path
import random
import sys
import shutil
import uuid
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_common as c
import build_audit_sample as b
import analyze_audit_sample as a
from score_audit_sample import atomic_json

def replace_csv(path,rows):
    path.unlink()
    c.write_csv(path,list(rows[0]),rows)

def fixture(root):
    rows=[]; meta=[]; rid=0
    for pool,count in c.EXPECTED.items():
        for i in range(count):
            rid+=1; text=f'Review {rid:04}: '+('x'*120)
            rows.append(dict(zip(c.SHEET_FIELDS,[f'T{rid}',text,'','','',''])))
            meta.append(dict(item_id=f'T{rid}',review_id=str(rid),pool=pool,
                inclusion_probability='0.025' if pool=='probability_sample' else '',
                true_stars='5',vader_compound='0.5',gmap_id=f'B{rid}',bert_tokens='40',bert_truncated='0',
                in_second_annotator_set='1' if rid<=50 else '0',pair_id=f'P{i}' if 'coldwarm' in pool else ''))
    pilot=[dict(zip(c.SHEET_FIELDS,[f'P{i}',f'Pilot {i}','positive','','',''])) for i in range(25)]
    pk=[dict(item_id=f'P{i}',review_id=str(1000+i),true_stars='5',vader_compound='0.5') for i in range(25)]
    sheets={'labelling_sheet.csv':rows,'pilot_sheet.csv':pilot,'labelling_sheet_annotator2.csv':rows[:50]}
    for name,data in sheets.items(): c.write_csv(root/name,c.SHEET_FIELDS,data)
    c.write_csv(root/'_hidden_metadata.csv',list(meta[0]),meta)
    c.write_csv(root/'_hidden_pilot_metadata.csv',list(pk[0]),pk)
    (root/'CODEBOOK.md').write_text('Frozen rubric',encoding='utf-8')
    (root/'ANALYSIS_PLAN.md').write_text('Prespecified analysis',encoding='utf-8')
    m=dict(frame={'eligible_after_exclusions':10000},excluded_review_ids=[99999],model=c.MODEL,model_revision='abc',max_tokens=256,
        sheet_identities={name:c.identities(data) for name,data in sheets.items()},
        immutable_hashes={name:c.digest(root/name) for name in ['_hidden_metadata.csv','_hidden_pilot_metadata.csv','ANALYSIS_PLAN.md']})
    (root/'_hidden_manifest.json').write_text(json.dumps(m),encoding='utf-8')
    predictions={r['item_id']:dict(text_sha256=c.text_hash(r['review_text']),bert_probabilities=[0,0,0,0,1],
        bert_label='positive',bert_forced='positive',vader_label='positive') for r in rows}
    atomic_json(root/'_hidden_predictions.json',dict(model=c.MODEL,model_revision='abc',max_tokens=256,
        manifest_sha256=c.digest(root/'_hidden_manifest.json'),predictions=predictions))

class HumanAuditTests(unittest.TestCase):
    def setUp(self):
        self.base=ROOT/'.audit-test-runs'; self.base.mkdir(exist_ok=True)
        self.root=self.base/uuid.uuid4().hex; self.root.mkdir(); fixture(self.root)
    def tearDown(self):
        self.assertEqual(self.root.resolve().parent,self.base.resolve())
        shutil.rmtree(self.root)
        if not any(self.base.iterdir()): self.base.rmdir()
    def metadata_edit(self,edit):
        path=self.root/'_hidden_metadata.csv'; rows=c.read_csv(path); edit(rows); replace_csv(path,rows)
        m=json.loads((self.root/'_hidden_manifest.json').read_text()); m['immutable_hashes'][path.name]=c.digest(path)
        (self.root/'_hidden_manifest.json').write_text(json.dumps(m))
    def fill_main(self):
        for name in ['labelling_sheet.csv','labelling_sheet_annotator2.csv']:
            path=self.root/name; rows=c.read_csv(path)
            for r in rows: r['sentiment']='positive'
            replace_csv(path,rows)
    def test_valid_package(self): c.validate_package(self.root)
    def test_refuses_existing_run_before_work(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaises(FileExistsError): b.build(self.root)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
    def test_failed_publish_does_not_create_destination(self):
        target=self.root/'new'
        def fail(stage): (stage/'partial').write_text('partial'); raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError): b.publish(target,fail)
        self.assertFalse(target.exists()); self.assertFalse(list(self.root.glob('.audit-incomplete-*')))
    def test_reservoir_reproducible_and_unique(self):
        rows=[(i,) for i in range(1000)]
        x=b.reservoir(rows,275,random.Random(42)); y=b.reservoir(rows,275,random.Random(42))
        self.assertEqual(x,y); self.assertEqual(len(set(x[0])),275); self.assertEqual(x[1],1000)
    def test_reservoir_does_not_take_only_first_rows(self):
        picked,n,_=b.reservoir([(i,) for i in range(1000)],275,random.Random(42))
        self.assertGreater(max(picked),900)
    def test_shortage_fails(self):
        with self.assertRaises(ValueError): b.reservoir([(1,)],2,random.Random(1))
        with self.assertRaises(ValueError): b.cap([(1,'a',5,'same',0)]*4,random.Random(1),3)
    def test_emoji_and_wrapped_excerpts(self):
        report='[Cafe]  VADER -0.9  BERT 2.0 stars\n   so fire 🔥🔥\n\n[Shop]  VADER -0.8  BERT 1.0 stars\n   extraordinarylong\n   word\n'
        self.assertEqual(b.resolve_excerpts(b.report_excerpts(report),[(1,'so fire 🔥🔥'),(2,'extraordinarylongword indeed')]),{1,2})
    def test_missing_exposure_fails(self):
        with self.assertRaises(ValueError): b.resolve_excerpts(['missing'],[(1,'other text')])
    def test_registry_accumulates(self):
        (self.root/'results').mkdir(); c.record_exposures(self.root,[1]); c.record_exposures(self.root,[2])
        self.assertEqual(json.loads((self.root/'results/audit_exposures.json').read_text())['review_ids'],[1,2])
    def test_exposed_item_rejected(self):
        self.metadata_edit(lambda rows:rows[0].update(review_id='99999'))
        with self.assertRaisesRegex(ValueError,'exposed'): c.validate_package(self.root)
    def test_incorrect_probability_rejected(self):
        self.metadata_edit(lambda rows:rows[0].update(inclusion_probability='0.9'))
        with self.assertRaisesRegex(ValueError,'probability'): c.validate_package(self.root)
    def test_real_matching_and_shortage(self):
        cold=[(i,'x'*(100+i),5,f'C{i}',0) for i in range(50)]
        warm=[(100+i,'x'*(100+i),5,f'W{i}',0) for i in range(50)]
        pairs=b.match_lengths(cold,warm,random.Random(1))
        self.assertEqual(len(pairs),50)
        self.assertTrue(all(abs(len(x[1])-len(y[1]))<=10 for x,y in pairs))
        with self.assertRaises(ValueError): b.match_lengths(cold,[(999,'x'*399,5,'W',0)],random.Random(1))
    def test_bad_pair_rejected(self):
        self.metadata_edit(lambda rows:next(r for r in rows if 'coldwarm' in r['pool']).update(pair_id='missing'))
        with self.assertRaises(ValueError): c.validate_package(self.root)
    def test_changed_text_rejected_but_labels_allowed(self):
        self.fill_main(); c.validate_package(self.root)
        path=self.root/'labelling_sheet.csv'; rows=c.read_csv(path); rows[0]['review_text']='changed'; replace_csv(path,rows)
        with self.assertRaisesRegex(ValueError,'text'): c.validate_package(self.root)
    def test_prediction_coverage_rejected(self):
        path=self.root/'_hidden_predictions.json'; data=json.loads(path.read_text()); data['predictions'].pop('T1'); path.write_text(json.dumps(data))
        m,s,k=c.validate_package(self.root)
        with self.assertRaisesRegex(ValueError,'exactly every'): a.validate_predictions(self.root,m,s)
    def test_blank_labels_refused(self):
        a.freeze(self.root)
        with self.assertRaisesRegex(ValueError,'valid sentiment'): a.analyze(self.root,self.root/'analysis.json')
    def test_wrong_saved_vader_label_rejected(self):
        path=self.root/'_hidden_predictions.json'; data=json.loads(path.read_text())
        data['predictions']['T1']['vader_label']='negative'; path.write_text(json.dumps(data))
        m,s,k=c.validate_package(self.root)
        with self.assertRaisesRegex(ValueError,'VADER'): a.validate_predictions(self.root,m,s)
    def test_partial_second_labels_not_silently_ignored(self):
        a.freeze(self.root); self.fill_main()
        path=self.root/'labelling_sheet_annotator2.csv'; rows=c.read_csv(path); rows[0]['sentiment']=''; replace_csv(path,rows)
        with self.assertRaisesRegex(ValueError,'valid sentiment'):
            a.analyze(self.root,self.root/'analysis.json',allow_single=True)
    def test_freeze_after_main_labels_refused(self):
        self.fill_main()
        with self.assertRaisesRegex(ValueError,'before any'): a.freeze(self.root)
    def test_changed_frozen_codebook_rejected(self):
        a.freeze(self.root); self.fill_main(); (self.root/'CODEBOOK.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Frozen'): a.analyze(self.root,self.root/'analysis.json')
    def test_completed_analysis_keeps_panels_separate(self):
        a.freeze(self.root); self.fill_main(); out=self.root/'analysis.json'; a.analyze(self.root,out)
        data=json.loads(out.read_text())
        self.assertEqual(data['probability_sample']['n'],250)
        self.assertEqual(data['probability_sample']['bert']['disagreements'],0)
        self.assertEqual(data['agreement']['fraction'],1)
        self.assertIsNone(data['agreement']['cohen_kappa'])
        self.assertEqual(len(data['diagnostic_panels']),4)
        self.assertEqual(data['coldwarm_exploratory']['positive_fraction_cold_minus_warm'],0)
        with self.assertRaises(FileExistsError): a.analyze(self.root,out)
    def test_mixed_and_unknown_are_not_model_successes(self):
        a.freeze(self.root); self.fill_main()
        path=self.root/'labelling_sheet.csv'; rows=c.read_csv(path)
        rows[0]['sentiment']='mixed'; rows[1]['sentiment']='cannot_tell'; replace_csv(path,rows)
        a.analyze(self.root,self.root/'analysis.json')
        data=json.loads((self.root/'analysis.json').read_text())['probability_sample']
        self.assertEqual(data['comparable_n'],248); self.assertEqual(data['excluded_from_model_error_n'],2)
    def test_wilson_boundary(self):
        lo,hi=a.wilson(0,250); self.assertAlmostEqual(lo,0); self.assertGreater(hi,0)
        self.assertIsNone(a.wilson(0,0))

if __name__=='__main__': unittest.main()
