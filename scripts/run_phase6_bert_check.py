"""Phase 6: check the VADER category gap with BERT on rating- and length-balanced samples."""

from project_paths import project_file

import csv
import os
import random
import statistics as st

import psycopg2
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from db_config import DB_PARAMS

ROOT = project_file('')
REPORT = os.path.join(ROOT, "results", "06_phase6_gap_report.txt")
CSV_OUT = os.path.join(ROOT, "results", "csv", "p6_bert_check.csv")

MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"
PER_BAND = 500
BANDS = [(100, 199), (200, 299), (300, 399)]
GRIM = ("(funeral|hospital|emergency room|oncolog|cancer|veterinar|collision|"
        "auto body|pest control|bail bond|criminal|urgent care)")
SEED = 42


def cold_warm_categories(cur):
    cur.execute("""
        SELECT category, avg(gap_fine) g
        FROM phase6_gap_fine
        WHERE category IS NOT NULL AND category <> ''
        GROUP BY category HAVING count(*) >= 1000
        ORDER BY g
    """)
    rows = cur.fetchall()
    return [r[0] for r in rows[:10]], [r[0] for r in rows[-10:]]


def sample_group(cur, where_sql, params, rng):
    """5-star reviews, PER_BAND drawn from each length band."""
    out = []
    for lo, hi in BANDS:
        cur.execute(f"""
            SELECT g.review_id, r.text, g.compound, g.category
            FROM phase6_gap_global g
            JOIN reviews_global_clean r USING (review_id)
            WHERE g.rating = 5
              AND length(r.text) BETWEEN %s AND %s
              AND {where_sql}
        """, (lo, hi, *params))
        pool = cur.fetchall()
        if len(pool) < PER_BAND:
            raise ValueError(f"Insufficient group coverage in length band {lo}-{hi}")
        rng.shuffle(pool)
        out.extend(pool[:PER_BAND])
    return out


def bert_scores(texts, tok, model):
    exp_star, p_pos = [], []
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    es = [0.0] * len(texts)
    pp = [0.0] * len(texts)
    with torch.no_grad():
        for s in range(0, len(order), 64):
            idx = order[s:s + 64]
            enc = tok([texts[i] for i in idx], padding=True, truncation=True,
                      max_length=256, return_tensors="pt")
            p = torch.softmax(model(**enc).logits, dim=1)
            for i, row in zip(idx, p.tolist()):
                es[i] = sum((k + 1) * row[k] for k in range(5))
                pp[i] = row[3] + row[4]
    return es, pp


def main():
    rng = random.Random(SEED)
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    cold10, warm10 = cold_warm_categories(cur)
    groups = {
        "A_grim": sample_group(cur, "g.category ~* %s", (GRIM,), rng),
        "A_reference": sample_group(cur, "g.category IS NOT NULL AND g.category !~* %s",
                                    (GRIM,), rng),
        "B_cold10": sample_group(cur, "g.category = ANY(%s)", (cold10,), rng),
        "B_warm10": sample_group(cur, "g.category = ANY(%s)", (warm10,), rng),
    }
    cur.close()
    conn.close()

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    model.eval()

    stats = {}
    for name, rows in groups.items():
        texts = [r[1] for r in rows]
        es, pp = bert_scores(texts, tok, model)
        stats[name] = dict(
            n=len(rows),
            mean_len=st.mean(len(t) for t in texts),
            vader=[float(r[2]) for r in rows],
            bert_star=es,
            bert_ppos=pp,
        )
        print(f"{name:12s} n={len(rows):>5}  len={stats[name]['mean_len']:.0f}  "
              f"vader={st.mean(stats[name]['vader']):+.4f}  "
              f"bert_star={st.mean(es):.4f}  bert_P(4-5)={st.mean(pp):.4f}", flush=True)

    all_v = [v for s in stats.values() for v in s["vader"]]
    all_b = [v for s in stats.values() for v in s["bert_star"]]
    sd_v, sd_b = st.stdev(all_v), st.stdev(all_b)

    def effect(a, b, key, sd):
        return (st.mean(stats[a][key]) - st.mean(stats[b][key])) / sd

    lines = ["", "=" * 78,
             "BERT CHECK -- category contrasts under a second model",
             "=" * 78,
             "5-star reviews only. Equal draws from length bands 100-199 / 200-299 /",
             "300-399 chars in every group. Effect sizes are standardized (difference",
             "in means / SD of all four groups, including between-group variation).",
             "This is not Cohen's d; model scales and calibration still differ.", "",
             f"{'group':14s}{'n':>6s}{'mean_len':>10s}{'VADER':>10s}"
             f"{'BERT star':>11s}{'BERT P(4-5)':>13s}"]
    rows_csv = []
    for name, s in stats.items():
        lines.append(f"{name:14s}{s['n']:>6}{s['mean_len']:>10.0f}"
                     f"{st.mean(s['vader']):>+10.4f}{st.mean(s['bert_star']):>11.4f}"
                     f"{st.mean(s['bert_ppos']):>13.4f}")
        rows_csv.append([name, s["n"], round(s["mean_len"], 1),
                         round(st.mean(s["vader"]), 4),
                         round(st.mean(s["bert_star"]), 4),
                         round(st.mean(s["bert_ppos"]), 4)])

    a_v = effect("A_grim", "A_reference", "vader", sd_v)
    a_b = effect("A_grim", "A_reference", "bert_star", sd_b)
    b_v = effect("B_cold10", "B_warm10", "vader", sd_v)
    b_b = effect("B_cold10", "B_warm10", "bert_star", sd_b)

    lines += ["",
              "Standardized difference (first group minus second):",
              f"  TEST A  grim - reference   VADER {a_v:+.3f}   BERT {a_b:+.3f}",
              f"  TEST B  cold10 - warm10    VADER {b_v:+.3f}   BERT {b_b:+.3f}",
              "",
              f"cold10: {', '.join(cold10)}",
              f"warm10: {', '.join(warm10)}",
              ""]

    text = "\n".join(lines)
    print(text)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text)
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "n", "mean_len", "vader_mean", "bert_expected_star", "bert_p_pos"])
        w.writerows(rows_csv)
        w.writerow([])
        w.writerow(["test", "vader_effect", "bert_effect"])
        w.writerow(["A_grim_minus_reference", round(a_v, 3), round(a_b, 3)])
        w.writerow(["B_cold10_minus_warm10", round(b_v, 3), round(b_b, 3)])


if __name__ == "__main__":
    main()
