"""Pick the Phase 4 businesses: every permanently closed business with 20+ reviews in
five states, plus about three open controls per closed one, matched on category and size."""

import psycopg2

from db_config import DB_PARAMS

STATES = ["New_York", "Illinois", "Washington", "Colorado", "Georgia"]
MIN_REVIEWS = 20
CONTROLS_PER_CLOSED = 3
SEED = 0.42  # for setseed(), so the control draw is reproducible

SQL = """
DROP TABLE IF EXISTS phase4_targets;

CREATE TABLE phase4_targets AS
WITH pool AS (
    SELECT gmap_id, state, category, num_of_reviews,
           CASE WHEN num_of_reviews <  50 THEN '20-49'
                WHEN num_of_reviews < 100 THEN '50-99'
                WHEN num_of_reviews < 250 THEN '100-249'
                ELSE '250+' END AS band,
           (business_status = 'Permanently closed') AS is_closed
    FROM businesses_clean
    WHERE state = ANY(%(states)s)
      AND num_of_reviews >= %(minrev)s
      AND category IS NOT NULL AND category <> ''
      -- 'Temporarily closed' is excluded from both groups (mostly COVID closures).
      AND business_status IS DISTINCT FROM 'Temporarily closed'
),
closed AS (
    SELECT * FROM pool WHERE is_closed
),
cell_quota AS (
    SELECT category, band, count(*) * %(ratio)s AS quota
    FROM closed GROUP BY category, band
),
ranked_controls AS (
    SELECT p.*,
           row_number() OVER (PARTITION BY p.category, p.band ORDER BY random()) AS rn
    FROM pool p
    WHERE NOT p.is_closed
),
controls AS (
    SELECT r.gmap_id, r.state, r.category, r.num_of_reviews, r.band, r.is_closed
    FROM ranked_controls r
    JOIN cell_quota q ON q.category = r.category AND q.band = r.band
    WHERE r.rn <= q.quota
)
SELECT gmap_id, state, category, num_of_reviews, band, 'closed' AS grp FROM closed
UNION ALL
SELECT gmap_id, state, category, num_of_reviews, band, 'control' AS grp FROM controls;

ALTER TABLE phase4_targets ADD PRIMARY KEY (gmap_id);
CREATE INDEX idx_p4t_grp ON phase4_targets (grp);
"""


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT setseed(%s)", (SEED,))
    cur.execute(SQL, {"states": STATES, "minrev": MIN_REVIEWS,
                      "ratio": CONTROLS_PER_CLOSED})
    conn.commit()

    cur.execute("""
        SELECT grp, count(*), sum(num_of_reviews),
               round(avg(num_of_reviews)::numeric, 1)
        FROM phase4_targets GROUP BY grp ORDER BY grp
    """)
    print(f"{'group':9s} {'businesses':>11s} {'total reviews':>15s} {'mean/biz':>9s}")
    total_rev = 0
    for grp, n, tot, avg in cur.fetchall():
        total_rev += tot
        print(f"{grp:9s} {n:>11,} {tot:>15,} {avg:>9}")
    print(f"\nreviews to extract (approx): {total_rev:,}")

    # Confirm the matching actually balanced the two groups.
    cur.execute("""
        SELECT band,
               count(*) FILTER (WHERE grp='closed')  AS closed,
               count(*) FILTER (WHERE grp='control') AS control
        FROM phase4_targets GROUP BY band ORDER BY band
    """)
    print("\nbalance by review-count band:")
    for band, c, k in cur.fetchall():
        ratio = (k / c) if c else 0
        print(f"   {band:8s} closed={c:>7,}  control={k:>7,}  ratio={ratio:.2f}")

    cur.execute("SELECT count(DISTINCT category) FROM phase4_targets")
    print(f"\ndistinct categories represented: {cur.fetchone()[0]:,}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
