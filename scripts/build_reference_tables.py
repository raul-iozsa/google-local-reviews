"""Build the state population and full-corpus review-count tables used for per-capita figures."""

from project_paths import project_file

import csv
import os
import re
import psycopg2

from db_config import DB_PARAMS

LOG_PATH = r"D:\google local project\samples\load_reviews_log.txt"
POP_CSV = project_file('results/state_population.csv')
TOTALS_CSV = project_file('results/state_review_totals.csv')

# April 1, 2020 Census Estimates Base -- U.S. Census Bureau NST-EST2024-POP.
POPULATION = {
    "Alabama": 5025369, "Alaska": 733395, "Arizona": 7158110,
    "Arkansas": 3011553, "California": 39555674, "Colorado": 5775324,
    "Connecticut": 3607701, "Delaware": 989955, "District_of_Columbia": 689545,
    "Florida": 21538192, "Georgia": 10713755, "Hawaii": 1455252,
    "Idaho": 1839140, "Illinois": 12821814, "Indiana": 6786587,
    "Iowa": 3190546, "Kansas": 2937745, "Kentucky": 4506302,
    "Louisiana": 4657874, "Maine": 1363196, "Maryland": 6181629,
    "Massachusetts": 7033132, "Michigan": 10079338, "Minnesota": 5706692,
    "Mississippi": 2961278, "Missouri": 6154854, "Montana": 1084216,
    "Nebraska": 1961996, "Nevada": 3105595, "New_Hampshire": 1377546,
    "New_Jersey": 9289014, "New_Mexico": 2117555, "New_York": 20203772,
    "North_Carolina": 10441499, "North_Dakota": 779046, "Ohio": 11799453,
    "Oklahoma": 3959405, "Oregon": 4237224, "Pennsylvania": 13002909,
    "Rhode_Island": 1097354, "South_Carolina": 5118252, "South_Dakota": 886729,
    "Tennessee": 6912347, "Texas": 29149458, "Utah": 3271608,
    "Vermont": 643082, "Virginia": 8631388, "Washington": 7707586,
    "West_Virginia": 1793736, "Wisconsin": 5894170, "Wyoming": 576844,
}


def parse_review_totals():
    """Each state's true full-corpus review count."""
    if os.path.isfile(TOTALS_CSV):
        totals = {}
        with open(TOTALS_CSV, encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)  # header
            for row in r:
                if len(row) >= 2:
                    totals[row[0]] = int(row[1])
        if totals:
            print(f"review totals loaded from {os.path.basename(TOTALS_CSV)}")
            return totals

    if not os.path.isfile(LOG_PATH):
        raise FileNotFoundError(
            f"Neither {TOTALS_CSV} nor {LOG_PATH} exists.\n"
            "Run load_reviews.py with its output teed to the log, e.g.\n"
            f'  python scripts/load_reviews.py | tee "{LOG_PATH}"')

    totals = {}
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        next(f)  # header line
        for line in f:
            m = re.match(r"^(\S+)\s+([\d,]+)\s+([\d,]+)\s*$", line)
            if m:
                totals[m.group(1)] = int(m.group(2).replace(",", ""))
    print(f"review totals loaded from {os.path.basename(LOG_PATH)}")
    return totals


def main():
    totals = parse_review_totals()
    print(f"parsed review totals for {len(totals)} states; "
          f"sum = {sum(totals.values()):,} (expect 666,324,103)")

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS state_population")
    cur.execute("CREATE TABLE state_population (state TEXT PRIMARY KEY, population BIGINT)")
    for s, p in POPULATION.items():
        cur.execute("INSERT INTO state_population VALUES (%s, %s)", (s, p))

    cur.execute("DROP TABLE IF EXISTS state_review_totals")
    cur.execute("CREATE TABLE state_review_totals (state TEXT PRIMARY KEY, total_reviews BIGINT)")
    for s, n in totals.items():
        cur.execute("INSERT INTO state_review_totals VALUES (%s, %s)", (s, n))

    conn.commit()

    with open(POP_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "population_2020_census"])
        for s, p in sorted(POPULATION.items()):
            w.writerow([s, p])

    with open(TOTALS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "total_reviews_full_corpus"])
        for s, n in sorted(totals.items()):
            w.writerow([s, n])

    cur.execute("SELECT count(*) FROM state_population")
    print("state_population rows:", cur.fetchone()[0], "(expect 51)")
    cur.execute("SELECT count(*) FROM state_review_totals")
    print("state_review_totals rows:", cur.fetchone()[0], "(expect 52, incl. 'other')")

    # every state in the analysis must have a population figure
    cur.execute("""
        SELECT count(*) FROM (SELECT DISTINCT state FROM phase3_reviews) s
        LEFT JOIN state_population p USING (state) WHERE p.state IS NULL
    """)
    print("phase3 states missing a population figure:", cur.fetchone()[0], "(expect 0)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
