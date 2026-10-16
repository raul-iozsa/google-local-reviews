"""Phase 6: build the text-vs-stars gap tables (sql/06) and the category and length results.

Statements are split on ';', so the SQL file must not use ';' inside strings or comments."""

from project_paths import project_file

import csv
import os

import psycopg2

from db_config import DB_PARAMS

ROOT = project_file('')
SQL_PATH = os.path.join(ROOT, "sql", "06_phase6_gap.sql")
REPORT = os.path.join(ROOT, "results", "06_phase6_gap_report.txt")
CSV_DIR = os.path.join(ROOT, "results", "csv")


def statements(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("--")]
    return [s.strip() for s in "".join(lines).split(";") if s.strip()]


def fmt(cols, rows, limit=None):
    rows = rows if limit is None else rows[:limit]
    w = [len(c) for c in cols]
    s = [["" if v is None else str(v) for v in r] for r in rows]
    for r in s:
        for i, v in enumerate(r):
            w[i] = max(w[i], len(v))
    out = ["  ".join(c.ljust(w[i]) for i, c in enumerate(cols)),
           "-" * (sum(w) + 2 * (len(w) - 1))]
    out += ["  ".join(v.ljust(w[i]) for i, v in enumerate(r)) for r in s]
    return "\n".join(out)


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1))


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def main():
    os.makedirs(CSV_DIR, exist_ok=True)
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    results = []
    for stmt in statements(SQL_PATH):
        head = stmt.split(None, 1)[0].upper()
        print("executing:", stmt.splitlines()[0][:70], flush=True)
        cur.execute(stmt)
        if head in ("SELECT", "WITH"):
            results.append(([d.name for d in cur.description], cur.fetchall()))
        else:
            conn.commit()

    (cat_cols, cat_rows), (len_cols, len_rows) = results

    gaps = [float(r[3]) for r in cat_rows]
    gaps_len = [float(r[5]) for r in cat_rows]
    rho = spearman(gaps, gaps_len)
    mean_abs = sum(abs(g) for g in gaps) / len(gaps)
    mean_abs_len = sum(abs(g) for g in gaps_len) / len(gaps_len)

    write_csv(os.path.join(CSV_DIR, "p6_category_gap.csv"), cat_cols, cat_rows)
    write_csv(os.path.join(CSV_DIR, "p6_length_vader.csv"), len_cols, len_rows)

    with open(REPORT, "w", encoding="utf-8") as rep:
        rep.write("PHASE 6 -- WHERE TEXT AND STARS DISAGREE\n" + "=" * 78 + "\n\n")
        rep.write("gap = VADER compound minus the corpus mean compound for the SAME star rating.\n")
        rep.write("Negative = text colder than is typical for that rating.\n\n")

        rep.write(f"Q1 - Category gap, {len(cat_rows)} categories with >= 1,000 scored reviews\n")
        rep.write("-" * 78 + "\n")
        rep.write("COLDEST 25 (text more negative than the stars suggest):\n")
        rep.write(fmt(cat_cols, cat_rows, 25) + "\n\n")
        rep.write("WARMEST 25 (text more positive than the stars suggest):\n")
        rep.write(fmt(cat_cols, list(reversed(cat_rows)), 25) + "\n\n\n")

        rep.write("Q2 - Review length vs VADER\n" + "-" * 78 + "\n")
        rep.write("len_bucket: 1 = <50 chars, 2 = 50-149, 3 = 150-399, 4 = 400+\n")
        rep.write(fmt(len_cols, len_rows) + "\n\n")
        rep.write(f"P4 check -- Spearman rho, category gap vs length-controlled gap: {rho:+.3f}\n")
        rep.write(f"            mean |gap| uncontrolled {mean_abs:.4f}  ->  "
                  f"length-controlled {mean_abs_len:.4f}\n\n\n")

    print(f"\n{len(cat_rows)} categories | rho(gap, gap_lenctl) = {rho:+.3f} | "
          f"mean|gap| {mean_abs:.4f} -> {mean_abs_len:.4f}")
    print("\nCOLDEST 15:")
    print(fmt(cat_cols, cat_rows, 15))
    print("\nWARMEST 15:")
    print(fmt(cat_cols, list(reversed(cat_rows)), 15))
    print("\nLENGTH:")
    print(fmt(len_cols, len_rows))

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
