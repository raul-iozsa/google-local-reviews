"""Build the Phase 5 sets: 10,000 evaluation and 100,000 training reviews per star, disjoint."""

import psycopg2

from db_config import DB_PARAMS

SQL = """
DROP TABLE IF EXISTS phase5_eval;
DROP TABLE IF EXISTS phase5_train;

-- One random ranking per star level keeps eval and train disjoint.
CREATE TEMP TABLE ranked AS
SELECT review_id, rating, state, gmap_id,
       row_number() OVER (PARTITION BY rating ORDER BY random()) AS rn
FROM reviews_global_clean
WHERE text IS NOT NULL AND length(text) >= 10;

CREATE TABLE phase5_eval AS
SELECT review_id, rating, state, gmap_id FROM ranked WHERE rn <= 10000;

CREATE TABLE phase5_train AS
SELECT review_id, rating, state, gmap_id FROM ranked WHERE rn > 10000 AND rn <= 110000;

ALTER TABLE phase5_eval  ADD PRIMARY KEY (review_id);
ALTER TABLE phase5_train ADD PRIMARY KEY (review_id);
"""


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT setseed(0.42)")
    cur.execute(SQL)
    conn.commit()

    for t in ("phase5_eval", "phase5_train"):
        cur.execute(f"SELECT rating, count(*) FROM {t} GROUP BY rating ORDER BY rating")
        rows = cur.fetchall()
        total = sum(r[1] for r in rows)
        print(f"{t}: {total:,} rows")
        for rating, n in rows:
            print(f"    {rating} star: {n:,}")

    # Train and eval must not overlap.
    cur.execute("""
        SELECT count(*) FROM phase5_eval e JOIN phase5_train t USING (review_id)
    """)
    overlap = cur.fetchone()[0]
    print(f"\noverlap between eval and train: {overlap} (MUST be 0)")

    cur.execute("""
        SELECT count(*) FROM phase5_eval WHERE rating IN (1,2,4,5)
    """)
    print(f"binary-comparable eval rows (1,2,4,5): {cur.fetchone()[0]:,}")

    # Disjoint IDs are not enough: duplicate source lines get different IDs. Text overlap
    # is reported, not removed, because short common phrases repeat legitimately.
    print("\nleakage checks beyond review_id:")

    cur.execute("""
        SELECT count(*)
        FROM phase5_eval e
        JOIN reviews_global_clean re USING (review_id)
        JOIN (SELECT rt.user_id, rt.gmap_id, rt.review_time
              FROM phase5_train t JOIN reviews_global_clean rt USING (review_id)) k
          ON k.user_id = re.user_id AND k.gmap_id = re.gmap_id
         AND k.review_time = re.review_time
    """)
    print(f"    same (user_id, gmap_id, review_time) as a training row: {cur.fetchone()[0]:,}")

    cur.execute("""
        SELECT count(*) FROM phase5_eval e JOIN reviews_global_clean re USING (review_id)
        WHERE re.gmap_id IN (SELECT rt.gmap_id FROM phase5_train t
                             JOIN reviews_global_clean rt USING (review_id))
    """)
    print(f"    business also appears in training: {cur.fetchone()[0]:,}")
    print("    (shared businesses are non-independence, not label leakage --")
    print("     but they mean this does not test generalization to NEW businesses)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
