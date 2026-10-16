"""Phase 5: compare VADER, BERT, Naive Bayes and SVM on the same evaluation set."""

from project_paths import project_file

import psycopg2

from db_config import DB_PARAMS

REPORT_PATH = (project_file('results/05_phase5_sentiment_comparison_report.txt'))

BASE = """
WITH j AS (
    SELECT e.review_id, e.rating,
           s.vader_compound,
           m.nb_binary, m.svm_binary, m.nb_5class, m.svm_5class,
           b.bert_5class, b.bert_binary, b.bert_forced,
           CASE WHEN e.rating >= 4 THEN 1 WHEN e.rating <= 2 THEN 0 END AS true_binary,
           CASE WHEN s.vader_compound IS NULL THEN NULL
                WHEN s.vader_compound >= 0 THEN 1 ELSE 0 END AS vader_binary
    FROM phase5_eval e
    LEFT JOIN sentiment        s USING (review_id)
    LEFT JOIN phase5_pred_ml   m USING (review_id)
    LEFT JOIN phase5_pred_bert b USING (review_id)
)
"""

Q_COVERAGE = BASE + """
SELECT count(*) AS eval_rows,
       count(true_binary) AS binary_rows,
       count(vader_compound) AS has_vader,
       count(nb_binary) FILTER (WHERE true_binary IS NOT NULL) AS has_nb_binary,
       count(svm_binary) FILTER (WHERE true_binary IS NOT NULL) AS has_svm_binary,
       count(nb_5class) AS has_nb_5class,
       count(svm_5class) AS has_svm_5class,
       count(bert_5class) AS has_bert,
       count(bert_forced) AS has_bert_forced
FROM j;
"""

# All four methods on the same 40,000 reviews, each forced to pick a side.
Q_BINARY = BASE + """
, b AS (SELECT * FROM j WHERE true_binary IS NOT NULL)
SELECT 'VADER (cut at 0)' AS method,
       count(*) AS n,
       round(100.0*count(*) FILTER (WHERE vader_binary = true_binary)/count(*), 2) AS accuracy
FROM b
UNION ALL
SELECT 'BERT (nlptown, pretrained, forced choice)', count(*),
       round(100.0*count(*) FILTER (WHERE bert_forced = true_binary)/count(*), 2) FROM b
UNION ALL
SELECT 'Naive Bayes (trained on stars)', count(*),
       round(100.0*count(*) FILTER (WHERE nb_binary = true_binary)/count(*), 2) FROM b
UNION ALL
SELECT 'Linear SVM (trained on stars)', count(*),
       round(100.0*count(*) FILTER (WHERE svm_binary = true_binary)/count(*), 2) FROM b
ORDER BY accuracy DESC;
"""

# Three BERT variants; only the forced one is comparable with the other methods.
Q_BERT_VARIANTS = BASE + """
, b AS (SELECT * FROM j WHERE true_binary IS NOT NULL)
SELECT 'argmax, scored only where it committed' AS variant,
       count(*) FILTER (WHERE bert_binary IS NOT NULL) AS n_scored,
       round(100.0*count(*) FILTER (WHERE bert_binary = true_binary)
             /NULLIF(count(*) FILTER (WHERE bert_binary IS NOT NULL),0), 2) AS accuracy
FROM b
UNION ALL
SELECT 'argmax, abstentions counted as wrong', count(*),
       round(100.0*count(*) FILTER (WHERE bert_binary = true_binary)/count(*), 2) FROM b
UNION ALL
SELECT 'forced choice P(1)+P(2) vs P(4)+P(5)', count(*),
       round(100.0*count(*) FILTER (WHERE bert_forced = true_binary)/count(*), 2) FROM b;
"""

Q_BY_STAR = BASE + """
, b AS (SELECT * FROM j WHERE true_binary IS NOT NULL)
SELECT rating,
       count(*) AS n,
       round(100.0*count(*) FILTER (WHERE vader_binary = true_binary)/count(*), 2) AS vader,
       round(100.0*count(*) FILTER (WHERE bert_forced = true_binary)/count(*), 2) AS bert,
       round(100.0*count(*) FILTER (WHERE nb_binary    = true_binary)/count(*), 2) AS naive_bayes,
       round(100.0*count(*) FILTER (WHERE svm_binary   = true_binary)/count(*), 2) AS svm
FROM b GROUP BY rating ORDER BY rating;
"""

Q_NEUTRAL_BAND = BASE + """
SELECT CASE WHEN vader_compound >=  0.05 THEN 'positive'
            WHEN vader_compound <= -0.05 THEN 'negative'
            ELSE 'neutral / declines to commit' END AS vader_label,
       count(*) AS n,
       round(avg(rating)::numeric, 3) AS mean_true_star
FROM j GROUP BY 1 ORDER BY 1;
"""

Q_THREE_STAR = BASE + """
SELECT 'VADER says positive'  AS verdict, count(*) FILTER (WHERE rating=3 AND vader_binary=1) AS n
FROM j
UNION ALL SELECT 'BERT says 1-2 star',    count(*) FILTER (WHERE rating=3 AND bert_5class <= 2) FROM j
UNION ALL SELECT 'BERT says 3 star',      count(*) FILTER (WHERE rating=3 AND bert_5class  = 3) FROM j
UNION ALL SELECT 'BERT says 4-5 star',    count(*) FILTER (WHERE rating=3 AND bert_5class >= 4) FROM j
UNION ALL SELECT 'NB 5-class says 3 star',count(*) FILTER (WHERE rating=3 AND nb_5class   = 3) FROM j
UNION ALL SELECT 'SVM 5-class says 3 star',count(*) FILTER (WHERE rating=3 AND svm_5class = 3) FROM j;
"""

Q_AGREEMENT = BASE + """
, b AS (SELECT * FROM j WHERE true_binary IS NOT NULL)
SELECT 'VADER vs BERT'  AS pair,
       round(100.0*count(*) FILTER (WHERE vader_binary = bert_forced)/count(*), 2) AS pct_agree FROM b
UNION ALL SELECT 'VADER vs SVM',
       round(100.0*count(*) FILTER (WHERE vader_binary = svm_binary)/count(*), 2) FROM b
UNION ALL SELECT 'BERT vs SVM',
       round(100.0*count(*) FILTER (WHERE bert_forced = svm_binary)/count(*), 2) FROM b
UNION ALL SELECT 'NB vs SVM',
       round(100.0*count(*) FILTER (WHERE nb_binary = svm_binary)/count(*), 2) FROM b
ORDER BY pct_agree DESC;
"""

Q_5CLASS = BASE + """
SELECT 'BERT (pretrained)' AS method,
       round(100.0*count(*) FILTER (WHERE bert_5class = rating)/count(*), 2) AS exact_acc,
       round(100.0*count(*) FILTER (WHERE abs(bert_5class - rating) <= 1)/count(*), 2) AS within_1_star,
       round(avg(abs(bert_5class - rating))::numeric, 3) AS mean_abs_err
FROM j WHERE bert_5class IS NOT NULL
UNION ALL
SELECT 'Naive Bayes (trained)',
       round(100.0*count(*) FILTER (WHERE nb_5class = rating)/count(*), 2),
       round(100.0*count(*) FILTER (WHERE abs(nb_5class - rating) <= 1)/count(*), 2),
       round(avg(abs(nb_5class - rating))::numeric, 3)
FROM j WHERE nb_5class IS NOT NULL
UNION ALL
SELECT 'Linear SVM (trained)',
       round(100.0*count(*) FILTER (WHERE svm_5class = rating)/count(*), 2),
       round(100.0*count(*) FILTER (WHERE abs(svm_5class - rating) <= 1)/count(*), 2),
       round(avg(abs(svm_5class - rating))::numeric, 3)
FROM j WHERE svm_5class IS NOT NULL
ORDER BY exact_acc DESC;
"""

Q_BERT_CONFUSION = BASE + """
SELECT rating AS true_star,
       count(*) FILTER (WHERE bert_5class=1) AS bert_1,
       count(*) FILTER (WHERE bert_5class=2) AS bert_2,
       count(*) FILTER (WHERE bert_5class=3) AS bert_3,
       count(*) FILTER (WHERE bert_5class=4) AS bert_4,
       count(*) FILTER (WHERE bert_5class=5) AS bert_5
FROM j WHERE bert_5class IS NOT NULL GROUP BY rating ORDER BY rating;
"""


def fmt(cols, rows):
    w = [len(c) for c in cols]
    s = [[('' if v is None else str(v)) for v in r] for r in rows]
    for r in s:
        for i, v in enumerate(r):
            w[i] = max(w[i], len(v))
    out = ["  ".join(c.ljust(w[i]) for i, c in enumerate(cols)),
           "-" * (sum(w) + 2 * (len(w) - 1))]
    out += ["  ".join(v.ljust(w[i]) for i, v in enumerate(r)) for r in s]
    return "\n".join(out)


def validate_coverage(cur):
    """Fail before opening the report; binary ML predictions exclude 3 stars."""
    cur.execute(Q_COVERAGE)
    row = dict(zip((d.name for d in cur.description), cur.fetchone()))
    if not row['eval_rows'] or not row['binary_rows']:
        raise ValueError('Empty evaluation population')
    for field in ('has_vader', 'has_nb_binary', 'has_svm_binary', 'has_nb_5class',
                  'has_svm_5class', 'has_bert', 'has_bert_forced'):
        expected = row['binary_rows'] if field.endswith('_binary') else row['eval_rows']
        if row[field] != expected:
            raise ValueError(f'Incomplete model coverage: {field}={row[field]}, expected {expected}')
    return row


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    validate_coverage(cur)

    sections = [
        ("Coverage check -- every method must have scored every eval review", Q_COVERAGE),
        ("BINARY accuracy on the 40,000 reviews rated 1/2/4/5 (balanced 20k/20k).\n"
         "NB and SVM are trained on star ratings and scored against held-out star\n"
         "ratings. Stars and human-judged sentiment are different targets.", Q_BINARY),
        ("The three possible BERT numbers -- only the last is comparable to the others.\n"
         "The first lets BERT skip the 9.2% of reviews where its top choice is\n"
         "3 stars, while every other method answers all 40,000.", Q_BERT_VARIANTS),
        ("Accuracy by true star rating", Q_BY_STAR),
        ("VADER with the conventional +/-0.05 neutral band, and the true star rating\n"
         "of each group", Q_NEUTRAL_BAND),
        ("The 10,000 THREE-STAR reviews: behavior outside the binary target.\n"
         "The five-class task below evaluates exact-star predictions.", Q_THREE_STAR),
        ("Pairwise agreement between methods (binary, where all are defined)", Q_AGREEMENT),
        ("5-CLASS: predicting the exact star, for the methods that emit 1-5", Q_5CLASS),
        ("BERT confusion matrix (rows = true star, cols = BERT's prediction)", Q_BERT_CONFUSION),
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as rep:
        rep.write("PHASE 5 -- SENTIMENT METHOD COMPARISON\n" + "=" * 78 + "\n\n")
        for title, sql in sections:
            print("Running:", title.split("\n")[0], flush=True)
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
            block = title + "\n" + "-" * 78 + "\n" + fmt(cols, rows) + "\n\n\n"
            rep.write(block)
            print(fmt(cols, rows) + "\n")

    cur.close()
    conn.close()
    print("Report written to", REPORT_PATH)


if __name__ == "__main__":
    main()
