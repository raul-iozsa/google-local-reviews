"""Read each state's raw review file once and write two samples: up to 200,000
reviews per state (stratified) and a ~1.5% national sample (global)."""

import csv
import gzip
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from states import STATES

RAW_DIR = Path(r"D:\google local project\raw\reviews")
OUT_DIR = Path(r"D:\google local project\samples")
STRATIFIED_DIR = OUT_DIR / "reviews_stratified"
GLOBAL_DIR = OUT_DIR / "reviews_global"

STRATIFIED_CAP = 200_000            # max rows kept per state (Phase 3)

# Target about 10M rows nationwide: enough for stable estimates, small enough for fast queries.
TOTAL_CORPUS_REVIEWS = 666_324_103
GLOBAL_SAMPLE_TARGET = 10_000_000
GLOBAL_SAMPLE_PROB = GLOBAL_SAMPLE_TARGET / TOTAL_CORPUS_REVIEWS

RANDOM_SEED = 42                    # fixed so a re-run is reproducible


def epoch_ms_to_iso(ms):
    """Epoch milliseconds -> 'YYYY-MM-DD HH:MM:SS' string, UTC."""
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value):
    # COPY rejects NUL bytes, which a few reviews contain.
    return (value or "").replace("\x00", "")


def flatten(record, state):
    resp = record.get("resp") or {}
    return [
        record.get("user_id", ""),
        record.get("gmap_id", ""),
        state,
        record.get("rating", ""),
        epoch_ms_to_iso(record.get("time")),
        clean_text(record.get("text")),
        epoch_ms_to_iso(resp.get("time")),
        clean_text(resp.get("text")),
    ]


def process_state(state, rng):
    src = RAW_DIR / f"review-{state}.json.gz"
    reservoir = []
    n_seen = 0

    global_path = GLOBAL_DIR / f"{state}.csv"
    with gzip.open(src, "rt", encoding="utf-8") as f, \
         open(global_path, "w", newline="", encoding="utf-8") as gf:
        global_writer = csv.writer(gf)

        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            row = flatten(record, state)

            # Reservoir sample (Algorithm R): every review seen so far has an equal chance of being kept.
            if n_seen < STRATIFIED_CAP:
                reservoir.append(row)
            else:
                j = rng.randint(0, n_seen)
                if j < STRATIFIED_CAP:
                    reservoir[j] = row

            # Global sample: an independent weighted coin flip for every review.
            if rng.random() < GLOBAL_SAMPLE_PROB:
                global_writer.writerow(row)

            n_seen += 1

    strat_path = STRATIFIED_DIR / f"{state}.csv"
    with open(strat_path, "w", newline="", encoding="utf-8") as sf:
        csv.writer(sf).writerows(reservoir)

    return n_seen, len(reservoir)


def main():
    STRATIFIED_DIR.mkdir(parents=True, exist_ok=True)
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)

    print(f"{'state':22s} {'total_reviews':>14s} {'stratified':>11s}")
    for state in STATES:
        total, kept = process_state(state, rng)
        print(f"{state:22s} {total:14,d} {kept:11,d}")


if __name__ == "__main__":
    main()
