# Human audit analysis plan, version 2

This plan is saved and hashed before main annotation. Model scores stay hidden
from annotators. The codebook can be refined using the pilot, then frozen with
the supplied command before main annotation begins.

**Population and sampling.** The finite frame is `reviews_global_clean` with
at least 20 characters, excluding the saved IDs of published/familiar examples.
A seeded reservoir over IDs in ascending order draws 275 items, then randomly
allocates 25 to the pilot and 250 to the probability sample. Each main item has
unconditional inclusion probability 250/N after exposure exclusions. The pilot
does not reduce that unconditional N. Counts and the ordered-frame hash are
recorded. A changed frame is a different sample even with the same seed.
This is not direct sampling from the full raw corpus. Shorter nonempty texts
are out of scope and their count is reported.

**Primary descriptive outcomes.** Report all five human-label proportions in
the 250-item probability sample with individual Wilson 95% intervals. These
are marginal intervals, not a simultaneous confidence region. Report model
disagreement conditional on human labels positive/neutral/negative. Exclude
mixed and cannot-tell from that comparison, state the denominator, and report
their prevalence separately. Do not call excluded cases model successes or
failures. No prevalence estimator combines the diagnostic panels with the
probability sample.

**Model rules.** VADER uses the existing full-text compound score with positive
>=0.05, negative <=-0.05, and neutral otherwise. BERT is the pinned cached
nlptown multilingual sentiment model, argmax stars 1–2 negative, 3 neutral,
4–5 positive. The exact commit and software versions are saved. BERT reads
normalized displayed text truncated to 256 tokens including special tokens;
VADER's stored score comes from the original full text. This input difference
is a limitation. Every main item must have a prediction; partial joins fail.

**Secondary comparisons.** Among human-positive/negative items only, report
the project's forced binary choices: VADER compound >=0 positive; BERT
P(4)+P(5) >= P(1)+P(2) positive. Show confusion tables. These are sensitivity
results and do not replace the prespecified three-way primary comparison.

**Diagnostic panels.** Report each panel separately as descriptive counts and
fractions, without population confidence claims. The cold/warm categories
were selected using the existing VADER results. Pair five-star items within
10 displayed characters and retain pair IDs. Report paired label counts and
the paired positive-label fraction contrast. This is exploratory and not
causal. Publish the saved categories only after annotation is complete.

**Human agreement.** Keep both sets of original independent labels. Report
the 50-item confusion table, exact agreement, its Wilson interval, and Cohen's
kappa (unavailable if its denominator is zero). This subset mixes diagnostic
and random items; agreement does not estimate corpus-wide reliability. A
single annotator can be reported explicitly, with no manufactured agreement
statistic. No automatic adjudication changes the primary labels.

**Further exploratory work.** Token-truncation flags and tags are retained
for descriptive error breakdowns. Any later analysis of tags, languages or
long texts must disclose its exploratory status and small subgroup sizes.
Do not search across definitions for the most favourable result. Optional
implied stars are secondary and are not the primary sentiment reference.

**Integrity.** Exact counts, unique IDs, disjoint pilot/main membership,
exposure exclusions, pair lengths, weights, text identity, model coverage,
and the frozen rubric are validated. Missing labels stop the final analysis.
Existing run folders and existing analysis/prediction outputs are never
overwritten. The original audit folder is retained as an archive.
