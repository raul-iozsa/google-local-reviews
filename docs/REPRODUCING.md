# Reproducing the project

There are two levels: checking the saved results, which needs only Python, and
rebuilding everything from the raw data, which needs the 51 GB archive and a
PostgreSQL database. Run every command from the project folder.

## Checking the saved results

No database, raw data or model downloads are needed:

```bash
python scripts/verify_project.py
```

It runs read-only checks that the README, the documents in `docs/`, the reports,
the CSVs and the charts agree with each other, and that the human-audit archive
is unchanged. To also redraw the charts and run the regression tests, install
the smaller set of packages:

```bash
pip install -r requirements-checks.txt
python scripts/finalize_outputs.py
python -m unittest discover -s tests -v
```

`finalize_outputs.py` re-inserts the correction notes into the reports, rebuilds
the combined reliability table, rewrites the human-audit sections, refreshes the
numbers filled in automatically, redraws the charts and then runs the checks.
The tests break copies of these outputs on purpose to confirm the checks catch
it. None of this certifies the statistics, reruns the raw archive, or replaces
independent peer review.

## Rebuilding from the raw data

Requires PostgreSQL 18, Python 3.14, and ~60 GB for the raw archive.

```bash
pip install -r requirements.txt
cp .env.example .env        # then set GL_DB_PASSWORD
```

Credentials are read from the environment (`scripts/db_config.py`); no
password appears in source. Run in this order - each step depends on the
previous ones:

```bash
# 1. raw archive -> sampled CSVs (slow: parses ~51 GB of gzipped JSON)
python scripts/load_reviews.py
python scripts/load_meta.py

# 2. create tables, COPY the samples in, index, verify
python scripts/run_load_and_verify.py

# 3. clean views + the derived tables every later phase depends on
#    (businesses_clean, phase3_reviews) -- asserts expected row counts
python scripts/build_derived_tables.py

# 4. reference data for per-capita figures
python scripts/build_reference_tables.py

# 5. analyses, in order
python scripts/run_phase2.py
python scripts/run_phase3.py
python scripts/run_phase3_reliability.py

python scripts/phase4_build_targets.py        # select businesses
python scripts/phase4_extract_reviews.py      # full histories from raw
python scripts/phase4_load.py
python scripts/run_phase4a_closure.py
python scripts/run_phase4a_predictive.py
python scripts/run_phase4b_responses.py

python scripts/run_vader.py                   # ~16 min, global sample
python scripts/run_vader_stratified.py        # ~16 min, stratified sample
python scripts/phase5_build_sets.py
python scripts/run_phase5_ml.py
python scripts/run_phase5_bert.py             # CPU only, ~20-40 min
python scripts/run_phase5_compare.py

python scripts/run_phase6_category_gap.py     # also builds phase6_gap_fine
python scripts/run_phase6_bert_check.py
python scripts/run_phase6_extremes.py
python scripts/run_phase6_state_gap.py

# 6. database exports, then finalize saved outputs
python scripts/export_chart_data.py
python scripts/finalize_outputs.py

# 7. regression tests
python -m unittest discover -s tests -v
```

Loading recreates the database tables, so use a dedicated database.

## Known reproducibility limits

- **Not bit-reproducible.** Sampling uses PostgreSQL `random()` with
  `setseed`, which is not invariant to query plans or scan order, and
  `ntile` splits tied review lengths arbitrarily. Rerunning Phase 6 moved
  the state-gap reliability from 0.811 to 0.8134 for exactly this reason.
  The reported headline interpretations survived the documented reruns;
  this is not a general guarantee for future versions.
- **Raw-data paths.** The raw `.gz` archive is not in the repo, and
  `load_reviews.py` uses a literal `D:\google local project` path. The
  `GL_DATA_ROOT` setting in `db_config.py` is defined but not yet wired through
  the scripts, so edit the constants at the top of the loader scripts to
  relocate the archive. Project reports, SQL inputs and charts follow this checkout.
