"""Train Naive Bayes and a linear SVM on TF-IDF features (binary and 5-class) and save predictions."""

import io
import time

import psycopg2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score

from db_config import DB_PARAMS


def fetch(conn, table):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT s.review_id, s.rating, r.text
        FROM {table} s JOIN reviews_global_clean r USING (review_id)
        ORDER BY s.review_id
    """)
    rows = cur.fetchall()
    cur.close()
    ids = [r[0] for r in rows]
    y = [r[1] for r in rows]
    X = [r[2] for r in rows]
    return ids, y, X


def main():
    conn = psycopg2.connect(**DB_PARAMS)

    t0 = time.time()
    print("loading train/eval text ...", flush=True)
    tr_ids, tr_y, tr_X = fetch(conn, "phase5_train")
    ev_ids, ev_y, ev_X = fetch(conn, "phase5_eval")
    print(f"  train {len(tr_X):,} | eval {len(ev_X):,}   [{time.time()-t0:.0f}s]")

    # Fit the vectoriser on training text only, so nothing leaks from the eval set.
    t0 = time.time()
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=300_000,
                          sublinear_tf=True, strip_accents="unicode")
    Xtr = vec.fit_transform(tr_X)
    Xev = vec.transform(ev_X)
    print(f"vectorised: {Xtr.shape[1]:,} features   [{time.time()-t0:.0f}s]")

    results = {}

    bin_tr = [i for i, y in enumerate(tr_y) if y != 3]
    bin_ev = [i for i, y in enumerate(ev_y) if y != 3]
    ytr_b = [1 if tr_y[i] >= 4 else 0 for i in bin_tr]
    yev_b = [1 if ev_y[i] >= 4 else 0 for i in bin_ev]
    Xtr_b, Xev_b = Xtr[bin_tr], Xev[bin_ev]
    print(f"\nbinary: train {len(ytr_b):,} (bal {sum(ytr_b)/len(ytr_b):.3f}) | "
          f"eval {len(yev_b):,} (bal {sum(yev_b)/len(yev_b):.3f})")

    for name, model in [("nb", MultinomialNB()), ("svm", LinearSVC(dual="auto"))]:
        t0 = time.time()
        model.fit(Xtr_b, ytr_b)
        pred = model.predict(Xev_b)
        acc = accuracy_score(yev_b, pred)
        f1 = f1_score(yev_b, pred)
        print(f"  {name:4s} binary  acc={acc:.4f}  f1={f1:.4f}   [{time.time()-t0:.0f}s]")
        results[f"{name}_binary"] = dict(zip((ev_ids[i] for i in bin_ev), pred))

    print("\n5-class:")
    for name, model in [("nb", MultinomialNB()), ("svm", LinearSVC(dual="auto"))]:
        t0 = time.time()
        model.fit(Xtr, tr_y)
        pred = model.predict(Xev)
        acc = accuracy_score(ev_y, pred)
        print(f"  {name:4s} 5-class acc={acc:.4f}   [{time.time()-t0:.0f}s]")
        results[f"{name}_5class"] = dict(zip(ev_ids, pred))

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS phase5_pred_ml")
    cur.execute("""
        CREATE TABLE phase5_pred_ml (
            review_id   BIGINT PRIMARY KEY,
            nb_binary   SMALLINT,
            svm_binary  SMALLINT,
            nb_5class   SMALLINT,
            svm_5class  SMALLINT
        )
    """)
    buf = io.StringIO()
    for rid in ev_ids:
        buf.write("{},{},{},{},{}\n".format(
            rid,
            results["nb_binary"].get(rid, ""),
            results["svm_binary"].get(rid, ""),
            results["nb_5class"].get(rid, ""),
            results["svm_5class"].get(rid, ""),
        ))
    buf.seek(0)
    cur.copy_expert(
        "COPY phase5_pred_ml (review_id, nb_binary, svm_binary, nb_5class, svm_5class) "
        "FROM STDIN WITH (FORMAT csv)", buf)
    conn.commit()
    cur.execute("SELECT count(*) FROM phase5_pred_ml")
    print(f"\nphase5_pred_ml: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
