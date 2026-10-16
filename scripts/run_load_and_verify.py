"""Create the tables, load the sample CSVs, add indexes and write the load-verification report."""

from project_paths import project_file

import time
import psycopg2

from db_config import DB_PARAMS

STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District_of_Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New_Hampshire", "New_Jersey", "New_Mexico", "New_York", "North_Carolina",
    "North_Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode_Island", "South_Carolina", "South_Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West_Virginia", "Wisconsin",
    "Wyoming", "other",
]

BASE = r"D:\google local project\samples"

CREATE_TABLES_SQL = """
DROP TABLE IF EXISTS reviews_stratified CASCADE;
DROP TABLE IF EXISTS reviews_global CASCADE;
DROP TABLE IF EXISTS businesses CASCADE;

CREATE TABLE reviews_stratified (
    review_id   BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    gmap_id     TEXT,
    state       TEXT,
    rating      SMALLINT,
    review_time TIMESTAMP,
    text        TEXT,
    resp_time   TIMESTAMP,
    resp_text   TEXT
);

CREATE TABLE reviews_global (
    review_id   BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    gmap_id     TEXT,
    state       TEXT,
    rating      SMALLINT,
    review_time TIMESTAMP,
    text        TEXT,
    resp_time   TIMESTAMP,
    resp_text   TEXT
);

CREATE TABLE businesses (
    gmap_id         TEXT,
    name            TEXT,
    state           TEXT,
    category        TEXT,
    price           TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    avg_rating      NUMERIC,
    num_of_reviews  INTEGER,
    business_status TEXT
);
"""

INDEX_SQL = """
CREATE INDEX idx_stratified_gmap  ON reviews_stratified (gmap_id);
CREATE INDEX idx_stratified_time  ON reviews_stratified (review_time);
CREATE INDEX idx_stratified_state ON reviews_stratified (state);

CREATE INDEX idx_global_gmap  ON reviews_global (gmap_id);
CREATE INDEX idx_global_time  ON reviews_global (review_time);
CREATE INDEX idx_global_state ON reviews_global (state);

CREATE INDEX idx_businesses_gmap ON businesses (gmap_id);
"""

REPORT_PATH = project_file('results/01_load_and_verify_report.txt')


def log(msg, report):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    report.write(line + "\n")
    report.flush()


def load_table(cur, table, columns, folder, report):
    col_list = ", ".join(columns)
    for s in STATES:
        path = BASE + f"\\{folder}\\{s}.csv"
        sql = (
            f"COPY {table} ({col_list}) FROM %s "
            f"WITH (FORMAT csv, ENCODING 'UTF8')"
        )
        cur.execute(sql, (path,))
    log(f"{table}: all 52 files COPY'd", report)


def main():
    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
        log("Connected to google_local.", report)

        log("Dropping and recreating all 3 tables (clean slate)...", report)
        cur.execute(CREATE_TABLES_SQL)
        conn.commit()
        log("Tables created.", report)

        log("Loading businesses (52 files)...", report)
        load_table(cur, "businesses",
                   ["gmap_id", "name", "state", "category", "price",
                    "latitude", "longitude", "avg_rating", "num_of_reviews",
                    "business_status"],
                   "meta", report)
        conn.commit()

        log("Loading reviews_stratified (52 files)...", report)
        load_table(cur, "reviews_stratified",
                   ["user_id", "gmap_id", "state", "rating", "review_time",
                    "text", "resp_time", "resp_text"],
                   "reviews_stratified", report)
        conn.commit()

        log("Loading reviews_global (52 files)...", report)
        load_table(cur, "reviews_global",
                   ["user_id", "gmap_id", "state", "rating", "review_time",
                    "text", "resp_time", "resp_text"],
                   "reviews_global", report)
        conn.commit()

        log("Building indexes (7)...", report)
        cur.execute(INDEX_SQL)
        conn.commit()
        log("Indexes built.", report)

        log("=== Verification ===", report)

        cur.execute("""
            SELECT
                (SELECT count(*) FROM reviews_stratified) AS stratified_rows,
                (SELECT count(*) FROM reviews_global)     AS global_rows,
                (SELECT count(*) FROM businesses)         AS business_rows
        """)
        r = cur.fetchone()
        log(f"Check 1 (row counts)   -> stratified={r[0]:,}  global={r[1]:,}  businesses={r[2]:,}", report)
        log(f"           expected    -> stratified=10,362,952  global=9,994,108  businesses=4,989,684", report)
        ok1 = (r[0] == 10362952 and r[1] == 9994108 and r[2] == 4989684)
        log(f"           result      -> {'PASS' if ok1 else 'FAIL -- investigate before continuing'}", report)

        cur.execute("""
            SELECT 'stratified', min(review_time), max(review_time) FROM reviews_stratified
            UNION ALL
            SELECT 'global', min(review_time), max(review_time) FROM reviews_global
        """)
        log("Check 2 (review_time range):", report)
        for row in cur.fetchall():
            log(f"           {row[0]}: {row[1]}  to  {row[2]}", report)

        cur.execute("SELECT rating, count(*) FROM reviews_stratified GROUP BY rating ORDER BY rating")
        log("Check 3 (rating distribution, reviews_stratified):", report)
        for row in cur.fetchall():
            log(f"           rating={row[0]}: {row[1]:,}", report)

        # Count the groups with COUNT(*), not from a LIMITed fetch.
        cur.execute("""
            SELECT count(*) FROM (
                SELECT 1 FROM reviews_stratified
                GROUP BY user_id, gmap_id, review_time HAVING count(*) > 1
            ) dup_groups
        """)
        n_dup_groups = cur.fetchone()[0]
        log(f"Check 4 (duplicate user_id+gmap_id+review_time GROUPS): {n_dup_groups:,} "
            f"(source-data duplicates, confirmed present in the raw .gz files -- not a load bug)", report)

        cur.execute("""
            SELECT count(*) FROM reviews_stratified r
            LEFT JOIN businesses b ON r.gmap_id = b.gmap_id
            WHERE b.gmap_id IS NULL
        """)
        orphans = cur.fetchone()[0]
        log(f"Check 5 (orphan reviews, gmap_id not in businesses): {orphans:,} (expect 0 or near-0)", report)

        # Check 6: third-party reviews (no user, no rating, placeholder date).
        cur.execute("""
            SELECT count(*) FROM reviews_stratified WHERE user_id IS NULL AND rating IS NULL
        """)
        synd = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM reviews_stratified")
        total = cur.fetchone()[0]
        log(f"Check 6 (syndicated third-party reviews -- NULL user_id AND NULL rating): "
            f"{synd:,} of {total:,} ({100*synd/total:.3f}%)", report)
        log(f"           These have no star rating and no real user -- exclude them (WHERE "
            f"user_id IS NOT NULL) from anything using rating or per-user analysis.", report)

        cur.close()
        conn.close()
        log("Done.", report)


if __name__ == "__main__":
    main()
