"""Extract every review of the Phase 4 businesses from the raw files (review length, not text)."""

import csv
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from db_config import DB_PARAMS

STATES = ["New_York", "Illinois", "Washington", "Colorado", "Georgia"]
RAW_DIR = Path(r"D:\google local project\raw\reviews")
OUT_DIR = Path(r"D:\google local project\samples\phase4")


def epoch_ms_to_iso(ms):
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def load_targets():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT state, gmap_id FROM phase4_targets")
    by_state = {s: set() for s in STATES}
    for state, gmap_id in cur.fetchall():
        by_state.setdefault(state, set()).add(gmap_id)
    cur.close()
    conn.close()
    return by_state


def process_state(state, targets):
    src = RAW_DIR / f"review-{state}.json.gz"
    out = OUT_DIR / f"{state}.csv"
    seen = kept = 0
    t0 = time.time()

    with gzip.open(src, "rt", encoding="utf-8") as f, \
         open(out, "w", newline="", encoding="utf-8") as of:
        w = csv.writer(of)
        for line in f:
            seen += 1
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if rec.get("gmap_id") not in targets:
                continue
            # same exclusion as the _clean views
            if rec.get("user_id") is None or rec.get("rating") is None:
                continue

            resp = rec.get("resp") or {}
            text = rec.get("text") or ""
            resp_text = resp.get("text") or ""
            w.writerow([
                rec.get("gmap_id", ""),
                rec.get("user_id", ""),
                rec.get("rating", ""),
                epoch_ms_to_iso(rec.get("time")),
                len(text),
                epoch_ms_to_iso(resp.get("time")),
                len(resp_text),
            ])
            kept += 1

    return seen, kept, time.time() - t0


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_state = load_targets()
    print(f"{'state':14s} {'lines read':>13s} {'kept':>11s} {'targets':>9s} {'secs':>7s}", flush=True)
    tot_kept = 0
    for state in STATES:
        targets = by_state.get(state, set())
        seen, kept, secs = process_state(state, targets)
        tot_kept += kept
        print(f"{state:14s} {seen:>13,} {kept:>11,} {len(targets):>9,} {secs:>7.0f}", flush=True)
    print(f"\ntotal reviews extracted: {tot_kept:,}")


if __name__ == "__main__":
    main()
