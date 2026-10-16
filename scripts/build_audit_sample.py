"""Create an immutable blinded audit run; never overwrite existing sheets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import uuid
from datetime import datetime, timezone
from audit_common import MODEL, MAX_TOKENS, SHEET_FIELDS, digest, identities, validate_package, write_csv
from project_paths import project_file

SEED=20260920
MIN_LEN=20

def flat(text):
    return ' '.join(text.split())

def compact(text):
    # Handle wrapped long words, Unicode and emoji in the published excerpts.
    return ''.join(text.split())

def report_excerpts(report):
    return [compact(m.group(1)) for m in re.finditer(
        r'^\[[^\n]+\]  VADER[^\n]*\n((?:   [^\n]*\n)+)',report,re.M)]

def resolve_excerpts(excerpts,candidates):
    if not excerpts:
        raise ValueError('No published examples found; exposure reconstruction requires review')
    ids=set()
    for excerpt in excerpts:
        matches={int(rid) for rid,text in candidates if compact(text).startswith(excerpt)}
        if not matches:
            raise ValueError('Unresolved published excerpt; refusing incomplete exclusions')
        ids.update(matches)
    return ids

def resolve_exposures(conn,root):
    report=root/'results/06_phase6_gap_report.txt'
    excerpts=report_excerpts(report.read_text(encoding='utf-8'))
    with conn.cursor() as cur:
        cur.execute('''
            (SELECT r.review_id,r.text FROM phase6_gap_global g JOIN reviews_global_clean r USING(review_id)
             WHERE g.rating=5 AND length(r.text)>=40 ORDER BY g.compound ASC,r.review_id LIMIT 2000)
            UNION ALL
            (SELECT r.review_id,r.text FROM phase6_gap_global g JOIN reviews_global_clean r USING(review_id)
             WHERE g.rating=1 AND length(r.text)>=40 ORDER BY g.compound DESC,r.review_id LIMIT 2000)''')
        ids=resolve_excerpts(excerpts,cur.fetchall())
    registry=root/'results/audit_exposures.json'
    if registry.exists():
        ids.update(json.loads(registry.read_text(encoding='utf-8'))['review_ids'])
    return ids,dict(report_sha256=digest(report),resolved_excerpt_count=len(excerpts))

def reservoir(rows,size,rng):
    selected=[]; n=0; h=hashlib.sha256()
    for (rid,) in rows:
        h.update(f'{rid}\n'.encode('ascii')); n+=1
        if n<=size:
            selected.append(rid)
        else:
            j=rng.randrange(n)
            if j<size:
                selected[j]=rid
    if n<size:
        raise ValueError('Eligible frame too small')
    rng.shuffle(selected)
    return selected,n,h.hexdigest()

def cap(rows,rng,size):
    rows=list(rows); rng.shuffle(rows); seen={}; chosen=[]
    for row in rows:
        if seen.get(row[3],0)>=2:
            continue
        seen[row[3]]=seen.get(row[3],0)+1; chosen.append(row)
        if len(chosen)==size:
            return chosen
    raise ValueError(f'Panel shortage: require {size}, found {len(chosen)}')

def match_lengths(cold,warm,rng,size=50,tolerance=10):
    cold=list(cold); warm=list(warm); rng.shuffle(cold); rng.shuffle(warm)
    used=set(); seen_c={}; seen_w={}; pairs=[]
    for c in cold:
        if seen_c.get(c[3],0)>=2:
            continue
        options=[(abs(len(flat(c[1]))-len(flat(w[1]))),i,w) for i,w in enumerate(warm)
                 if i not in used and c[0]!=w[0] and seen_w.get(w[3],0)<2
                 and abs(len(flat(c[1]))-len(flat(w[1])))<=tolerance]
        if not options:
            continue
        _,i,w=min(options,key=lambda x:(x[0],x[1]))
        used.add(i); seen_c[c[3]]=seen_c.get(c[3],0)+1; seen_w[w[3]]=seen_w.get(w[3],0)+1
        pairs.append((c,w))
        if len(pairs)==size:
            return pairs
    raise ValueError('Insufficient distinct, length-matched cold/warm pairs')

def item_id(rid):
    return 'IT-'+hashlib.sha1(f'audit{rid}'.encode()).hexdigest()[:10].upper()

def cached_revision():
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(MODEL,local_files_only=True)).name

def publish(destination,populate):
    destination=Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Audit destination already exists; existing labels were not changed')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # A UUID directory avoids a Windows ACL problem with Python's private temp dirs.
    stage=destination.parent/('.audit-incomplete-'+uuid.uuid4().hex)
    stage.mkdir()
    try:
        populate(stage)
        validate_package(stage)
        if destination.exists():
            raise FileExistsError('Audit destination appeared during generation')
        os.rename(stage,destination)
    finally:
        if stage.exists():
            if stage.resolve().parent!=destination.parent or not stage.name.startswith('.audit-incomplete-'):
                raise RuntimeError('Unexpected staging path')
            shutil.rmtree(stage)

def build(destination,seed=SEED):
    if Path(destination).exists():
        raise FileExistsError('Audit destination already exists; existing labels were not changed')
    import psycopg2
    from db_config import DB_PARAMS
    from transformers import AutoTokenizer
    root=Path(project_file('')); revision=cached_revision()
    tok=AutoTokenizer.from_pretrained(MODEL,revision=revision,local_files_only=True)
    rng=random.Random(seed); conn=psycopg2.connect(**DB_PARAMS)
    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
    try:
        excluded,exposure_info=resolve_exposures(conn,root)
        with conn.cursor() as cur:
            cur.execute('''SELECT count(*),count(*) FILTER(WHERE length(text)>0),
                count(*) FILTER(WHERE length(text) BETWEEN 1 AND 19),count(*) FILTER(WHERE length(text)>=20)
                FROM reviews_global_clean''')
            frame=dict(zip(['clean_total','nonempty_text','text_1_to_19','eligible_before_exclusions'],cur.fetchone()))
            cur.execute('SELECT txid_current_snapshot()::text'); snapshot=cur.fetchone()[0]
        print('Drawing probability sample from the ordered eligible frame ...',flush=True)
        with conn.cursor(name='audit_frame') as stream:
            stream.itersize=20000
            stream.execute('''SELECT review_id FROM reviews_global_clean
                WHERE length(text)>=%s AND NOT(review_id=ANY(%s)) ORDER BY review_id''',(MIN_LEN,sorted(excluded)))
            selected,population,frame_hash=reservoir(stream,275,rng)
        frame['eligible_after_exclusions']=population
        with conn.cursor() as cur:
            cur.execute('''SELECT r.review_id,r.text,r.rating,r.gmap_id,s.vader_compound
                FROM reviews_global_clean r LEFT JOIN sentiment s USING(review_id) WHERE r.review_id=ANY(%s)''',(selected,))
            found=cur.fetchall(); lookup={r[0]:r for r in found}
            if len(found)!=275 or len(lookup)!=275:
                raise ValueError('Missing or duplicate source rows')
            pilot=[lookup[r] for r in selected[:25]]; probability=[lookup[r] for r in selected[25:]]
            taken=set(selected)|excluded
            def available(rows):
                return [r for r in rows if r[0] not in taken]
            cur.execute('''
                (SELECT g.review_id,r.text,g.rating,r.gmap_id,g.compound FROM phase6_gap_global g
                 JOIN reviews_global_clean r USING(review_id) WHERE g.rating=5 AND length(r.text)>=40
                 ORDER BY g.compound ASC,g.review_id LIMIT 400)
                UNION ALL
                (SELECT g.review_id,r.text,g.rating,r.gmap_id,g.compound FROM phase6_gap_global g
                 JOIN reviews_global_clean r USING(review_id) WHERE g.rating=1 AND length(r.text)>=40
                 ORDER BY g.compound DESC,g.review_id LIMIT 400)''')
            extremes=cap(available(cur.fetchall()),rng,50); taken.update(r[0] for r in extremes)
            cur.execute('''SELECT e.review_id,r.text,e.rating,r.gmap_id,s.vader_compound
                FROM phase5_eval e JOIN reviews_global_clean r USING(review_id) JOIN sentiment s USING(review_id)
                JOIN phase5_pred_bert b USING(review_id) WHERE length(r.text)>=40
                AND (CASE WHEN s.vader_compound>=0 THEN 1 ELSE 0 END)<>b.bert_forced ORDER BY e.review_id''')
            disagree=cap(available(cur.fetchall()),rng,50); taken.update(r[0] for r in disagree)
            cur.execute('''SELECT category FROM phase6_gap_fine WHERE category IS NOT NULL AND category<>''
                GROUP BY category HAVING count(*)>=1000 ORDER BY avg(gap_fine),category''')
            cats=[r[0] for r in cur.fetchall()]
            if len(cats)<20:
                raise ValueError('Fewer than 20 eligible categories')
            groups={'cold':cats[:10],'warm':cats[-10:]}; candidates={}
            for side,categories in groups.items():
                # Hash thinning is confined to diagnostic candidate sets.
                cur.execute('''SELECT g.review_id,r.text,g.rating,r.gmap_id,g.compound FROM phase6_gap_global g
                    JOIN reviews_global_clean r USING(review_id) WHERE g.rating=5
                    AND length(r.text) BETWEEN 100 AND 399 AND g.category=ANY(%s)
                    ORDER BY md5(g.review_id::text || %s),g.review_id LIMIT 2000''',(categories,str(seed)))
                candidates[side]=[r for r in available(cur.fetchall()) if 100<=len(flat(r[1]))<=399]
            pairs=match_lengths(candidates['cold'],candidates['warm'],rng)
        records=[(r,'probability_sample','') for r in probability]
        records += [(r,'panel_extremes','') for r in extremes]+[(r,'panel_model_disagreement','') for r in disagree]
        for i,(c,w) in enumerate(pairs,1):
            records += [(c,'panel_coldwarm_cold',f'PAIR-{i:03}'),(w,'panel_coldwarm_warm',f'PAIR-{i:03}')]
        if any(r[4] is None for r,_,_ in records):
            raise ValueError('Missing VADER score')
        rng.shuffle(records)
        second_ids={item_id(r[0]) for r,_,_ in rng.sample(records,50)}
        counts=[len(ids) for ids in tok([flat(r[1]) for r,_,_ in records],truncation=False)['input_ids']]
        def populate(stage):
            def sheet(rows):
                return [dict(zip(SHEET_FIELDS,[item_id(r[0]),flat(r[1]),'','','',''])) for r in rows]
            main=sheet([r for r,_,_ in records]); ps=sheet(pilot)
            second=[r.copy() for r in main if r['item_id'] in second_ids]; rng.shuffle(second)
            sheet_rows={'labelling_sheet.csv':main,'pilot_sheet.csv':ps,'labelling_sheet_annotator2.csv':second}
            for name,rows in sheet_rows.items():
                write_csv(stage/name,SHEET_FIELDS,rows)
            keys=[]
            for (r,pool,pair),ntok in zip(records,counts):
                keys.append(dict(item_id=item_id(r[0]),review_id=r[0],pool=pool,
                    inclusion_probability=format(250/population,'.17g') if pool=='probability_sample' else '',
                    true_stars=r[2],vader_compound=r[4],gmap_id=r[3],bert_tokens=ntok,bert_truncated=int(ntok>MAX_TOKENS),
                    in_second_annotator_set=int(item_id(r[0]) in second_ids),pair_id=pair))
            write_csv(stage/'_hidden_metadata.csv',list(keys[0]),keys)
            pk=[dict(item_id=item_id(r[0]),review_id=r[0],true_stars=r[2],vader_compound=r[4]) for r in pilot]
            write_csv(stage/'_hidden_pilot_metadata.csv',list(pk[0]),pk)
            for name in ['CODEBOOK.md','ANALYSIS_PLAN.md']:
                shutil.copyfile(root/'results/audit_v2'/name,stage/name)
            manifest=dict(schema_version=2,created_utc=datetime.now(timezone.utc).isoformat(),seed=seed,
                selection='Python Random reservoir over review_id ascending; shuffle and split 25 pilot / 250 main',
                frame=frame,frame_ids_sha256=frame_hash,database_snapshot=snapshot,excluded_review_ids=sorted(excluded),
                exposure_sources=exposure_info,categories=groups,coldwarm_max_character_difference=10,
                model=MODEL,model_revision=revision,max_tokens=MAX_TOKENS,builder_sha256=digest(Path(__file__)),
                sheet_identities={name:identities(rows) for name,rows in sheet_rows.items()},
                immutable_hashes={name:digest(stage/name) for name in ['_hidden_metadata.csv','_hidden_pilot_metadata.csv','ANALYSIS_PLAN.md']})
            (stage/'_hidden_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        publish(destination,populate)
        print('Published 450 main, 25 pilot, 50 second-annotator items; existing runs preserved.',flush=True)
    finally:
        conn.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(project_file('results/audit_v2')))
    parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args(); build(args.output,args.seed)
