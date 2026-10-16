"""Phase 6: the reviews where text and stars disagree most, and where BERT lands on them.

Model agreement is reported, not used to decide who is right."""

from project_paths import project_file
from audit_common import record_exposures

import os
import textwrap

import psycopg2
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from db_config import DB_PARAMS

ROOT = project_file('')
REPORT = os.path.join(ROOT, "results", "06_phase6_gap_report.txt")
MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"
N_EXTREME = 200
MIN_LEN = 40


def fetch_extremes(cur, rating, order):
    cur.execute(f"""
        SELECT g.review_id, g.category, g.compound, r.text
        FROM phase6_gap_global g
        JOIN reviews_global_clean r USING (review_id)
        WHERE g.rating = %s AND length(r.text) >= %s
        ORDER BY g.compound {order}
        LIMIT %s
    """, (rating, MIN_LEN, N_EXTREME))
    return cur.fetchall()


def bert_expected_star(texts, tok, model):
    out = [0.0] * len(texts)
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    with torch.no_grad():
        for s in range(0, len(order), 32):
            idx = order[s:s + 32]
            enc = tok([texts[i] for i in idx], padding=True, truncation=True,
                      max_length=256, return_tensors="pt")
            p = torch.softmax(model(**enc).logits, dim=1)
            for i, row in zip(idx, p.tolist()):
                out[i] = sum((k + 1) * row[k] for k in range(5))
    return out


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    five = fetch_extremes(cur, 5, "ASC")    # 5-star, most NEGATIVE text
    one = fetch_extremes(cur, 1, "DESC")    # 1-star, most POSITIVE text
    cur.close()
    conn.close()

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    model.eval()

    five_b = bert_expected_star([r[3] for r in five], tok, model)
    one_b = bert_expected_star([r[3] for r in one], tok, model)

    # 5-star extremes: BERT low means both models read the text as negative; BERT high
    # means they disagree. Neither shows what the reviewer meant.
    five_both_neg = sum(1 for b in five_b if b <= 2.5)
    five_disagree = sum(1 for b in five_b if b >= 3.5)
    one_both_pos = sum(1 for b in one_b if b >= 3.5)
    one_disagree = sum(1 for b in one_b if b <= 2.5)

    lines = ["", "=" * 78,
             "EXTREME DISAGREEMENTS -- where the two models land",
             "=" * 78, "",
             f"Top {N_EXTREME} 5-star reviews by most NEGATIVE VADER score:",
             f"   BERT also reads as negative (<=2.5 stars) : {five_both_neg:>4}"
             f"   -> both models read it as negative (NOT proof the reviewer erred)",
             f"   BERT reads as positive     (>=3.5 stars) : {five_disagree:>4}"
             f"   -> the models disagree; VADER is the outlier",
             f"   ambiguous (2.5-3.5)                      : "
             f"{N_EXTREME - five_both_neg - five_disagree:>4}",
             "",
             f"Top {N_EXTREME} 1-star reviews by most POSITIVE VADER score:",
             f"   BERT also reads as positive (>=3.5 stars): {one_both_pos:>4}"
             f"   -> both models read it as POSITIVE (NOT proof the reviewer erred)",
             f"   BERT reads as negative      (<=2.5 stars): {one_disagree:>4}"
             f"   -> the models disagree; VADER is the outlier",
             f"   ambiguous (2.5-3.5)                      : "
             f"{N_EXTREME - one_both_pos - one_disagree:>4}",
             ""]

    exposed_ids = set()

    def examples(rows, berts, title, pick):
        block = ["", title, "-" * len(title)]
        shown = 0
        for (rid, cat, comp, text), b in zip(rows, berts):
            if not pick(b):
                continue
            exposed_ids.add(rid)
            excerpt = " ".join(text.split())[:260]
            block.append(f"[{cat}]  VADER {comp:+.3f}  BERT {b:.2f} stars")
            block.extend(textwrap.wrap(excerpt, 76, initial_indent="   ",
                                       subsequent_indent="   "))
            block.append("")
            shown += 1
            if shown >= 5:
                break
        return block

    lines += examples(five, five_b,
                      "5-STAR, both models read the text as negative (hard text -- not adjudicated)",
                      lambda b: b <= 2.5)
    lines += examples(five, five_b,
                      "5-STAR, models disagree: BERT reads it positive (VADER the likely error)",
                      lambda b: b >= 3.5)
    lines += examples(one, one_b,
                      "1-STAR, both models read the text as positive (hard text -- not adjudicated)",
                      lambda b: b >= 3.5)
    lines += examples(one, one_b,
                      "1-STAR, models disagree: BERT reads it negative (VADER the likely error)",
                      lambda b: b <= 2.5)

    # Record identities before publishing text, so future audit runs exclude them.
    record_exposures(ROOT, exposed_ids)
    text = "\n".join(lines)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    # console-safe: the corpus contains characters cp1252 cannot encode
    print(text.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
