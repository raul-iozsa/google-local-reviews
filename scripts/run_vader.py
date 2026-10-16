"""Score every text review in the global sample with VADER and save the compound score."""

import csv
import time

import psycopg2
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from db_config import DB_PARAMS

OUT_CSV = r"D:\google local project\samples\vader_scores.csv"
BATCH = 50_000


def main():
    analyzer = SentimentIntensityAnalyzer()

    conn = psycopg2.connect(**DB_PARAMS)
    read_cur = conn.cursor(name="vader_stream")   # server-side: streams, no 5.7M-row fetch
    read_cur.itersize = BATCH
    read_cur.execute("""
        SELECT review_id, text
        FROM reviews_global_clean
        WHERE text IS NOT NULL AND text <> ''
    """)

    n = 0
    t0 = time.time()
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for review_id, text in read_cur:
            w.writerow([review_id, f"{analyzer.polarity_scores(text)['compound']:.4f}"])
            n += 1
            if n % 250_000 == 0:
                rate = n / (time.time() - t0)
                print(f"  {n:>9,} scored   {rate:,.0f}/sec", flush=True)
    read_cur.close()

    elapsed = time.time() - t0
    print(f"scored {n:,} reviews in {elapsed/60:.1f} min ({n/elapsed:,.0f}/sec)")

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS sentiment")
    cur.execute("""
        CREATE TABLE sentiment (
            review_id BIGINT PRIMARY KEY,
            vader_compound REAL
        )
    """)
    cur.execute("COPY sentiment (review_id, vader_compound) FROM %s WITH (FORMAT csv)", (OUT_CSV,))
    conn.commit()

    cur.execute("SELECT count(*) FROM sentiment")
    print(f"sentiment table: {cur.fetchone()[0]:,} rows")

    # Sanity: does VADER agree with stars at all, in the expected direction?
    cur.execute("""
        SELECT r.rating, count(*),
               round(avg(s.vader_compound)::numeric, 4) AS mean_compound
        FROM sentiment s JOIN reviews_global_clean r USING (review_id)
        GROUP BY r.rating ORDER BY r.rating
    """)
    print("\nmean VADER compound by star rating (should rise monotonically):")
    for rating, cnt, mc in cur.fetchall():
        print(f"   {rating} star: n={cnt:>9,}  mean compound={mc:>8}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
