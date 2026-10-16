"""Export the small aggregate CSVs that make_charts.py draws from."""

from project_paths import project_file

import bisect
import csv
import os

import psycopg2

from db_config import DB_PARAMS
CSV_DIR = project_file('results/csv')

QUERIES = {
    "p2_rating_distribution": """
        SELECT rating, count(*) AS n,
               round(100.0*count(*)/sum(count(*)) OVER (), 2) AS pct
        FROM reviews_global_clean GROUP BY rating ORDER BY rating
    """,
    "p2_reviews_per_year": """
        SELECT EXTRACT(YEAR FROM review_time)::int AS year, count(*) AS n
        FROM reviews_global_clean
        WHERE review_time >= '2010-01-01' GROUP BY 1 ORDER BY 1
    """,
    "p2_mean_rating_per_year": """
        SELECT EXTRACT(YEAR FROM review_time)::int AS year,
               round(avg(rating)::numeric, 4) AS mean_rating
        FROM reviews_global_clean
        WHERE review_time >= '2010-01-01' GROUP BY 1 ORDER BY 1
    """,
    "p2_length_vs_rating": """
        SELECT rating,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY length(text)) AS median_length,
               round(avg(length(text))::numeric, 1) AS mean_length
        FROM reviews_global_clean WHERE text IS NOT NULL
        GROUP BY rating ORDER BY rating
    """,
    "p2_response_rate_by_rating": """
        SELECT rating,
               round(100.0*count(*) FILTER (WHERE resp_text IS NOT NULL)/count(*), 2) AS pct_with_response
        FROM reviews_global_clean GROUP BY rating ORDER BY rating
    """,
    "p4a_did_by_year": """
        WITH rel AS (
            SELECT b.gmap_id, b.grp, EXTRACT(YEAR FROM b.last_review)::int AS end_year,
                   r.rating,
                   EXTRACT(EPOCH FROM (b.last_review - r.review_time))/(86400*30.44) AS mb
            FROM phase4_business b JOIN phase4_reviews r USING (gmap_id)
        ), w AS (
            SELECT gmap_id, grp, end_year,
                avg(rating) FILTER (WHERE mb>=12 AND mb<24) AS base_r,
                count(*)    FILTER (WHERE mb>=12 AND mb<24) AS base_n,
                avg(rating) FILTER (WHERE mb>=0  AND mb<6)  AS final_r,
                count(*)    FILTER (WHERE mb>=0  AND mb<6)  AS final_n
            FROM rel GROUP BY 1,2,3
        )
        SELECT end_year,
               round(avg(final_r-base_r) FILTER (WHERE grp='closed')::numeric,4)  AS delta_closed,
               round(avg(final_r-base_r) FILTER (WHERE grp='control')::numeric,4) AS delta_control,
               round((avg(final_r-base_r) FILTER (WHERE grp='closed')
                    - avg(final_r-base_r) FILTER (WHERE grp='control'))::numeric,4) AS did
        FROM w WHERE base_n>=5 AND final_n>=5
        GROUP BY end_year
        HAVING count(*) FILTER (WHERE grp='closed')>=50 AND count(*) FILTER (WHERE grp='control')>=50
        ORDER BY end_year
    """,
    "p4b_did_by_pre_bin": """
        -- Read the persisted Phase 4B cohort so this export matches the report.
        WITH assigned AS (
            SELECT gmap_id, t0, grp FROM phase4b_cohort WHERE has_full_followup),
        win AS (
            SELECT a.gmap_id,a.grp,
                avg(r.rating) FILTER (WHERE r.review_time>=a.t0-INTERVAL '12 months'
                                        AND r.review_time<a.t0) AS pre_r,
                count(*)      FILTER (WHERE r.review_time>=a.t0-INTERVAL '12 months'
                                        AND r.review_time<a.t0) AS pre_n,
                avg(r.rating) FILTER (WHERE r.review_time>a.t0
                                        AND r.review_time<=a.t0+INTERVAL '12 months') AS post_r,
                count(*)      FILTER (WHERE r.review_time>a.t0
                                        AND r.review_time<=a.t0+INTERVAL '12 months') AS post_n
            FROM assigned a JOIN phase4_reviews r USING (gmap_id)
            GROUP BY 1,2)
        SELECT width_bucket(pre_r,2.0,5.0,12) AS pre_bin,
               round(min(pre_r)::numeric,2) AS pre_from,
               round(max(pre_r)::numeric,2) AS pre_to,
               round(avg(post_r-pre_r) FILTER (WHERE grp='responder')::numeric,4) AS chg_responder,
               round(avg(post_r-pre_r) FILTER (WHERE grp='never')::numeric,4)     AS chg_never
        FROM win WHERE pre_n>=5 AND post_n>=5
        GROUP BY 1
        HAVING count(*) FILTER (WHERE grp='responder')>=25 AND count(*) FILTER (WHERE grp='never')>=25
        ORDER BY 1
    """,
    "p5_accuracy_by_star": """
        WITH j AS (
            SELECT e.rating,
                   CASE WHEN e.rating>=4 THEN 1 ELSE 0 END AS truth,
                   CASE WHEN s.vader_compound>=0 THEN 1 ELSE 0 END AS vader,
                   b.bert_forced, m.nb_binary, m.svm_binary
            FROM phase5_eval e
            JOIN sentiment s USING (review_id)
            JOIN phase5_pred_ml m USING (review_id)
            JOIN phase5_pred_bert b USING (review_id)
            WHERE e.rating IN (1,2,4,5))
        SELECT rating,
               round(100.0*count(*) FILTER (WHERE vader=truth)/count(*),2)       AS vader,
               round(100.0*count(*) FILTER (WHERE bert_forced=truth)/count(*),2) AS bert,
               round(100.0*count(*) FILTER (WHERE nb_binary=truth)/count(*),2)   AS naive_bayes,
               round(100.0*count(*) FILTER (WHERE svm_binary=truth)/count(*),2)  AS svm
        FROM j GROUP BY rating ORDER BY rating
    """,
    "p3_state_raw_vs_std": """
        WITH cells AS (SELECT state,category,count(*) n,avg(rating)::numeric m
                       FROM phase3_reviews GROUP BY 1,2),
        common AS (SELECT category FROM cells WHERE n>=100
                   GROUP BY category HAVING count(DISTINCT state)=51),
        wt AS (SELECT c.category,sum(c.n)::numeric w FROM cells c JOIN common k USING (category)
               GROUP BY 1),
        tot AS (SELECT sum(w) tw FROM wt),
        raw AS (SELECT state,avg(rating)::numeric m FROM phase3_reviews GROUP BY 1),
        std AS (SELECT c.state,sum(w.w*c.m)/(SELECT tw FROM tot) m
                FROM cells c JOIN wt w USING (category) GROUP BY 1)
        SELECT raw.state,
               round(raw.m,4) AS raw_mean,
               rank() OVER (ORDER BY raw.m DESC) AS raw_rank,
               round(std.m,4) AS std_mean,
               rank() OVER (ORDER BY std.m DESC) AS std_rank
        FROM raw JOIN std USING (state) ORDER BY std_rank
    """,
}

from artifact_values import reliability_rows


def auc_rows(cur):
    cur.execute("""
        WITH rel AS (
            SELECT b.gmap_id,b.grp,b.mean_rating,
                   EXTRACT(YEAR FROM b.last_review)::int AS end_year, r.rating,
                   EXTRACT(EPOCH FROM (b.last_review-r.review_time))/(86400*30.44) AS mb
            FROM phase4_business b JOIN phase4_reviews r USING (gmap_id)
        ), w AS (
            SELECT gmap_id,grp,end_year,mean_rating,
                avg(rating) FILTER (WHERE mb>=12 AND mb<24) AS base_r,
                count(*)    FILTER (WHERE mb>=12 AND mb<24) AS base_n,
                avg(rating) FILTER (WHERE mb>=0 AND mb<6)   AS final_r,
                count(*)    FILTER (WHERE mb>=0 AND mb<6)   AS final_n
            FROM rel GROUP BY 1,2,3,4)
        SELECT end_year,grp,mean_rating::float,(final_r-base_r)::float,final_r::float
        FROM w WHERE base_n>=5 AND final_n>=5
    """)
    rows = cur.fetchall()

    def auc(cl, ct, i):
        c = sorted(r[i] for r in cl if r[i] is not None)
        k = sorted(r[i] for r in ct if r[i] is not None)
        tot = 0.0
        for v in c:
            lo, hi = bisect.bisect_left(k, v), bisect.bisect_right(k, v)
            tot += (len(k) - hi) + 0.5 * (hi - lo)
        return tot / (len(c) * len(k))

    out = [["end_year", "signal", "auc"]]
    for yr in (2019, 2020, 2021):
        cl = [r for r in rows if r[0] == yr and r[1] == 'closed']
        ct = [r for r in rows if r[0] == yr and r[1] == 'control']
        if len(cl) < 50 or len(ct) < 50:
            continue
        for label, idx in (("rating level", 2), ("trajectory", 3), ("final-window rating", 4)):
            out.append([yr, label, round(auc(cl, ct, idx), 4)])
    return out


def main():
    os.makedirs(CSV_DIR, exist_ok=True)
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT setseed(0.42)")

    for name, sql in QUERIES.items():
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
        with open(os.path.join(CSV_DIR, name + ".csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"{name:32s} {len(rows):>5} rows")

    for name, rows in (("p4a_auc", auc_rows(cur)), ("reliability_contrast", reliability_rows(CSV_DIR))):
        with open(os.path.join(CSV_DIR, name + ".csv"), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"{name:32s} {len(rows)-1:>5} rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
