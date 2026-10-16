"""Maintain the completed human-audit summary from its immutable dated archive."""
import hashlib
import json
from pathlib import Path
import re

ARCHIVE = Path('results/audit_v2/analysis_20260927')
BEGIN = '<!-- completed-human-audit:begin -->'
END = '<!-- completed-human-audit:end -->'
DOCUMENTS = ('docs/HUMAN_AUDIT.md',)


def checked_results(root):
    archive = Path(root) / ARCHIVE
    hashes = json.loads((archive / 'archive_hashes.json').read_text(encoding='utf-8'))
    for relative, expected in hashes.items():
        path = (archive / relative).resolve()
        if not path.is_relative_to(archive.resolve()):
            raise ValueError('Archive manifest path escapes archive')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Completed audit archive changed: {relative}')
    return json.loads((archive / 'analysis_results.json').read_text(encoding='utf-8'))


def render(root):
    data = checked_results(root)
    prob = data['probability_sample']
    rows = []
    for key, label in (('vader', 'VADER'), ('bert', 'BERT')):
        r = prob[key]
        lo, hi = r['wilson_95']
        rows.append(f"| {label} | {r['disagreements']}/{r['denominator']} | "
                    f"{100*r['fraction']:.1f}% | {100*lo:.1f}–{100*hi:.1f}% | "
                    f"{100*(1-r['fraction']):.1f}% |")
    return '\n'.join([
        BEGIN,
        '### Completed human audit', '',
        'All 450 main reviews were labelled under frozen codebook v2.1. The primary',
        f"estimate uses only the {prob['n']}-item probability sample; the other 200",
        'items are selected diagnostic panels and are reported separately.', '',
        f"The sampling frame contains {data['frame']['eligible_after_exclusions']:,} clean global-sample reviews",
        'with at least 20 characters, after documented exposure exclusions. The',
        f"{prob['comparable_n']} positive/negative/neutral labels support the three-way model comparison;",
        'six mixed and one cannot-tell labels are excluded from that comparison.', '',
        '| Model | Disagreements | Disagreement rate | Wilson 95% interval | Agreement |',
        '|---|---:|---:|---:|---:|', *rows, '',
        'BERT agrees more often with this annotator. These are human-label agreement',
        'rates, with a different population and decision rule from the star-balanced',
        'Phase 5 benchmark. The intervals describe sampling uncertainty, not uncertainty',
        'about the annotator. There was one human annotator, AI discussion of some items',
        '(quantified in the addendum below), and no independent second-annotator',
        'agreement measurement.', '',
        'The cold/warm diagnostic comparison found 49/50 versus 50/50 positive labels.',
        'This near-ceiling result cannot measure differences in positivity intensity',
        'or determine what fraction of the continuous model-score gap is real.',
        'BERT still disagrees on 17/45 comparable extreme cases; it is not an adjudicator.', '',
        'Original labels, optional tags and notes are preserved. Documented rubric',
        'ambiguities remain in the primary results; optional tags were not exhaustively',
        'applied, so a blank tag is not verified absence. Any future adjudication must',
        'be a separately logged sensitivity analysis.',
        END,
    ])


def refreshed(text, block):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Expected exactly one completed human-audit block')
    return re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), lambda _: block, text, flags=re.S)


def documents_current(root):
    block = render(root)
    return all((text := (Path(root)/name).read_text(encoding='utf-8')) == refreshed(text, block)
               for name in DOCUMENTS)


def refresh_documents(root):
    block = render(root)
    pending = []
    for name in DOCUMENTS:
        path = Path(root)/name
        before = path.read_text(encoding='utf-8')
        after = refreshed(before, block)
        if after != before:
            pending.append((path, after))
    for path, after in pending:
        path.write_text(after, encoding='utf-8')
