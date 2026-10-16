"""Phase 4A: can rating signals rank closed businesses below open ones? AUC by year."""

from project_paths import project_file

import bisect

import psycopg2

from db_config import DB_PARAMS

REPORT_PATH = (project_file('results/04a_phase4_closure_report.txt'))

QUERY = """
WITH rel AS (
    SELECT b.gmap_id, b.grp, b.mean_rating,
           EXTRACT(YEAR FROM b.last_review)::int AS end_year, r.rating,
           EXTRACT(EPOCH FROM (b.last_review - r.review_time))/(86400*30.44) AS mb
    FROM phase4_business b JOIN phase4_reviews r USING (gmap_id)
), w AS (
    SELECT gmap_id, grp, end_year, mean_rating,
        avg(rating) FILTER (WHERE mb >= 12 AND mb < 24) AS base_r,
        count(*)    FILTER (WHERE mb >= 12 AND mb < 24) AS base_n,
        avg(rating) FILTER (WHERE mb >= 0  AND mb < 6)  AS final_r,
        count(*)    FILTER (WHERE mb >= 0  AND mb < 6)  AS final_n
    FROM rel GROUP BY 1, 2, 3, 4
)
SELECT end_year, grp, mean_rating::float, (final_r - base_r)::float, final_r::float
FROM w WHERE base_n >= 5 AND final_n >= 5
"""


def auc_closed_lower(closed, ctrl, idx):
    """P(random closed business scores LOWER than random control), ties = 0.5."""
    c = sorted(r[idx] for r in closed if r[idx] is not None)
    k = sorted(r[idx] for r in ctrl if r[idx] is not None)
    if not c or not k:
        return None
    tot = 0.0
    for v in c:
        lo = bisect.bisect_left(k, v)
        hi = bisect.bisect_right(k, v)
        tot += (len(k) - hi) + 0.5 * (hi - lo)   # controls ABOVE, plus half the ties
    return tot / (len(c) * len(k))


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(QUERY)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    lines = ["", "=" * 78,
             "A6 -- IS THE CLOSURE SIGNAL ACTUALLY USABLE? (AUC)",
             "=" * 78, "",
             "AUC = P(a random closed business scores lower than a random open one).",
             "0.50 = chance pairwise ranking. Practical utility needs a decision context.", "",
             f"{'year':6s}{'n_closed':>10s}{'n_control':>11s}{'AUC level':>11s}"
             f"{'AUC traj':>10s}{'AUC final':>11s}"]

    for yr in (2019, 2020, 2021):
        cl = [r for r in rows if r[0] == yr and r[1] == 'closed']
        ct = [r for r in rows if r[0] == yr and r[1] == 'control']
        if len(cl) < 50 or len(ct) < 50:
            continue
        a_lvl = auc_closed_lower(cl, ct, 2)
        a_trj = auc_closed_lower(cl, ct, 3)
        a_fin = auc_closed_lower(cl, ct, 4)
        lines.append(f"{yr:<6d}{len(cl):>10,}{len(ct):>11,}"
                     f"{a_lvl:>11.3f}{a_trj:>10.3f}{a_fin:>11.3f}")

    lines += [
        "",
        "INTERPRETATION",
        "These three signals rank closed versus comparison businesses only weakly",
        "in this retrospective cohort. AUC alone does not determine utility at",
        "every decision threshold or establish a forecasting error rate.",
        "",
        "The average decline is clear in 2020 and 2021. The 2019 (pre-COVID)",
        "estimate has a 95% interval spanning zero on only 135 controls, so it",
        "does NOT establish that the effect predates the pandemic.",
        "",
        "The distributions of closed and surviving businesses overlap heavily.",
        "AUC measures RANKING, not accuracy: it does not imply a",
        "particular error rate, and does not show that closure prediction is",
        "impossible in general -- only that these three signals rank weakly in",
        "this retrospective cohort.",
        "",
        "The final-window rating level (AUC 0.56-0.58) separates the groups slightly",
        "better than the trajectory (0.53-0.55). The weak signal that exists is more",
        "'rated poorly right now' than 'declining', the opposite of the",
        "leading-indicator idea this phase set out to test.",
        "",
    ]

    text = "\n".join(lines)
    print(text)
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
