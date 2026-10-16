"""Phase 3: raw and category-standardized state rankings."""

from project_paths import project_file

import psycopg2

from db_config import DB_PARAMS

REPORT_PATH = (project_file('results/03_phase3_state_comparison_report.txt'))

CELLS_CTE = """
WITH cells AS (
    SELECT state, category,
           count(*)                                                AS n,
           avg(rating)::numeric                                    AS mean_r,
           var_samp(rating)::numeric                               AS var_r,
           (count(*) FILTER (WHERE rating = 1))::numeric / count(*) AS p1,
           (count(*) FILTER (WHERE rating = 5))::numeric / count(*) AS p5
    FROM phase3_reviews
    GROUP BY state, category
),
common AS (
    SELECT category FROM cells WHERE n >= 100
    GROUP BY category HAVING count(DISTINCT state) = 51
),
wt AS (
    SELECT c.category, sum(c.n)::numeric AS w
    FROM cells c JOIN common k USING (category) GROUP BY c.category
),
tot AS (SELECT sum(w) AS tw FROM wt)
"""

Q_RAW = """
SELECT state, count(*) AS n,
       round(avg(rating)::numeric, 3) AS mean_rating,
       round((stddev_samp(rating) / sqrt(count(*)))::numeric, 4) AS se,
       round(100.0 * count(*) FILTER (WHERE rating = 1) / count(*), 2) AS pct_1star,
       round(100.0 * count(*) FILTER (WHERE rating = 5) / count(*), 2) AS pct_5star,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY text_len) AS median_len
FROM phase3_reviews GROUP BY state ORDER BY mean_rating DESC;
"""

Q_STD = CELLS_CTE + """
SELECT c.state,
       round(sum(w.w * c.mean_r) / (SELECT tw FROM tot), 3) AS std_mean_rating,
       round(sqrt(sum(power(w.w / (SELECT tw FROM tot), 2) * c.var_r / c.n)), 4) AS std_se,
       round(100 * sum(w.w * c.p1) / (SELECT tw FROM tot), 2) AS std_pct_1star,
       round(100 * sum(w.w * c.p5) / (SELECT tw FROM tot), 2) AS std_pct_5star
FROM cells c JOIN wt w USING (category)
GROUP BY c.state ORDER BY std_mean_rating DESC;
"""

Q_RANK_CHANGE = CELLS_CTE + """
, raw AS (SELECT state, avg(rating)::numeric AS m FROM phase3_reviews GROUP BY state),
  std AS (SELECT c.state, sum(w.w * c.mean_r) / (SELECT tw FROM tot) AS m
          FROM cells c JOIN wt w USING (category) GROUP BY c.state)
SELECT raw.state,
       round(raw.m, 3) AS raw_mean,
       rank() OVER (ORDER BY raw.m DESC) AS raw_rank,
       round(std.m, 3) AS std_mean,
       rank() OVER (ORDER BY std.m DESC) AS std_rank,
       (rank() OVER (ORDER BY raw.m DESC)) - (rank() OVER (ORDER BY std.m DESC)) AS rank_change
FROM raw JOIN std USING (state)
ORDER BY abs((rank() OVER (ORDER BY raw.m DESC)) - (rank() OVER (ORDER BY std.m DESC))) DESC;
"""

Q_RESTAURANT = """
SELECT state, count(*) AS n,
       round(avg(rating)::numeric, 3) AS restaurant_mean_rating,
       round((stddev_samp(rating) / sqrt(count(*)))::numeric, 4) AS se
FROM phase3_reviews WHERE category = 'Restaurant'
GROUP BY state ORDER BY restaurant_mean_rating DESC;
"""

Q_PER_CAPITA = """
SELECT t.state, t.total_reviews, p.population,
       round(t.total_reviews::numeric / p.population, 2) AS reviews_per_capita
FROM state_review_totals t JOIN state_population p USING (state)
ORDER BY reviews_per_capita DESC;
"""


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


def spearman(rank_map_a, rank_map_b):
    """Rank correlation between two {state: value} maps (higher value = rank 1)."""
    states = sorted(set(rank_map_a) & set(rank_map_b))
    a = sorted(states, key=lambda s: -rank_map_a[s])
    b = sorted(states, key=lambda s: -rank_map_b[s])
    ra = {s: i for i, s in enumerate(a)}
    rb = {s: i for i, s in enumerate(b)}
    n = len(states)
    d2 = sum((ra[s] - rb[s]) ** 2 for s in states)
    return 1 - (6 * d2) / (n * (n * n - 1))


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    sections = [
        ("Q1 - RAW state ranking (uncontrolled)", Q_RAW),
        ("Q2 - CATEGORY-STANDARDIZED state ranking (direct standardization, 66 common categories)", Q_STD),
        ("Q3 - THE FINDING: raw vs standardized rank, biggest movers first", Q_RANK_CHANGE),
        ("Q4 - Robustness check: 'Restaurant' category only", Q_RESTAURANT),
        ("Q5 - Reviews per capita (full-corpus counts / 2020 Census population)", Q_PER_CAPITA),
    ]

    results = {}
    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("PHASE 3 -- STATE COMPARISON, WITH CATEGORY CONTROL\n")
        report.write("=" * 78 + "\n\n")

        for title, sql in sections:
            print("Running:", title)
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
            results[title] = (cols, rows)
            report.write(title + "\n" + "-" * len(title) + "\n")
            report.write(format_table(cols, rows) + "\n\n\n")

        raw_map = {r[0]: float(r[2]) for r in results[sections[0][0]][1]}
        std_map = {r[0]: float(r[1]) for r in results[sections[1][0]][1]}
        rest_map = {r[0]: float(r[2]) for r in results[sections[3][0]][1]}

        rho_raw_std = spearman(raw_map, std_map)
        rho_std_rest = spearman(std_map, rest_map)

        report.write("SUMMARY STATISTICS\n" + "-" * 18 + "\n")
        report.write(f"Spearman rank correlation, raw vs standardized ranking: {rho_raw_std:+.3f}\n")
        report.write(f"Spearman rank correlation, standardized vs restaurants-only: {rho_std_rest:+.3f}\n\n")
        report.write(f"Raw spread      (max - min mean rating): "
                     f"{max(raw_map.values()) - min(raw_map.values()):.3f}\n")
        report.write(f"Standardized spread                    : "
                     f"{max(std_map.values()) - min(std_map.values()):.3f}\n")

        print(f"\nSpearman raw vs standardized:      {rho_raw_std:+.3f}")
        print(f"Spearman standardized vs restaurant: {rho_std_rest:+.3f}")

    cur.close()
    conn.close()
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
