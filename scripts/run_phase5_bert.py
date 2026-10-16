"""Score the Phase 5 evaluation set with pretrained BERT (nlptown), on CPU."""

import io
import time

import psycopg2
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from db_config import DB_PARAMS

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
BATCH_SIZE = 64
MAX_LEN = 256


def main():
    torch.set_num_threads(torch.get_num_threads())
    print(f"torch threads: {torch.get_num_threads()}", flush=True)

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("""
        SELECT e.review_id, r.text
        FROM phase5_eval e JOIN reviews_global_clean r USING (review_id)
        ORDER BY e.review_id
    """)
    rows = cur.fetchall()
    cur.close()
    print(f"eval reviews: {len(rows):,}", flush=True)

    print("loading model (downloads ~670MB on first run) ...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    # sort by text length so each batch pads to its own longest member
    order = sorted(range(len(rows)), key=lambda i: len(rows[i][1]))
    preds = [None] * len(rows)
    probs = [None] * len(rows)

    t0 = time.time()
    done = 0
    with torch.no_grad():
        for start in range(0, len(order), BATCH_SIZE):
            idx = order[start:start + BATCH_SIZE]
            texts = [rows[i][1] for i in idx]
            enc = tok(texts, padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            logits = model(**enc).logits
            # nlptown labels are 0..4 == 1..5 stars
            p = torch.softmax(logits, dim=1)
            stars = torch.argmax(logits, dim=1).tolist()
            for i, s, pr in zip(idx, stars, p.tolist()):
                preds[i] = s + 1
                probs[i] = pr
            done += len(idx)
            if done % 3200 == 0 or done == len(order):
                rate = done / (time.time() - t0)
                eta = (len(order) - done) / rate / 60
                print(f"  {done:>6,}/{len(order):,}  {rate:5.1f}/sec  eta {eta:5.1f} min",
                      flush=True)

    elapsed = time.time() - t0
    print(f"\nscored {len(rows):,} reviews in {elapsed/60:.1f} min "
          f"({len(rows)/elapsed:.1f}/sec)")

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS phase5_pred_bert")
    cur.execute("""
        CREATE TABLE phase5_pred_bert (
            review_id    BIGINT PRIMARY KEY,
            bert_5class  SMALLINT,  -- argmax: 1..5
            bert_binary  SMALLINT,  -- argmax collapsed: 1,2->0  4,5->1  3->NULL (abstains)
            bert_forced  SMALLINT,  -- FORCED choice: P(1)+P(2) vs P(4)+P(5), never abstains
            bert_p_neg   REAL,      -- P(1 star) + P(2 star)
            bert_p_pos   REAL       -- P(4 star) + P(5 star)
        )
    """)
    # bert_forced picks the more probable side, so BERT can't abstain on hard reviews.
    buf = io.StringIO()
    for (rid, _), p, pr in zip(rows, preds, probs):
        b = "" if p == 3 else (1 if p >= 4 else 0)
        p_neg = pr[0] + pr[1]
        p_pos = pr[3] + pr[4]
        forced = 1 if p_pos > p_neg else 0
        buf.write(f"{rid},{p},{b},{forced},{p_neg:.6f},{p_pos:.6f}\n")
    buf.seek(0)
    cur.copy_expert("COPY phase5_pred_bert (review_id, bert_5class, bert_binary, "
                    "bert_forced, bert_p_neg, bert_p_pos) FROM STDIN WITH (FORMAT csv)", buf)
    conn.commit()
    cur.execute("SELECT count(*) FROM phase5_pred_bert")
    print(f"phase5_pred_bert: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
