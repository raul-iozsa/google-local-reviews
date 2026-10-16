"""Read each state's business metadata file and write one CSV per state for loading."""

import csv
import gzip
import json
from pathlib import Path

from states import STATES

RAW_DIR = Path(r"D:\google local project\raw\meta")
OUT_DIR = Path(r"D:\google local project\samples\meta")


def clean_text(value):
    return (value or "").replace("\x00", "")


def first_category(categories):
    if isinstance(categories, list) and categories:
        return categories[0]
    return ""


def flatten(record, state):
    return [
        record.get("gmap_id", ""),
        clean_text(record.get("name")),
        state,
        first_category(record.get("category")),
        record.get("price") or "",
        record.get("latitude", ""),
        record.get("longitude", ""),
        record.get("avg_rating", ""),
        record.get("num_of_reviews", ""),
        clean_text(record.get("state")),   # the source's "state" field is a business status
    ]


def process_state(state):
    src = RAW_DIR / f"meta-{state}.json.gz"
    out = OUT_DIR / f"{state}.csv"
    n = 0
    with gzip.open(src, "rt", encoding="utf-8") as f, \
         open(out, "w", newline="", encoding="utf-8") as of:
        writer = csv.writer(of)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            writer.writerow(flatten(record, state))
            n += 1
    return n


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{'state':22s} {'businesses':>12s}")
    for state in STATES:
        n = process_state(state)
        print(f"{state:22s} {n:12,d}")


if __name__ == "__main__":
    main()
