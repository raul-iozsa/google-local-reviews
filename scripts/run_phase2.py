"""Phase 2: create the clean views and run the six descriptive queries."""

from project_paths import project_file

import psycopg2

from db_config import DB_PARAMS

VIEWS_SQL_PATH = project_file('sql/03_clean_views.sql')
REPORT_PATH = project_file('results/02_phase2_descriptive_report.txt')

QUERIES = [
    ("Q1a - Rating distribution, OVERALL (reviews_global_clean)", """
        SELECT
            rating,
            count(*) AS n,
            round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
        FROM reviews_global_clean
        GROUP BY rating
        ORDER BY rating;
    """),
    ("Q1b - Rating distribution, BY STATE (reviews_stratified_clean)", """
        SELECT
            state,
            count(*) AS n,
            round(avg(rating)::numeric, 3) AS mean_rating,
            round(100.0 * count(*) FILTER (WHERE rating = 1) / count(*), 2) AS pct_1star,
            round(100.0 * count(*) FILTER (WHERE rating = 5) / count(*), 2) AS pct_5star
        FROM reviews_stratified_clean
        GROUP BY state
        ORDER BY mean_rating DESC;
    """),
    ("Q2 - Reviews per year (reviews_global_clean)", """
        SELECT
            date_trunc('year', review_time)::date AS year,
            count(*) AS n
        FROM reviews_global_clean
        GROUP BY 1
        ORDER BY 1;
    """),
    ("Q3 - Rating inflation, mean rating by year + YoY change (reviews_global_clean)", """
        SELECT
            year,
            mean_rating,
            round(mean_rating - LAG(mean_rating) OVER (ORDER BY year), 4) AS change_from_prior_year
        FROM (
            SELECT
                date_trunc('year', review_time)::date AS year,
                avg(rating)::numeric AS mean_rating
            FROM reviews_global_clean
            GROUP BY 1
        ) yearly
        ORDER BY year;
    """),
    ("Q4 - Review length vs rating, mean + median (reviews_global_clean)", """
        SELECT
            rating,
            count(*) FILTER (WHERE text IS NOT NULL) AS n_with_text,
            round(avg(length(text))::numeric, 1) AS mean_length,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY length(text)) AS median_length
        FROM reviews_global_clean
        GROUP BY rating
        ORDER BY rating;
    """),
    ("Q5 - Category comparison, min 500 sampled reviews (reviews_global_clean x businesses)", """
        SELECT
            b.category,
            count(*) AS n,
            round(avg(r.rating)::numeric, 3) AS mean_rating
        FROM reviews_global_clean r
        JOIN businesses_clean b ON r.gmap_id = b.gmap_id
        WHERE b.category IS NOT NULL AND b.category <> ''
        GROUP BY b.category
        HAVING count(*) >= 500
        ORDER BY mean_rating DESC;
    """),
    ("Q6 - Owner response rate by rating (reviews_global_clean)", """
        SELECT
            rating,
            count(*) AS n,
            count(*) FILTER (WHERE resp_text IS NOT NULL) AS n_with_response,
            round(100.0 * count(*) FILTER (WHERE resp_text IS NOT NULL) / count(*), 2) AS pct_with_response
        FROM reviews_global_clean
        GROUP BY rating
        ORDER BY rating;
    """),
]


def format_table(colnames, rows, max_rows=60):
    widths = [len(c) for c in colnames]
    str_rows = [[str(v) for v in row] for row in rows[:max_rows]]
    for row in str_rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(v))

    lines = []
    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(colnames))
    lines.append(header)
    lines.append("-" * len(header))
    for row in str_rows:
        lines.append("  ".join(v.ljust(widths[i]) for i, v in enumerate(row)))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows not shown)")
    lines.append(f"[{len(rows)} row(s)]")
    return "\n".join(lines)


def main():
    with open(VIEWS_SQL_PATH, "r", encoding="utf-8") as f:
        views_sql = f.read()

    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(views_sql)
    conn.commit()
    print("Views created (reviews_global_clean, reviews_stratified_clean).")

    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("PHASE 2 -- DESCRIPTIVE SQL RESULTS\n")
        report.write("=" * 70 + "\n\n")

        for title, sql in QUERIES:
            print(f"Running: {title}")
            cur.execute(sql)
            colnames = [d.name for d in cur.description]
            rows = cur.fetchall()
            table = format_table(colnames, rows)

            report.write(title + "\n")
            report.write("-" * len(title) + "\n")
            report.write(table + "\n\n\n")

    cur.close()
    conn.close()
    print(f"Done. Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
