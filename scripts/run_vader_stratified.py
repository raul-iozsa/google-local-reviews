"""Score every text review in the stratified sample with VADER."""

import csv
import time

import psycopg2
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from db_config import DB_PARAMS

OUT_CSV = r"D:\google local project\samples\vader_scores_stratified.csv"
BATCH = 50_000


def main():
    analyzer = SentimentIntensityAnalyzer()

    conn = psycopg2.connect(**DB_PARAMS)
    read_cur = conn.cursor(name="vader_stream_strat")
    read_cur.itersize = BATCH
    read_cur.execute("""
        SELECT review_id, text
        FROM reviews_stratified_clean
        WHERE text IS NOT NULL AND text <> ''
    """)

    n = 0
    t0 = time.time()
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for review_id, text in read_cur:
            w.writerow([review_id, f"{analyzer.polarity_scores(text)['compound']:.4f}"])
            n += 1
            if n % 500_000 == 0:
                print(f"  {n:>9,} scored   {n / (time.time() - t0):,.0f}/sec", flush=True)
    read_cur.close()

    elapsed = time.time() - t0
    print(f"scored {n:,} reviews in {elapsed/60:.1f} min ({n/elapsed:,.0f}/sec)")

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS sentiment_stratified")
    cur.execute("""
        CREATE TABLE sentiment_stratified (
            review_id BIGINT PRIMARY KEY,
            vader_compound REAL
        )
    """)
    cur.execute("COPY sentiment_stratified (review_id, vader_compound) "
                "FROM %s WITH (FORMAT csv)", (OUT_CSV,))
    conn.commit()

    cur.execute("SELECT count(*) FROM sentiment_stratified")
    print(f"sentiment_stratified: {cur.fetchone()[0]:,} rows")

    # Should closely match the global sample's per-star means.
    cur.execute("""
        SELECT r.rating, round(avg(s.vader_compound)::numeric, 4)
        FROM sentiment_stratified s JOIN reviews_stratified_clean r USING (review_id)
        GROUP BY r.rating ORDER BY r.rating
    """)
    print("\nmean compound by star (global sample was -0.253 / -0.009 / 0.251 / 0.551 / 0.696):")
    for rating, mc in cur.fetchall():
        print(f"   {rating} star: {mc}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
