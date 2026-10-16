"""Phase 4B: owner reply rates and speed, and the rating change after a business starts
replying compared with matched never-responders. Descriptive, not causal."""

from project_paths import project_file

import psycopg2

from db_config import DB_PARAMS

REPORT_PATH = (project_file('results/04b_phase4_responses_report.txt'))

Q_ADOPTION = """
SELECT EXTRACT(YEAR FROM review_time)::int AS year,
       count(*) AS n_reviews,
       count(*) FILTER (WHERE resp_time IS NOT NULL) AS n_responded,
       round(100.0 * count(*) FILTER (WHERE resp_time IS NOT NULL) / count(*), 2) AS pct_responded
FROM phase4_reviews
WHERE review_time >= '2010-01-01'
GROUP BY 1 ORDER BY 1;
"""

# 51,428 replies are dated before their review (probably edited reviews), so the
# report gives both the raw median and the valid-lag median.
Q_BY_RATING = """
SELECT rating,
       count(*) AS n,
       round(100.0 * count(*) FILTER (WHERE resp_time IS NOT NULL) / count(*), 2) AS pct_responded,
       count(*) FILTER (WHERE resp_time < review_time) AS replies_dated_before_review,
       round(percentile_cont(0.5) WITHIN GROUP (
           ORDER BY EXTRACT(EPOCH FROM (resp_time - review_time))/86400.0)::numeric, 2)
           AS median_days_raw,
       round(percentile_cont(0.5) WITHIN GROUP (
           ORDER BY EXTRACT(EPOCH FROM (resp_time - review_time))/86400.0)
           FILTER (WHERE resp_time >= review_time)::numeric, 2)
           AS median_days_valid_lag
FROM phase4_reviews
GROUP BY rating ORDER BY rating;
"""


# One persisted cohort, so every query below uses the same control assignment.
# has_full_followup: the 12-month post window must end before the data does.
BUILD_COHORT = """
DROP TABLE IF EXISTS phase4b_cohort;

CREATE TABLE phase4b_cohort AS
WITH corpus_end AS (SELECT max(review_time) AS t_end FROM phase4_reviews),
starters AS (
    SELECT gmap_id, first_response AS t0, 'responder'::text AS grp
    FROM phase4_business WHERE first_response IS NOT NULL
),
pool AS (SELECT t0, row_number() OVER (ORDER BY random()) AS rn FROM starters),
pool_n AS (SELECT count(*) AS c FROM pool),
nevers AS (
    SELECT gmap_id, row_number() OVER (ORDER BY random()) AS rn
    FROM phase4_business WHERE n_responses = 0
),
never_t0 AS (
    SELECT n.gmap_id, p.t0, 'never'::text AS grp
    FROM nevers n JOIN pool p ON p.rn = ((n.rn - 1) % (SELECT c FROM pool_n)) + 1
)
SELECT a.gmap_id, a.grp, a.t0,
       (a.t0 + INTERVAL '12 months' <= (SELECT t_end FROM corpus_end)) AS has_full_followup
FROM (SELECT * FROM starters UNION ALL SELECT * FROM never_t0) a;

ALTER TABLE phase4b_cohort ADD PRIMARY KEY (gmap_id);
CREATE INDEX idx_p4bc_grp ON phase4b_cohort (grp);
"""

# Shared window construction for B2.
WIN = """
WITH assigned AS (
    -- one fixed assignment, shared by every query below
    SELECT gmap_id, t0, grp FROM phase4b_cohort WHERE has_full_followup
),
win AS (
    SELECT a.gmap_id, a.grp, a.t0,
        avg(r.rating) FILTER (WHERE r.review_time >= a.t0 - INTERVAL '12 months'
                                AND r.review_time <  a.t0)                    AS pre_r,
        count(*)      FILTER (WHERE r.review_time >= a.t0 - INTERVAL '12 months'
                                AND r.review_time <  a.t0)                    AS pre_n,
        avg(r.rating) FILTER (WHERE r.review_time >  a.t0
                                AND r.review_time <= a.t0 + INTERVAL '12 months') AS post_r,
        count(*)      FILTER (WHERE r.review_time >  a.t0
                                AND r.review_time <= a.t0 + INTERVAL '12 months') AS post_n
    FROM assigned a JOIN phase4_reviews r USING (gmap_id)
    GROUP BY a.gmap_id, a.grp, a.t0
)
"""

Q_NAIVE = WIN + """
SELECT grp, count(*) AS n_biz,
       round(avg(pre_r)::numeric, 3)           AS pre_rating,
       round(avg(post_r)::numeric, 3)          AS post_rating,
       round(avg(post_r - pre_r)::numeric, 4)  AS naive_change
FROM win WHERE pre_n >= 5 AND post_n >= 5
GROUP BY grp ORDER BY grp;
"""

Q_MATCHED = WIN + """
, cells AS (
    SELECT width_bucket(pre_r, 2.0, 5.0, 12) AS pre_bin,
           EXTRACT(YEAR FROM t0)::int         AS t0_year,
           count(*) FILTER (WHERE grp='responder')                                AS n_resp,
           avg(post_r - pre_r) FILTER (WHERE grp='responder')                     AS chg_resp,
           count(*) FILTER (WHERE grp='never')                                    AS n_never,
           avg(post_r - pre_r) FILTER (WHERE grp='never')                         AS chg_never
    FROM win WHERE pre_n >= 5 AND post_n >= 5
    GROUP BY 1, 2
    HAVING count(*) FILTER (WHERE grp='responder') >= 25
       AND count(*) FILTER (WHERE grp='never')     >= 25
)
-- Average the per-cell differences, weighted by responders per cell. Differencing
-- two separately weighted group means would bring back the composition bias the
-- matching removes. did_att is a descriptive contrast, not a causal effect.
SELECT count(*)                                                       AS n_cells,
       sum(n_resp)                                                    AS responder_biz,
       sum(n_never)                                                   AS never_biz,
       round(avg(chg_resp)::numeric, 4)                               AS mean_change_responders,
       round(avg(chg_never)::numeric, 4)                              AS mean_change_never,
       round(avg(chg_resp - chg_never)::numeric, 4)                   AS did_cell_unweighted,
       round((sum(n_resp * (chg_resp - chg_never))
              / sum(n_resp))::numeric, 4)                             AS did_att,
       count(*) FILTER (WHERE chg_resp > chg_never)                   AS cells_favouring_responders
FROM cells;
"""

Q_MATCHED_BY_BIN = WIN + """
SELECT width_bucket(pre_r, 2.0, 5.0, 12) AS pre_bin,
       round(min(pre_r)::numeric, 2)                                     AS pre_rating_from,
       round(max(pre_r)::numeric, 2)                                     AS pre_rating_to,
       count(*) FILTER (WHERE grp='responder')                           AS n_resp,
       round(avg(post_r - pre_r) FILTER (WHERE grp='responder')::numeric, 4)  AS chg_resp,
       count(*) FILTER (WHERE grp='never')                               AS n_never,
       round(avg(post_r - pre_r) FILTER (WHERE grp='never')::numeric, 4)      AS chg_never,
       round((avg(post_r - pre_r) FILTER (WHERE grp='responder')
            - avg(post_r - pre_r) FILTER (WHERE grp='never'))::numeric, 4)    AS did
FROM win WHERE pre_n >= 5 AND post_n >= 5
GROUP BY 1
HAVING count(*) FILTER (WHERE grp='responder') >= 25
   AND count(*) FILTER (WHERE grp='never')     >= 25
ORDER BY 1;
"""

# Targeting uses lifetime data, so this comparison is descriptive, not a policy effect.
Q_TARGETING = """
WITH resp_profile AS (
    SELECT gmap_id,
           count(*) FILTER (WHERE resp_time IS NOT NULL)                      AS n_resp,
           count(*) FILTER (WHERE resp_time IS NOT NULL AND rating <= 2)      AS n_resp_low,
           count(*) FILTER (WHERE rating <= 2)                                AS n_low
    FROM phase4_reviews GROUP BY gmap_id
),
profiled AS (
    SELECT p.gmap_id,
           p.n_resp_low::numeric / NULLIF(p.n_low, 0) AS low_response_rate,
           b.first_response, b.grp
    FROM resp_profile p JOIN phase4_business b USING (gmap_id)
    JOIN phase4b_cohort cohort USING (gmap_id)
    WHERE p.n_resp >= 5 AND p.n_low >= 5 AND b.first_response IS NOT NULL
      AND cohort.has_full_followup AND cohort.grp = 'responder'
),
win AS (
    SELECT pr.gmap_id, pr.low_response_rate,
        avg(r.rating) FILTER (WHERE r.review_time >= pr.first_response - INTERVAL '12 months'
                                AND r.review_time <  pr.first_response) AS pre_r,
        count(*)      FILTER (WHERE r.review_time >= pr.first_response - INTERVAL '12 months'
                                AND r.review_time <  pr.first_response) AS pre_n,
        avg(r.rating) FILTER (WHERE r.review_time >  pr.first_response
                                AND r.review_time <= pr.first_response + INTERVAL '12 months') AS post_r,
        count(*)      FILTER (WHERE r.review_time >  pr.first_response
                                AND r.review_time <= pr.first_response + INTERVAL '12 months') AS post_n
    FROM profiled pr JOIN phase4_reviews r USING (gmap_id)
    GROUP BY pr.gmap_id, pr.low_response_rate
)
SELECT CASE WHEN low_response_rate >= 0.75 THEN 'replies to most 1-2 star'
            WHEN low_response_rate >= 0.25 THEN 'replies to some'
            ELSE 'rarely replies to 1-2 star' END AS targeting,
       count(*) AS n_biz,
       round(avg(pre_r)::numeric, 3)          AS pre_rating,
       round(avg(post_r - pre_r)::numeric, 4) AS change
FROM win WHERE pre_n >= 5 AND post_n >= 5
GROUP BY 1 ORDER BY 1;
"""


def fmt(colnames, rows):
    widths = [len(c) for c in colnames]
    srows = [[('' if v is None else str(v)) for v in r] for r in rows]
    for r in srows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(v))
    out = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(colnames)),
           "-" * (sum(widths) + 2 * (len(widths) - 1))]
    out += ["  ".join(v.ljust(widths[i]) for i, v in enumerate(r)) for r in srows]
    out.append(f"[{len(rows)} row(s)]")
    return "\n".join(out)


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT setseed(0.42)")
    cur.execute(BUILD_COHORT)
    conn.commit()
    cur.execute("SELECT grp, count(*), count(*) FILTER (WHERE has_full_followup) "
                "FROM phase4b_cohort GROUP BY grp ORDER BY grp")
    print("cohort (one fixed assignment; analyses use full-followup rows only):")
    for grp, n, full in cur.fetchall():
        print(f"   {grp:10s} {n:>7,} businesses, {full:>7,} with a full 12-month follow-up")

    sections = [
        ("B1 - Response adoption over time (share of reviews receiving an owner reply)", Q_ADOPTION),
        ("B2 - Who gets replied to, and how fast, by star rating", Q_BY_RATING),
        ("B3 - NAIVE before/after around first response, with no comparison group.\n"
         "     Not an effect estimate: ratings drift on their own (see B4).", Q_NAIVE),
        ("B4 - MATCHED difference-in-differences (pre-rating bin x t0 year cells).\n"
         "     did = responders' change minus never-responders' change, from the same\n"
         "     pre-period rating level and the same calendar period.", Q_MATCHED),
        ("B5 - Same comparison, by pre-period rating bin", Q_MATCHED_BY_BIN),
        ("B6 - Reply targeting (descriptive, full-follow-up responders only)", Q_TARGETING),
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as rep:
        rep.write("PHASE 4B -- OWNER RESPONSES\n" + "=" * 78 + "\n\n")
        for title, sql in sections:
            print("Running:", title.split("\n")[0], flush=True)
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
            rep.write(title + "\n" + "-" * 78 + "\n")
            rep.write(fmt(cols, rows) + "\n\n\n")
            print(fmt(cols, rows) + "\n")

    cur.close()
    conn.close()
    print("Report written to", REPORT_PATH)


if __name__ == "__main__":
    main()
