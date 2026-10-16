"""Phase 4A: do ratings fall before a business closes?

Each business is anchored on its last review and compared with its own baseline;
closed and control businesses are compared within the same year."""

from project_paths import project_file

import psycopg2

from db_config import DB_PARAMS

REPORT_PATH = (project_file('results/04a_phase4_closure_report.txt'))

REL = """
WITH rel AS (
    SELECT b.gmap_id, b.grp,
           EXTRACT(YEAR FROM b.last_review)::int AS end_year,
           r.rating,
           EXTRACT(EPOCH FROM (b.last_review - r.review_time)) / (86400*30.44) AS months_before
    FROM phase4_business b
    JOIN phase4_reviews r USING (gmap_id)
),
w AS (
    SELECT gmap_id, grp, end_year,
        avg(rating) FILTER (WHERE months_before >= 12 AND months_before < 24) AS base_r,
        count(*)    FILTER (WHERE months_before >= 12 AND months_before < 24) AS base_n,
        avg(rating) FILTER (WHERE months_before >= 0  AND months_before < 6)  AS final_r,
        count(*)    FILTER (WHERE months_before >= 0  AND months_before < 6)  AS final_n
    FROM rel GROUP BY gmap_id, grp, end_year
)
"""

Q_WHEN = """
SELECT EXTRACT(YEAR FROM last_review)::int AS end_year,
       count(*) FILTER (WHERE grp='closed')  AS closed,
       count(*) FILTER (WHERE grp='control') AS control
FROM phase4_business
GROUP BY 1 ORDER BY 1;
"""

Q_RATING = REL + """
SELECT end_year,
       count(*) FILTER (WHERE grp='closed')                                    AS n_closed,
       round(avg(final_r - base_r) FILTER (WHERE grp='closed')::numeric, 4)    AS delta_closed,
       count(*) FILTER (WHERE grp='control')                                   AS n_control,
       round(avg(final_r - base_r) FILTER (WHERE grp='control')::numeric, 4)   AS delta_control,
       round((avg(final_r - base_r) FILTER (WHERE grp='closed')
            - avg(final_r - base_r) FILTER (WHERE grp='control'))::numeric, 4) AS did,
       -- SE of the difference, to judge effect size.
       round(sqrt(
           power(stddev_samp(final_r - base_r) FILTER (WHERE grp='closed'), 2)
             / nullif(count(*) FILTER (WHERE grp='closed'), 0)
         + power(stddev_samp(final_r - base_r) FILTER (WHERE grp='control'), 2)
             / nullif(count(*) FILTER (WHERE grp='control'), 0)
       )::numeric, 4) AS did_se,
       -- 95%% interval for the difference.
       round(((avg(final_r - base_r) FILTER (WHERE grp='closed')
             - avg(final_r - base_r) FILTER (WHERE grp='control'))
         - 1.96 * sqrt(
             power(stddev_samp(final_r - base_r) FILTER (WHERE grp='closed'), 2)
               / nullif(count(*) FILTER (WHERE grp='closed'), 0)
           + power(stddev_samp(final_r - base_r) FILTER (WHERE grp='control'), 2)
               / nullif(count(*) FILTER (WHERE grp='control'), 0)))::numeric, 4) AS ci_low,
       round(((avg(final_r - base_r) FILTER (WHERE grp='closed')
             - avg(final_r - base_r) FILTER (WHERE grp='control'))
         + 1.96 * sqrt(
             power(stddev_samp(final_r - base_r) FILTER (WHERE grp='closed'), 2)
               / nullif(count(*) FILTER (WHERE grp='closed'), 0)
           + power(stddev_samp(final_r - base_r) FILTER (WHERE grp='control'), 2)
               / nullif(count(*) FILTER (WHERE grp='control'), 0)))::numeric, 4) AS ci_high
FROM w
WHERE base_n >= 5 AND final_n >= 5
GROUP BY end_year
HAVING count(*) FILTER (WHERE grp='closed') >= 50
   AND count(*) FILTER (WHERE grp='control') >= 50
ORDER BY end_year;
"""

Q_VOLUME = REL + """
SELECT end_year,
       count(*) FILTER (WHERE grp='closed')  AS n_closed,
       round(avg((final_n/6.0) / NULLIF(base_n/12.0, 0)) FILTER (WHERE grp='closed')::numeric, 3)  AS mean_ratio_closed,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (final_n/6.0) / NULLIF(base_n/12.0, 0))
             FILTER (WHERE grp='closed')::numeric, 3)                                              AS med_ratio_closed,
       count(*) FILTER (WHERE grp='control') AS n_control,
       round(avg((final_n/6.0) / NULLIF(base_n/12.0, 0)) FILTER (WHERE grp='control')::numeric, 3) AS mean_ratio_control,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (final_n/6.0) / NULLIF(base_n/12.0, 0))
             FILTER (WHERE grp='control')::numeric, 3)                                             AS med_ratio_control
FROM w
WHERE base_n >= 5
GROUP BY end_year
HAVING count(*) FILTER (WHERE grp='closed') >= 50
   AND count(*) FILTER (WHERE grp='control') >= 50
ORDER BY end_year;
"""

# Level, separately from trajectory: were closed businesses rated worse all along?
Q_LEVEL = """
SELECT grp, count(*) AS n_biz,
       round(avg(mean_rating), 3) AS mean_rating,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY mean_rating)::numeric, 3) AS median_rating
FROM phase4_business GROUP BY grp ORDER BY grp;
"""

# Same, but paired within category+band so it isn't just industry mix.
Q_LEVEL_MATCHED = """
WITH cellwise AS (
    SELECT category, band,
           avg(mean_rating) FILTER (WHERE grp='closed')  AS closed_mean,
           avg(mean_rating) FILTER (WHERE grp='control') AS control_mean,
           count(*) FILTER (WHERE grp='closed')          AS n_closed
    FROM phase4_business GROUP BY category, band
    HAVING count(*) FILTER (WHERE grp='closed') >= 5
       AND count(*) FILTER (WHERE grp='control') >= 5
)
SELECT count(*) AS n_cells,
       sum(n_closed) AS closed_biz_covered,
       round(avg(closed_mean - control_mean), 4) AS mean_gap_closed_minus_control,
       count(*) FILTER (WHERE closed_mean < control_mean) AS cells_where_closed_lower
FROM cellwise;
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

    sections = [
        ("A1 - WHEN do businesses end? (year of last review, closed vs control)", Q_WHEN),
        ("A2 - RATING trajectory: within-business change, final 6mo vs baseline 24-12mo\n"
         "     did = delta_closed - delta_control. Negative => closed businesses' ratings\n"
         "     fell MORE than comparable open businesses' over the same period.", Q_RATING),
        ("A3 - VOLUME trajectory: final monthly review rate / baseline monthly rate.\n"
         "     NOTE: alignment on last review guarantees decline in BOTH groups.\n"
         "     Only the closed-vs-control gap is interpretable, never the level.", Q_VOLUME),
        ("A4 - LEVEL (a different question): are closed businesses just rated worse?", Q_LEVEL),
        ("A5 - LEVEL, matched within category x review-band cells", Q_LEVEL_MATCHED),
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as rep:
        rep.write("PHASE 4A -- CLOSURE PREDICTION\n" + "=" * 78 + "\n\n")
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
