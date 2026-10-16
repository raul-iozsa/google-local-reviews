"""Phase 6: the state gap (sql/07) and its split-half reliability (prediction P5).

Statements are split on ';', so the SQL file must not use ';' inside strings or comments."""

from project_paths import project_file

import csv
import os
import random
import statistics as st

import psycopg2

from db_config import DB_PARAMS

ROOT = project_file('')
SQL_PATH = os.path.join(ROOT, "sql", "07_phase6_state_gap.sql")
REPORT = os.path.join(ROOT, "results", "06_phase6_gap_report.txt")
CSV_DIR = os.path.join(ROOT, "results", "csv")
N_SPLITS = 200
SEED = 42


def statements(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("--")]
    return [s.strip() for s in "".join(lines).split(";") if s.strip()]


def fmt(cols, rows):
    w = [len(c) for c in cols]
    s = [["" if v is None else str(v) for v in r] for r in rows]
    for r in s:
        for i, v in enumerate(r):
            w[i] = max(w[i], len(v))
    out = ["  ".join(c.ljust(w[i]) for i, c in enumerate(cols)),
           "-" * (sum(w) + 2 * (len(w) - 1))]
    out += ["  ".join(v.ljust(w[i]) for i, v in enumerate(r)) for r in s]
    return "\n".join(out)


def spearman(a, b):
    sa = sorted(a, key=lambda s: -a[s])
    sb = sorted(b, key=lambda s: -b[s])
    ra = {s: i for i, s in enumerate(sa)}
    rb = {s: i for i, s in enumerate(sb)}
    n = len(a)
    return 1 - 6 * sum((ra[s] - rb[s]) ** 2 for s in a) / (n * (n * n - 1))


def main():
    os.makedirs(CSV_DIR, exist_ok=True)
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    results = []
    for stmt in statements(SQL_PATH):
        print("executing:", stmt.splitlines()[0][:70], flush=True)
        cur.execute(stmt)
        if stmt.split(None, 1)[0].upper() in ("SELECT", "WITH"):
            results.append(([d.name for d in cur.description], cur.fetchall()))
        else:
            conn.commit()

    (raw_cols, raw_rows), (std_cols, std_rows) = results

    for name, cols, rows in [("p6_state_gap_raw", raw_cols, raw_rows),
                             ("p6_state_gap_standardized", std_cols, std_rows)]:
        with open(os.path.join(CSV_DIR, name + ".csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)

    # P5: split-half reliability of the standardized gap
    cur.execute("""
        WITH cells AS (
            SELECT state, category, count(*) AS n, avg(gap) AS g, var_samp(gap) AS v
            FROM phase6_gap_strat
            WHERE category IS NOT NULL AND category <> ''
            GROUP BY state, category
        ),
        common AS (
            SELECT category FROM cells WHERE n >= 100
            GROUP BY category HAVING count(DISTINCT state) = 51
        )
        SELECT c.state, c.category, c.n, c.g, c.v
        FROM cells c JOIN common k USING (category)
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    weight, cell = {}, {}
    for state, cat, n, g, v in rows:
        weight[cat] = weight.get(cat, 0) + n
        cell[(state, cat)] = (n, float(g), float(v or 0))
    states = sorted({r[0] for r in rows})
    cats = sorted(weight)

    def std_gap(state, catset):
        tw = sum(weight[c] for c in catset)
        return sum(weight[c] * cell[(state, c)][1] for c in catset) / tw

    def std_se(state, catset):
        tw = sum(weight[c] for c in catset)
        return sum((weight[c] / tw) ** 2 * cell[(state, c)][2] / cell[(state, c)][0]
                   for c in catset) ** 0.5

    full = {s: std_gap(s, cats) for s in states}
    ses = [std_se(s, cats) for s in states]
    sd_obs, se_mean = st.stdev(full.values()), st.mean(ses)
    var_true = sd_obs ** 2 - se_mean ** 2
    expected_rho = var_true / (var_true + (se_mean * 2 ** 0.5) ** 2)

    rng = random.Random(SEED)
    rhos = []
    for _ in range(N_SPLITS):
        sh = cats[:]
        rng.shuffle(sh)
        h1, h2 = sh[:len(cats) // 2], sh[len(cats) // 2:]
        rhos.append(spearman({s: std_gap(s, h1) for s in states},
                             {s: std_gap(s, h2) for s in states}))
    rhos.sort()
    med = rhos[len(rhos) // 2]

    lines = ["", "=" * 78,
             "STATE GAP -- does the text-vs-stars gap differ by state?",
             "=" * 78, "",
             "All figures below are rating- AND length-controlled "
             "(gap within rating x 20 length quantiles).", "",
             "Q1 -- raw state gap (no category control), top and bottom 8:",
             fmt(raw_cols, raw_rows[:8]), "   ...",
             fmt(raw_cols, raw_rows[-8:]), "",
             "Q2 -- category-standardized state gap, top and bottom 8:",
             fmt(std_cols, std_rows[:8]), "   ...",
             fmt(std_cols, std_rows[-8:]), "",
             f"Common categories used: {len(cats)}   States: {len(states)}",
             f"Standardized gap spread (max-min): "
             f"{max(full.values()) - min(full.values()):.4f}",
             f"Observed SD across states        : {sd_obs:.4f}",
             f"Mean sampling SE per state       : {se_mean:.4f}",
             "",
             "P5 -- split-half reliability of the standardized state gap:",
             f"   observed median rho over {N_SPLITS} splits : {med:+.3f}",
             f"   expected if sampling noise were all   : {expected_rho:+.3f}",
             f"   Spearman-Brown, full category set     : {2*med/(1+med):+.3f}",
             ""]
    text = "\n".join(lines)
    print(text)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text)

    # Save the metrics for the reliability chart.
    with open(os.path.join(CSV_DIR, "metrics_phase6_reliability.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["measure", "split_half_observed", "noise_only_expected",
                    "spearman_brown_full"])
        w.writerow(["Phase 6: how warmly states WRITE", round(med, 4),
                    round(expected_rho, 4), round(2 * med / (1 + med), 4)])
    print("metrics written to metrics_phase6_reliability.csv")


if __name__ == "__main__":
    main()
