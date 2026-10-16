"""Shared, database-free values used by the README, docs, exports and verifier."""
import csv
import hashlib
import json
from pathlib import Path
import re

# How many times each filled-in number must appear in each document.
# A number missing from a document's list must not appear in it at all.
METRIC_DOCUMENTS = {
    "README.md": {
        "vermont_shift": 2, "p3_split": 2, "p3_noise": 1, "p3_full": 1, "p6_full": 1,
        "closure_did_range": 2, "closure_auc_range": 2,
        "response_1": 2, "response_5": 2, "response_gain": 2,
        "vader_5star": 2, "vader_2star": 2, "bert_cold": 1, "vader_cold": 1,
        "audit_vader_negatives": 1, "audit_bert_negatives": 1,
    },
    "docs/FINDINGS.md": {
        "vermont_shift": 1, "p3_split": 1, "p3_noise": 1, "p3_full": 1, "p6_full": 1,
        "closure_did_range": 1, "closure_auc_range": 1,
        "response_1": 1, "response_5": 1, "response_gain": 1,
        "bert_cold": 1, "vader_cold": 1, "category_range": 1, "state_range": 1,
        "vader_5star": 1, "vader_2star": 1,
    },
}
METRIC_COUNTS = METRIC_DOCUMENTS["README.md"]

CHART_INPUTS = {
    "01_rating_distribution": ["p2_rating_distribution"],
    "02_volume_and_rating_inflation": ["p2_reviews_per_year", "p2_mean_rating_per_year"],
    "03_length_vs_rating": ["p2_length_vs_rating"],
    "04_owner_response_rate": ["p2_response_rate_by_rating"],
    "05_state_rank_shift": ["p3_state_raw_vs_std"],
    "06_reliability_contrast": ["reliability_contrast"],
    "07_closure_auc": ["p4a_auc"],
    "08_closure_did": ["p4a_did_by_year"],
    "09_sentiment_accuracy_by_star": ["p5_accuracy_by_star"],
    "10_category_gap": ["p6_category_gap"],
    "11_length_effect": ["p6_length_vader"],
    "12_bert_check": ["p6_bert_check"],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metric_row(root, phase):
    with (Path(root) / f"results/csv/metrics_phase{phase}_reliability.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"Expected one Phase {phase} reliability row")
    return rows[0]


def reliability_rows(csv_dir):
    rows = [["measure", "split_half_observed", "noise_only_expected", "spearman_brown_full"]]
    for phase in (3, 6):
        with (Path(csv_dir) / f"metrics_phase{phase}_reliability.csv").open(encoding="utf-8", newline="") as f:
            source = list(csv.reader(f))
        if len(source) != 2 or source[0] != rows[0]:
            raise ValueError(f"Malformed Phase {phase} reliability CSV")
        rows.append(source[1])
    return rows


def bert_effects(root):
    with (Path(root) / "results/csv/p6_bert_check.csv").open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.reader(f) if r and r[0] in ("A_grim_minus_reference", "B_cold10_minus_warm10")]
    if len(rows) != 2 or len({r[0] for r in rows}) != 2:
        raise ValueError("Expected the two BERT contrasts exactly once")
    return {r[0]: tuple(float(v) for v in r[1:]) for r in rows}


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def response_gain(root):
    """The matched B4 contrast, read from the Phase 4B report's own table."""
    lines = (Path(root) / "results/04b_phase4_responses_report.txt").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        header = line.split()
        if "did_att" in header and "cells_favouring_responders" in header:
            values = next(l.split() for l in lines[i + 1:] if l.strip() and not set(l.strip()) <= {"-"})
            if len(values) != len(header):
                raise ValueError("Malformed Phase 4B matched-result row")
            return float(values[header.index("did_att")])
    raise ValueError("Phase 4B report has no matched (did_att) result")


def readme_values(root):
    root = Path(root)
    with (root / "results/csv/p3_state_raw_vs_std.csv").open(encoding="utf-8", newline="") as f:
        vermont = next(r for r in csv.DictReader(f) if r["state"] == "Vermont")
    with (root / "results/csv/p4a_did_by_year.csv").open(encoding="utf-8", newline="") as f:
        dids = [abs(float(r["did"])) for r in csv.DictReader(f)]
    with (root / "results/csv/p4a_auc.csv").open(encoding="utf-8", newline="") as f:
        aucs = [float(r["auc"]) for r in csv.DictReader(f)]
    with (root / "results/csv/p5_accuracy_by_star.csv").open(encoding="utf-8", newline="") as f:
        vader_by_star = {r["rating"]: float(r["vader"]) for r in csv.DictReader(f)}
    addendum = json.loads((root / "results/audit_v2/addendum_20260928/addendum_results.json").read_text(encoding="utf-8"))
    vader_neg = addendum["models"]["vader"]["per_class"]["negative"]
    bert_neg = addendum["models"]["bert"]["per_class"]["negative"]
    p3, p6 = metric_row(root, 3), metric_row(root, 6)
    effects = bert_effects(root)
    signed = lambda x: f"{x:+.2f}".replace("-", "−")
    with (root / "results/csv/p6_category_gap.csv").open(encoding="utf-8", newline="") as f:
        cats = list(csv.DictReader(f))
    with (root / "results/csv/p6_state_gap_standardized.csv").open(encoding="utf-8", newline="") as f:
        states = list(csv.DictReader(f))
    with (root / "results/csv/p2_response_rate_by_rating.csv").open(encoding="utf-8", newline="") as f:
        responses = {r['rating']: float(r['pct_with_response']) for r in csv.DictReader(f)}
    catvals = [float(r['mean_gap_lenctl']) for r in cats]
    statevals = [float(r['std_gap']) for r in states]
    return {
        "p3_split": f"{float(p3['split_half_observed']):.3f}",
        "p3_noise": f"{float(p3['noise_only_expected']):.3f}",
        "p3_full": f"{float(p3['spearman_brown_full']):.3f}",
        "p6_full": f"≈{float(p6['spearman_brown_full']):.2f}",
        "vader_grim": signed(effects['A_grim_minus_reference'][0]),
        "bert_grim": signed(effects['A_grim_minus_reference'][1]),
        "vader_cold": signed(effects['B_cold10_minus_warm10'][0]),
        "bert_cold": signed(effects['B_cold10_minus_warm10'][1]),
        "category_range": f"{max(catvals) - min(catvals):.3f}",
        "state_range": f"{max(statevals) - min(statevals):.4f}",
        "response_1": f"{responses['1']:.2f}%",
        "response_5": f"{responses['5']:.2f}%",
        "vermont_shift": f"{ordinal(vermont['raw_rank'])} to {ordinal(vermont['std_rank'])}",
        "closure_did_range": f"{min(dids):.2f}–{max(dids):.2f}",
        "closure_auc_range": f"{min(aucs):.2f}–{max(aucs):.2f}",
        "response_gain": f"{response_gain(root):+.3f}",
        "vader_2star": f"{vader_by_star['2']:.0f}%",
        "vader_5star": f"{vader_by_star['5']:.0f}%",
        "audit_vader_negatives": f"{vader_neg['agreed']} of {vader_neg['human_n']}",
        "audit_bert_negatives": f"{bert_neg['agreed']}",
    }


def metric_pattern(key):
    return re.compile(r"(<!-- metric:" + re.escape(key) + r" -->)(.*?)(<!-- /metric:" + re.escape(key) + r" -->)", re.S)


def refresh_document(text, values, counts, name="README"):
    for key in values:
        pattern = metric_pattern(key)
        expected = counts.get(key, 0)
        if len(pattern.findall(text)) != expected:
            raise ValueError(f"{name} requires {expected} explicit metric field(s): {key}")
        text = pattern.sub(lambda m: m[1] + values[key] + m[3], text)
    return text


def refresh_readme(text, values):
    return refresh_document(text, values, METRIC_COUNTS)
