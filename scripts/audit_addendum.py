"""Post-hoc additions to the completed human audit, computed from the locked archive:
majority baseline, per-class agreement, an exact McNemar test, and a sensitivity
check that excludes the items discussed with AI during labelling.

    py -B scripts/audit_addendum.py          # write results and documents
    py -B scripts/audit_addendum.py --check  # recompute and compare only"""
import argparse
import csv
import json
from math import comb
from pathlib import Path

from analyze_audit_sample import wilson
from completed_audit_summary import ARCHIVE, END as AUDIT_END, checked_results

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('results/audit_v2/addendum_20260928')
BEGIN = '<!-- human-audit-addendum:begin -->'
END = '<!-- human-audit-addendum:end -->'
DOCUMENTS = ('docs/HUMAN_AUDIT.md',)
COMPARABLE = ('positive', 'negative', 'neutral')
# Short version for the README's Findings section.
HEAD_BEGIN = '<!-- human-audit-headline:begin -->'
HEAD_END = '<!-- human-audit-headline:end -->'
HEAD_AFTER = 'every trained model on 4- and 5-star reviews.'

# Each snippet must match exactly one main-sheet review. `suggested` is the label
# the assistant proposed, or None where none was recorded.
DISCUSSED = [
    # source, snippet, suggested
    ('assistant 1', 'Going out of business', None),
    ('assistant 1', 'Ate one of my sliders before taking a second to snag a pic', None),
    ('assistant 1', 'I hope you have a pleasant long, busy, holiday weekend', None),
    ('both', 'Not what I expected but ok', 'negative'),
    ('assistant 2', 'But at 2am it is better than', None),
    ('assistant 2', 'Everything thing was very salty', 'negative'),
    ('assistant 2', 'Tiene de todo', 'positive'),
    ('assistant 2', 'too noisy', 'negative'),
    ('assistant 2', "the chicken had father's on it", 'negative'),
    ('assistant 2', 'Exxon fuel', 'positive'),
    ('assistant 2', 'required documents needed to file my taxes', 'positive'),
    ('assistant 2', 'Love the midnight showings', 'positive'),
    ('assistant 2', 'Here you can do all your shopping', 'positive'),
    ('assistant 2', 'turkey sausage and turkey bacon', 'positive'),
    ('assistant 2', 'Food was plain and over cooked', 'negative'),
    ('assistant 2', '50% off on almost everything', 'positive'),
    ('assistant 2', 'Dean Crouch', 'mixed'),
    ('assistant 2', 'Taste tots', 'cannot_tell'),
    ('assistant 2', 'Sandwich shop with subway rolls', 'negative'),
    ('assistant 2', 'Houston Hobby', 'negative'),
    ('assistant 2', 'Bring back chocolate chip bagels', 'negative'),
    ('assistant 2', "have enough registers open", 'negative'),
    ('assistant 2', 'ribs lunch special', 'negative'),
    ('assistant 2', 'fox ford', 'positive'),
    ('assistant 2', 'Busy Bees', 'cannot_tell'),
]


def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the two discordant counts."""
    n = b + c
    if not n:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def disagreement(items, labels, pred, field):
    k = sum(pred[i][field] != labels[i] for i in items)
    return {'disagreements': k, 'denominator': len(items),
            'fraction': k / len(items) if items else None,
            'wilson_95': wilson(k, len(items))}


def compute(root=ROOT):
    root = Path(root)
    checked_results(root)                      # raises if the archive changed
    inputs = root / ARCHIVE / 'inputs'
    main = read(inputs / 'labelling_sheet.csv')
    meta = {r['item_id']: r for r in read(inputs / '_hidden_metadata.csv')}
    pred = json.loads((inputs / '_hidden_predictions.json').read_text(encoding='utf-8'))['predictions']
    labels = {r['item_id']: r['sentiment'] for r in main}

    discussed = []
    for source, snippet, suggested in DISCUSSED:
        hits = [r['item_id'] for r in main if snippet.lower() in r['review_text'].lower()]
        if len(hits) != 1:
            raise ValueError(f'Snippet must match exactly one item, matched {len(hits)}: {snippet!r}')
        i = hits[0]
        discussed.append({'item_id': i, 'source': source, 'pool': meta[i]['pool'],
                          'annotator_label': labels[i], 'suggested_label': suggested})
    ids = {d['item_id'] for d in discussed}
    if len(ids) != len(discussed):
        raise ValueError('Two snippets matched the same item')

    random_ids = [r['item_id'] for r in main if meta[r['item_id']]['pool'] == 'probability_sample']
    comp = [i for i in random_ids if labels[i] in COMPARABLE]
    kept = [i for i in comp if i not in ids]

    models = {}
    for key, field in (('vader', 'vader_label'), ('bert', 'bert_label')):
        per_class = {}
        for cls in COMPARABLE:
            truth = [i for i in comp if labels[i] == cls]
            per_class[cls] = {'human_n': len(truth),
                              'agreed': sum(pred[i][field] == cls for i in truth),
                              'model_n': sum(pred[i][field] == cls for i in comp)}
        models[key] = {'all': disagreement(comp, labels, pred, field),
                       'excluding_discussed': disagreement(kept, labels, pred, field),
                       'within_discussed': disagreement([i for i in comp if i in ids], labels, pred, field),
                       'per_class': per_class}

    vader_only = sum(pred[i]['vader_label'] != labels[i] and pred[i]['bert_label'] == labels[i] for i in comp)
    bert_only = sum(pred[i]['bert_label'] != labels[i] and pred[i]['vader_label'] == labels[i] for i in comp)
    suggested = [d for d in discussed if d['suggested_label']]
    majority = max(COMPARABLE, key=lambda c: sum(labels[i] == c for i in comp))
    majority_n = sum(labels[i] == majority for i in comp)
    result = {
        'schema': 1,
        'archive': ARCHIVE.as_posix(),
        'post_hoc': True,
        'comparable_n': len(comp),
        'majority_baseline': {'label': majority, 'agreed': majority_n, 'fraction': majority_n / len(comp)},
        'models': models,
        'mcnemar': {'vader_only_wrong': vader_only, 'bert_only_wrong': bert_only,
                    'p_exact_two_sided': mcnemar_exact(vader_only, bert_only)},
        'discussed': {'n': len(discussed),
                      'in_random_sample': sum(d['pool'] == 'probability_sample' for d in discussed),
                      'in_comparable_random_sample': sum(i in ids for i in comp),
                      'archive_reported_n': 4, 'archive_reported_in_random_sample': 1,
                      'with_suggestion': len(suggested),
                      'annotator_differed_from_suggestion': sum(d['annotator_label'] != d['suggested_label']
                                                                for d in suggested),
                      'items': discussed},
    }
    return json.loads(json.dumps(result))      # normalise exactly as saved


def pct(x):
    return f'{100 * x:.1f}%'


def interval(w):
    return f'{100 * w[0]:.1f}–{100 * w[1]:.1f}%'


def body_lines(r):
    v, b, d, base = r['models']['vader'], r['models']['bert'], r['discussed'], r['majority_baseline']
    rows = []
    for name, m in (('VADER', v), ('BERT', b)):
        a, e = m['all'], m['excluding_discussed']
        rows.append(f"| {name} | {a['disagreements']}/{a['denominator']} ({pct(a['fraction'])}) | "
                    f"{e['disagreements']}/{e['denominator']} ({pct(e['fraction'])}) | {interval(e['wilson_95'])} |")
    neg_v, neg_b = v['per_class']['negative'], b['per_class']['negative']
    pos_v, pos_b = v['per_class']['positive'], b['per_class']['positive']
    mc = r['mcnemar']
    agree_v, agree_b = 1 - v['all']['fraction'], 1 - b['all']['fraction']
    return [
        'Post-hoc checks that the archived report omitted; none were in the pre-written',
        'analysis plan. Computed by `scripts/audit_addendum.py` from the unchanged archive.',
        '',
        f"**Documented AI discussion: {d['n']} items.** The archive's check "
        f"found {d['archive_reported_n']} ({d['archive_reported_in_random_sample']} in the random sample) "
        'because its snippet list was incomplete. The two assistant conversations used during '
        f"labelling together identify {d['n']} main-sheet items, {d['in_random_sample']} "
        'in the random sample. Where a label was suggested, the annotator chose differently on '
        f"{d['annotator_differed_from_suggestion']} of {d['with_suggestion']}. "
        'Excluding these identified items leaves the ranking unchanged. This checks the supplied snippet list, not every possible use of AI:',
        '',
        f"| Model | All {r['comparable_n']} | Excluding discussed | Wilson 95% (excluding) |",
        '|---|---:|---:|---:|',
        *rows,
        '',
        f"**Baseline.** {base['agreed']}/{r['comparable_n']} comparable labels are {base['label']}, so "
        f"always answering \"{base['label']}\" agrees {pct(base['fraction'])} of the time. VADER's "
        f"{pct(agree_v)} agreement is {100 * (agree_v - base['fraction']):.1f} points above that; "
        f"BERT's {pct(agree_b)} is {100 * (agree_b - base['fraction']):.1f} points above.",
        '',
        f"**Where they differ: negative reviews.** Of {neg_v['human_n']} reviews labelled negative, VADER "
        f"agrees on {neg_v['agreed']} ({pct(neg_v['agreed'] / neg_v['human_n'])}) and BERT on "
        f"{neg_b['agreed']} ({pct(neg_b['agreed'] / neg_b['human_n'])}). On positive reviews the gap is "
        f"small: {pos_v['agreed']}/{pos_v['human_n']} versus {pos_b['agreed']}/{pos_b['human_n']}. "
        f"Only {v['per_class']['neutral']['human_n']} items are labelled neutral, too few to evaluate.",
        '',
        f"**Paired test.** Both models scored the same items: VADER alone was wrong on "
        f"{mc['vader_only_wrong']}, BERT alone on {mc['bert_only_wrong']} (exact McNemar p = "
        f"{mc['p_exact_two_sided']:.3f}). This tests equal disagreement probabilities for the two models on these paired items; it does not test either model against the majority baseline. "
        'The single-annotator and sampling caveats of the primary result still apply.',
    ]


def render_block(r):
    return '\n'.join([BEGIN, '### Human-audit addendum (28 September 2026)', '', *body_lines(r), END])


def render_headline(r):
    v, b, base = r['models']['vader'], r['models']['bert'], r['majority_baseline']
    neg_v, neg_b = v['per_class']['negative'], b['per_class']['negative']
    return '\n'.join([
        HEAD_BEGIN,
        "**A hand-labelled check shows the same weakness.** Among the randomly chosen "
        "reviews I labelled without seeing their stars or the model scores, "
        f"{neg_v['human_n']} were negative: VADER agreed on {neg_v['agreed']} of them "
        f"({pct(neg_v['agreed'] / neg_v['human_n'])}), BERT on {neg_b['agreed']} "
        f"({pct(neg_b['agreed'] / neg_b['human_n'])}). Because {pct(base['fraction'])} of the "
        f"{r['comparable_n']} comparable labels were {base['label']}, answering \"{base['label']}\" every "
        f"time would already agree {pct(base['fraction'])} of the time; VADER agrees on "
        f"{pct(1 - v['all']['fraction'])} and BERT on {pct(1 - b['all']['fraction'])}. A post-hoc "
        "paired test makes BERT's lead over VADER unlikely to be chance (exact McNemar "
        f"p = {r['mcnemar']['p_exact_two_sided']:.3f}). One person did the labelling, with some "
        "items discussed with AI; the full results are in [docs/HUMAN_AUDIT.md](docs/HUMAN_AUDIT.md).",
        HEAD_END,
    ])


def refreshed_headline(text, block):
    if HEAD_BEGIN not in text and HEAD_END not in text:
        if text.count(HEAD_AFTER) != 1:
            raise ValueError('Cannot place headline: expected one Finding 6 anchor sentence')
        return text.replace(HEAD_AFTER, HEAD_AFTER + '\n\n' + block, 1)
    if text.count(HEAD_BEGIN) != 1 or text.count(HEAD_END) != 1:
        raise ValueError('Expected exactly one human-audit headline block')
    start, stop = text.index(HEAD_BEGIN), text.index(HEAD_END) + len(HEAD_END)
    return text[:start] + block + text[stop:]


def render_report(r):
    lines = ['# Human-audit addendum - 28 September 2026', '', *body_lines(r), '',
             '## Discussed items', '',
             'Identified from both assistant transcripts. `Suggested` is the label the assistant',
             'proposed; blank where it explained a rule without proposing one, or where that',
             "conversation's suggestions were not recorded.", '',
             '| Item | Source | Pool | Annotator label | Suggested |', '|---|---|---|---|---|']
    lines += [f"| {d['item_id']} | {d['source']} | {d['pool']} | {d['annotator_label']} | "
              f"{d['suggested_label'] or ''} |" for d in r['discussed']['items']]
    return '\n'.join(lines) + '\n'


def refreshed(text, block):
    if BEGIN not in text and END not in text:
        if text.count(AUDIT_END) != 1:
            raise ValueError('Cannot place addendum: expected one completed-audit block')
        return text.replace(AUDIT_END, AUDIT_END + '\n\n' + block, 1)
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Expected exactly one human-audit addendum block')
    start, stop = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + block + text[stop:]


def is_current(root=ROOT):
    root = Path(root)
    r = compute(root)
    out = root / OUT
    saved = json.loads((out / 'addendum_results.json').read_text(encoding='utf-8'))
    block = render_block(r)
    docs_ok = True
    for name in DOCUMENTS:
        text = (root / name).read_text(encoding='utf-8')
        docs_ok &= text.count(BEGIN) == 1 and text == refreshed(text, block)
    readme = (root / 'README.md').read_text(encoding='utf-8')
    docs_ok &= readme.count(HEAD_BEGIN) == 1 and readme == refreshed_headline(readme, render_headline(r))
    return (saved == r and docs_ok
            and (out / 'ADDENDUM.md').read_text(encoding='utf-8') == render_report(r))


def write(root=ROOT):
    root = Path(root)
    r = compute(root)
    out = root / OUT
    out.mkdir(exist_ok=True)
    (out / 'addendum_results.json').write_text(json.dumps(r, indent=2) + '\n', encoding='utf-8')
    (out / 'ADDENDUM.md').write_text(render_report(r), encoding='utf-8')
    block = render_block(r)
    for name in DOCUMENTS:
        path = root / name
        path.write_text(refreshed(path.read_text(encoding='utf-8'), block), encoding='utf-8')
    readme = root / 'README.md'
    readme.write_text(refreshed_headline(readme.read_text(encoding='utf-8'), render_headline(r)),
                      encoding='utf-8')
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        ok = is_current(args.root)
        print('addendum current' if ok else 'addendum STALE')
        return int(not ok)
    print(render_block(write(args.root)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
