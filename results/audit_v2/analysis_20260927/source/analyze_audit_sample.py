"""Validate a run, freeze the pilot rubric, or analyze completed human labels."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path
from audit_common import LABELS, digest, read_csv, text_hash, validate_labels, validate_package
from score_audit_sample import atomic_json

def wilson(k,n):
    if not n:
        return None
    z=1.959963984540054; p=k/n; d=1+z*z/n
    center=(p+z*z/(2*n))/d; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,center-half),min(1,center+half)]

def validate_predictions(run,manifest,sheets):
    data=json.loads((run/'_hidden_predictions.json').read_text(encoding='utf-8'))
    if (data['model'],data['model_revision'],data['max_tokens'])!=(manifest['model'],manifest['model_revision'],manifest['max_tokens']):
        raise ValueError('Prediction model configuration mismatch')
    if data['manifest_sha256']!=digest(run/'_hidden_manifest.json'):
        raise ValueError('Predictions belong to a different manifest')
    pred=data['predictions']; main=sheets['labelling_sheet.csv']
    if set(pred)!={r['item_id'] for r in main}:
        raise ValueError('Predictions must cover exactly every main item')
    metadata={r['item_id']:r for r in read_csv(run/'_hidden_metadata.csv')}
    for r in main:
        p=pred[r['item_id']]; probs=p['bert_probabilities']
        if p['text_sha256']!=text_hash(r['review_text']):
            raise ValueError('Prediction text mismatch')
        if len(probs)!=5 or not all(math.isfinite(x) and 0<=x<=1 for x in probs) or not math.isclose(sum(probs),1,abs_tol=1e-5):
            raise ValueError('Invalid model probabilities')
        stars=max(range(5),key=lambda i:probs[i])+1
        expected='negative' if stars<=2 else 'neutral' if stars==3 else 'positive'
        forced='positive' if probs[3]+probs[4]>=probs[0]+probs[1] else 'negative'
        if p['bert_label']!=expected or p['bert_forced']!=forced or p['vader_label'] not in {'positive','negative','neutral'}:
            raise ValueError('Prediction label/probability mismatch')
        compound=float(metadata[r['item_id']]['vader_compound'])
        vader='positive' if compound>=.05 else 'negative' if compound<=-.05 else 'neutral'
        if not math.isfinite(compound) or p['vader_label']!=vader:
            raise ValueError('VADER prediction inconsistent with score')
    return pred

def freeze(run):
    manifest,sheets,key=validate_package(run)
    validate_labels(sheets['pilot_sheet.csv'])
    if any(r['sentiment'] or r['tags'] or r['notes'] or r['implied_stars_optional']
           for name in ['labelling_sheet.csv','labelling_sheet_annotator2.csv'] for r in sheets[name]):
        raise ValueError('Freeze the rubric before any main/second-annotator labels')
    atomic_json(run/'_codebook_freeze.json',dict(codebook_sha256=digest(run/'CODEBOOK.md'),
        pilot_labels_sha256=digest(run/'pilot_sheet.csv'),manifest_sha256=digest(run/'_hidden_manifest.json'),
        frozen_utc=datetime.now(timezone.utc).isoformat()))

def summarize(rows,key,pred,with_ci):
    counts=Counter(r['sentiment'] for r in rows); n=len(rows)
    result={'n':n,'human_labels':{label:{'n':counts[label],'fraction':counts[label]/n,
        **({'wilson_95':wilson(counts[label],n)} if with_ci else {})} for label in sorted(LABELS)}}
    comparable=[r for r in rows if r['sentiment'] in {'positive','negative','neutral'}]
    result['comparable_n']=len(comparable)
    result['excluded_from_model_error_n']=n-len(comparable)
    for model in ['vader','bert']:
        wrong=sum(pred[r['item_id']][model+'_label']!=r['sentiment'] for r in comparable)
        denom=len(comparable)
        result[model]={'disagreements':wrong,'denominator':denom,'fraction':wrong/denom if denom else None,
            **({'wilson_95':wilson(wrong,denom)} if with_ci else {}),
            'confusion':dict(Counter(r['sentiment']+' -> '+pred[r['item_id']][model+'_label'] for r in comparable))}
    result['binary_sensitivity']={}
    binary=[r for r in rows if r['sentiment'] in {'positive','negative'}]
    for model in ['vader','bert']:
        def label(r):
            return pred[r['item_id']]['bert_forced'] if model=='bert' else ('positive' if float(key[r['item_id']]['vader_compound'])>=0 else 'negative')
        wrong=sum(label(r)!=r['sentiment'] for r in binary)
        result['binary_sensitivity'][model]={'disagreements':wrong,'denominator':len(binary),
            'fraction':wrong/len(binary) if binary else None}
    result['truncated_n']=sum(key[r['item_id']]['bert_truncated']=='1' for r in rows)
    return result

def analyze(run,output,allow_single=False):
    manifest,sheets,meta=validate_package(run)
    frozen=json.loads((run/'_codebook_freeze.json').read_text(encoding='utf-8'))
    if frozen['codebook_sha256']!=digest(run/'CODEBOOK.md') or frozen['manifest_sha256']!=digest(run/'_hidden_manifest.json'):
        raise ValueError('Frozen codebook or run changed')
    main=sheets['labelling_sheet.csv']; validate_labels(main)
    pred=validate_predictions(run,manifest,sheets); key={r['item_id']:r for r in meta}
    result={'frame':manifest['frame'],'scope':'Text >=20 characters in the clean global sample, excluding documented exposed reviews',
        'probability_sample':None,'diagnostic_panels':{},'source_manifest_sha256':digest(run/'_hidden_manifest.json'),
        'main_labels_sha256':digest(run/'labelling_sheet.csv'),'prediction_sha256':digest(run/'_hidden_predictions.json')}
    for pool in sorted({r['pool'] for r in meta}):
        rows=[r for r in main if key[r['item_id']]['pool']==pool]
        summary=summarize(rows,key,pred,pool=='probability_sample')
        if pool=='probability_sample':
            result['probability_sample']=summary
        else:
            result['diagnostic_panels'][pool]=summary
    pairs={}; labels={r['item_id']:r['sentiment'] for r in main}
    for r in meta:
        if r['pair_id']:
            pairs.setdefault(r['pair_id'],{})[r['pool'].split('_')[-1]]=labels[r['item_id']]
    result['coldwarm_exploratory']={'pairs':len(pairs),'label_pairs':dict(Counter(p['cold']+' / '+p['warm'] for p in pairs.values())),
        'positive_fraction_cold_minus_warm':sum((p['cold']=='positive')-(p['warm']=='positive') for p in pairs.values())/len(pairs),
        'interpretation':'Descriptive paired contrast; not a causal effect or corpus prevalence estimate'}
    second=sheets['labelling_sheet_annotator2.csv']
    has_any=any(r[c] for r in second for c in ['sentiment','tags','implied_stars_optional','notes'])
    if not has_any and allow_single:
        result['agreement']={'status':'Not measured; one annotator only'}
    else:
        validate_labels(second)
        n=len(second); agree=sum(r['sentiment']==labels[r['item_id']] for r in second)
        a=Counter(labels[r['item_id']] for r in second); b=Counter(r['sentiment'] for r in second)
        expected=sum(a[l]*b[l] for l in LABELS)/n**2
        result['agreement']={'n':n,'fraction':agree/n,'wilson_95':wilson(agree,n),
            'cohen_kappa':(agree/n-expected)/(1-expected) if expected<1 else None,
            'confusion':dict(Counter(labels[r['item_id']]+' / '+r['sentiment'] for r in second)),
            'scope':'The mixed diagnostic/probability subset only; not corpus-wide reliability'}
    atomic_json(output,result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('run',type=Path)
    p.add_argument('--freeze',action='store_true'); p.add_argument('--validate-only',action='store_true')
    p.add_argument('--allow-single-annotator',action='store_true'); p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.freeze: freeze(a.run)
    elif a.validate_only:
        m,s,k=validate_package(a.run)
        if (a.run/'_hidden_predictions.json').exists(): validate_predictions(a.run,m,s)
        print('Audit package valid; human labels are not required for this check.')
    else: analyze(a.run,a.output or a.run/'analysis_results.json',a.allow_single_annotator)
