"""Independent arithmetic cross-check and explicitly exploratory summaries."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

RUN=Path(__file__).resolve().parents[1]/'inputs'
OUT=Path(__file__).resolve().parents[1]
def read(name):
    with (RUN/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
main=read('labelling_sheet.csv'); key={r['item_id']:r for r in read('_hidden_metadata.csv')}
pred=json.loads((RUN/'_hidden_predictions.json').read_text(encoding='utf-8'))['predictions']
primary=json.loads((OUT/'analysis_results.json').read_text(encoding='utf-8'))
known_discussions=['Going out of business','Ate one of my sliders before taking a second to snag a pic',
                  'Not what I expected but ok','I hope you have a pleasant long, busy, holiday weekend']
known_ids={r['item_id'] for r in main if any(s.lower() in r['review_text'].lower() for s in known_discussions)}
valid={'positive','negative','neutral'}
def details(rows):
    eligible=[r for r in rows if r['sentiment'] in valid]
    joint=Counter()
    for r in eligible:
        p=pred[r['item_id']]; h=r['sentiment']
        v=p['vader_label']==h; b=p['bert_label']==h
        joint['both_agree' if v and b else 'vader_only_agrees' if v else 'bert_only_agrees' if b else 'neither_agrees']+=1
    return {'total_n':len(rows),'comparable_n':len(eligible),'joint_agreement':dict(joint),
            'vader_disagreements':sum(pred[r['item_id']]['vader_label']!=r['sentiment'] for r in eligible),
            'bert_disagreements':sum(pred[r['item_id']]['bert_label']!=r['sentiment'] for r in eligible)}

crosscheck={}
for pool in sorted({r['pool'] for r in key.values()}):
    rows=[r for r in main if key[r['item_id']]['pool']==pool]
    d=details(rows); crosscheck[pool]=d
    reference=primary['probability_sample'] if pool=='probability_sample' else primary['diagnostic_panels'][pool]
    assert d['comparable_n']==reference['comparable_n']
    for model in ['vader','bert']: assert d[model+'_disagreements']==reference[model]['disagreements']
random_rows=[r for r in main if key[r['item_id']]['pool']=='probability_sample']
tags={r['item_id']:{t.strip() for t in r['tags'].split(';') if t.strip()} for r in main}
tag_stats={}
for tag in sorted({t for ts in tags.values() for t in ts}):
    tag_stats[tag]={'all_panels_descriptive':details([r for r in main if tag in tags[r['item_id']]]),
                    'probability_sample_only':details([r for r in random_rows if tag in tags[r['item_id']]])}
freeze=json.loads((RUN/'_codebook_freeze.json').read_text(encoding='utf-8'))
sha=lambda name:hashlib.sha256((RUN/name).read_bytes()).hexdigest()
result={'main_labels_sha256':sha('labelling_sheet.csv'),
    'labels':dict(Counter(r['sentiment'] for r in main)),
    'rows_with_tags':sum(bool(v) for v in tags.values()),
    'rows_with_notes':sum(bool(r['notes']) for r in main),
    'rows_with_implied_stars':sum(bool(r['implied_stars_optional']) for r in main),
    'pilot_hash_matches_freeze':freeze['pilot_labels_sha256']==sha('pilot_sheet.csv'),
    'crosschecks':crosscheck,'exploratory_tag_summaries':tag_stats,
    'known_discussed_items_found':len(known_ids),
    'known_discussed_items_in_random_sample':sum(r['item_id'] in known_ids for r in random_rows),
    'random_sample_excluding_known_discussed_items':details([r for r in random_rows if r['item_id'] not in known_ids]),
    'truncation_sensitivity':{scope:{flag:details([r for r in rows if (key[r['item_id']]['bert_truncated']=='1')==flag]) for flag in [False,True]}
                             for scope,rows in [('random_sample',random_rows),('extremes',[r for r in main if key[r['item_id']]['pool']=='panel_extremes'])]}}
assert result['main_labels_sha256']==primary['main_labels_sha256']
with (OUT/'exploratory_recheck.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
