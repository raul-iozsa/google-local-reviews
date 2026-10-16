"""Shared integrity checks for immutable audit runs and editable labels."""
import csv
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path

MODEL = 'nlptown/bert-base-multilingual-uncased-sentiment'
MAX_TOKENS = 256
LABELS = {'positive', 'negative', 'neutral', 'mixed', 'cannot_tell'}
TAGS = {'sarcasm','slang_or_emoji','mixed_content','off_topic','not_english',
        'cannot_assess_language','no_sentiment_words','quotes_complaint','very_long'}
SHEET_FIELDS = ['item_id','review_text','sentiment','tags','implied_stars_optional','notes']
EXPECTED = {'probability_sample':250, 'panel_extremes':50,
            'panel_model_disagreement':50, 'panel_coldwarm_cold':50,
            'panel_coldwarm_warm':50}

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, fields, rows):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def record_exposures(root, review_ids):
    """Append published IDs to the persistent exclusion registry before publication."""
    path=Path(root)/'results/audit_exposures.json'
    ids=set(review_ids)
    if path.exists():
        ids.update(json.loads(path.read_text(encoding='utf-8'))['review_ids'])
    fd,tmp=tempfile.mkstemp(prefix='.exposures-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({'review_ids':sorted(ids)},f,indent=2)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def identities(rows):
    """Label edits and sorting are allowed; identities and text are immutable."""
    pairs=sorted((r['item_id'],r['review_text']) for r in rows)
    return hashlib.sha256(json.dumps(pairs,ensure_ascii=False).encode('utf-8')).hexdigest()

def unique(rows, key='item_id'):
    values=[r[key] for r in rows]
    if len(values)!=len(set(values)):
        raise ValueError(f'Duplicate {key}')
    return set(values)

def validate_package(path):
    path=Path(path)
    manifest=json.loads((path/'_hidden_manifest.json').read_text(encoding='utf-8'))
    for filename, expected in manifest['immutable_hashes'].items():
        if digest(path/filename)!=expected:
            raise ValueError(f'Changed immutable file: {filename}')
    sheets={name:read_csv(path/name) for name in manifest['sheet_identities']}
    for name, rows in sheets.items():
        unique(rows)
        if identities(rows)!=manifest['sheet_identities'][name]:
            raise ValueError(f'Changed item IDs or text: {name}')
        if any(set(r)!=set(SHEET_FIELDS) for r in rows):
            raise ValueError(f'Incorrect columns: {name}')
    main=sheets['labelling_sheet.csv']; pilot=sheets['pilot_sheet.csv']
    second=sheets['labelling_sheet_annotator2.csv']
    key=read_csv(path/'_hidden_metadata.csv'); pk=read_csv(path/'_hidden_pilot_metadata.csv')
    if len(main)!=450 or len(pilot)!=25 or len(second)!=50:
        raise ValueError('Incorrect sheet counts')
    if unique(main)!=unique(key) or unique(pilot)!=unique(pk):
        raise ValueError('Sheet/key mismatch')
    if unique(main)&unique(pilot) or unique(key,'review_id')&unique(pk,'review_id'):
        raise ValueError('Pilot/main overlap')
    if Counter(r['pool'] for r in key)!=EXPECTED:
        raise ValueError('Incorrect panel counts')
    if unique(second)!={r['item_id'] for r in key if r['in_second_annotator_set']=='1'}:
        raise ValueError('Second-annotator membership mismatch')
    main_map={r['item_id']:r['review_text'] for r in main}
    if any(main_map.get(r['item_id'])!=r['review_text'] for r in second):
        raise ValueError('Second-annotator text mismatch')
    excluded=set(map(str,manifest['excluded_review_ids']))
    if excluded & {r['review_id'] for r in key+pk}:
        raise ValueError('Previously exposed review included')
    p=250/manifest['frame']['eligible_after_exclusions']
    for r in key:
        if not r['bert_tokens'] or int(r['bert_truncated'])!=int(int(r['bert_tokens'])>MAX_TOKENS):
            raise ValueError('Missing or inconsistent token metadata')
        if r['pool']=='probability_sample':
            if not math.isclose(float(r['inclusion_probability']),p,rel_tol=1e-12):
                raise ValueError('Incorrect inclusion probability')
        elif r['inclusion_probability']:
            raise ValueError('Diagnostic panel has prevalence weight')
    for pool in EXPECTED:
        if pool!='probability_sample' and max(Counter(r['gmap_id'] for r in key if r['pool']==pool).values())>2:
            raise ValueError('Panel business cap exceeded')
    pairs={}
    for r in key:
        if r['pool'].startswith('panel_coldwarm_'):
            pairs.setdefault(r['pair_id'],[]).append(r)
    if len(pairs)!=50 or '' in pairs:
        raise ValueError('Incorrect matched pairs')
    for rows in pairs.values():
        if {r['pool'] for r in rows}!={'panel_coldwarm_cold','panel_coldwarm_warm'} or len(rows)!=2:
            raise ValueError('Invalid pair sides')
        lengths=[len(main_map[r['item_id']]) for r in rows]
        if any(r['true_stars']!='5' for r in rows) or any(not 100<=n<=399 for n in lengths) or abs(lengths[0]-lengths[1])>10:
            raise ValueError('Pair rating/length mismatch')
    return manifest, sheets, key

def validate_labels(rows):
    for r in rows:
        if r['sentiment'] not in LABELS:
            raise ValueError('All rows require a valid sentiment label')
        tags={t.strip() for t in r['tags'].split(';') if t.strip()}
        if not tags<=TAGS:
            raise ValueError('Unknown annotation tag')
        if r['implied_stars_optional'] not in {'','1','2','3','4','5'}:
            raise ValueError('Implied stars must be blank or 1-5')
        if 'cannot_assess_language' in tags and r['sentiment']!='cannot_tell':
            raise ValueError('Unassessable language requires cannot_tell')
