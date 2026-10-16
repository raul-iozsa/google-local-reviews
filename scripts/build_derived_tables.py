"""Build businesses_clean and phase3_reviews (sql/02b) and check their row counts."""

import os

import psycopg2

from db_config import DB_PARAMS

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 02b reads the clean views, and reloading drops them, so recreate them first.
VIEWS_PATH = os.path.join(_ROOT, "sql", "03_clean_views.sql")
SQL_PATH = os.path.join(_ROOT, "sql", "02b_derived_tables.sql")

# UCSD publishes 4,963,111 points of interest; the deduplicated table must match.
EXPECTED_BUSINESSES = 4_963_111


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    print("creating clean views (03_clean_views.sql) ...", flush=True)
    with open(VIEWS_PATH, encoding="utf-8") as f:
        cur.execute(f.read())

    print("building businesses_clean and phase3_reviews ...", flush=True)
    with open(SQL_PATH, encoding="utf-8") as f:
        cur.execute(f.read())

    cur.execute("SELECT count(*) FROM businesses_clean")
    n_biz = cur.fetchone()[0]
    cur.execute("SELECT count(*), count(DISTINCT state), count(DISTINCT category) FROM phase3_reviews")
    n_p3, n_states, n_cats = cur.fetchone()

    print(f"businesses_clean : {n_biz:,} rows")
    print(f"phase3_reviews   : {n_p3:,} rows | {n_states} states | {n_cats:,} categories")

    # Check before committing, so a bad rebuild rolls back.
    if n_biz != EXPECTED_BUSINESSES:
        conn.rollback()
        raise RuntimeError(f"businesses_clean has {n_biz:,}, expected {EXPECTED_BUSINESSES:,}")
    if n_states != 51:
        conn.rollback()
        raise RuntimeError(f"expected 51 states (50 + DC, 'other' excluded), got {n_states}")
    if n_p3 < 9_000_000:
        conn.rollback()
        raise RuntimeError(f"phase3_reviews has only {n_p3:,} rows; expected ~10.1M")

    # The whole point of the PK: one review must never join to two business rows.
    cur.execute("""
        SELECT count(*) FROM (
            SELECT gmap_id FROM businesses_clean GROUP BY gmap_id HAVING count(*) > 1
        ) d
    """)
    dupes = cur.fetchone()[0]
    if dupes:
        conn.rollback()
        raise RuntimeError(f"businesses_clean still has {dupes} duplicated gmap_ids")

    conn.commit()
    print("all checks passed; committed")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
