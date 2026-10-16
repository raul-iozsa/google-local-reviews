# Human audit

To check the sentiment models against a person's reading rather than star
ratings, I labelled 450 reviews by hand without seeing their stars, the model
scores or which sample each came from. 250 were drawn at random; the other 200
were selected as diagnostic cases (extreme text/star disagreements, cases where the
models disagree, and matched pairs of "cold" and "warm" business types) and are
reported separately. The labelling rules were tested on a 25-review pilot and
frozen before the main labelling. One person did all the labelling, and some
items were discussed with AI assistants along the way, as quantified below.

The sections below are generated from the locked record in
[`results/audit_v2/analysis_20260927/`](../results/audit_v2/analysis_20260927/):
its [report](../results/audit_v2/analysis_20260927/ANALYSIS_REPORT.md), a
[review of how consistently the rules were applied](../results/audit_v2/analysis_20260927/RUBRIC_REVIEW_20260927.md),
and the original inputs and code. The rules are in the
[codebook](../results/audit_v2/CODEBOOK.md) and the plan written before labelling in
[ANALYSIS_PLAN.md](../results/audit_v2/ANALYSIS_PLAN.md). The archived report and
rubric review were written during AI-assisted review and are kept unedited.

<!-- completed-human-audit:begin -->
### Completed human audit

All 450 main reviews were labelled under frozen codebook v2.1. The primary
estimate uses only the 250-item probability sample; the other 200
items are selected diagnostic panels and are reported separately.

The sampling frame contains 5,033,861 clean global-sample reviews
with at least 20 characters, after documented exposure exclusions. The
243 positive/negative/neutral labels support the three-way model comparison;
six mixed and one cannot-tell labels are excluded from that comparison.

| Model | Disagreements | Disagreement rate | Wilson 95% interval | Agreement |
|---|---:|---:|---:|---:|
| VADER | 33/243 | 13.6% | 9.8–18.5% | 86.4% |
| BERT | 17/243 | 7.0% | 4.4–10.9% | 93.0% |

BERT agrees more often with this annotator. These are human-label agreement
rates, with a different population and decision rule from the star-balanced
Phase 5 benchmark. The intervals describe sampling uncertainty, not uncertainty
about the annotator. There was one human annotator, AI discussion of some items
(quantified in the addendum below), and no independent second-annotator
agreement measurement.

The cold/warm diagnostic comparison found 49/50 versus 50/50 positive labels.
This near-ceiling result cannot measure differences in positivity intensity
or determine what fraction of the continuous model-score gap is real.
BERT still disagrees on 17/45 comparable extreme cases; it is not an adjudicator.

Original labels, optional tags and notes are preserved. Documented rubric
ambiguities remain in the primary results; optional tags were not exhaustively
applied, so a blank tag is not verified absence. Any future adjudication must
be a separately logged sensitivity analysis.
<!-- completed-human-audit:end -->

<!-- human-audit-addendum:begin -->
### Human-audit addendum (28 September 2026)

Post-hoc checks that the archived report omitted; none were in the pre-written
analysis plan. Computed by `scripts/audit_addendum.py` from the unchanged archive.

**Documented AI discussion: 25 items.** The archive's check found 4 (1 in the random sample) because its snippet list was incomplete. The two assistant conversations used during labelling together identify 25 main-sheet items, 11 in the random sample. Where a label was suggested, the annotator chose differently on 3 of 21. Excluding these identified items leaves the ranking unchanged. This checks the supplied snippet list, not every possible use of AI:

| Model | All 243 | Excluding discussed | Wilson 95% (excluding) |
|---|---:|---:|---:|
| VADER | 33/243 (13.6%) | 28/233 (12.0%) | 8.4–16.8% |
| BERT | 17/243 (7.0%) | 14/233 (6.0%) | 3.6–9.8% |

**Baseline.** 202/243 comparable labels are positive, so always answering "positive" agrees 83.1% of the time. VADER's 86.4% agreement is 3.3 points above that; BERT's 93.0% is 9.9 points above.

**Where they differ: negative reviews.** Of 38 reviews labelled negative, VADER agrees on 19 (50.0%) and BERT on 32 (84.2%). On positive reviews the gap is small: 188/202 versus 193/202. Only 3 items are labelled neutral, too few to evaluate.

**Paired test.** Both models scored the same items: VADER alone was wrong on 26, BERT alone on 10 (exact McNemar p = 0.011). This tests equal disagreement probabilities for the two models on these paired items; it does not test either model against the majority baseline. The single-annotator and sampling caveats of the primary result still apply.
<!-- human-audit-addendum:end -->

The 50-item second-annotator sheet has not been completed, so agreement between
two annotators was not measured.
