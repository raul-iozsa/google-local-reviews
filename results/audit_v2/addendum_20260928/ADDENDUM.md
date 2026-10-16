# Human-audit addendum - 28 September 2026

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

## Discussed items

Identified from both assistant transcripts. `Suggested` is the label the assistant
proposed; blank where it explained a rule without proposing one, or where that
conversation's suggestions were not recorded.

| Item | Source | Pool | Annotator label | Suggested |
|---|---|---|---|---|
| IT-020D652AEF | assistant 1 | probability_sample | neutral |  |
| IT-2B3285E651 | assistant 1 | panel_coldwarm_warm | positive |  |
| IT-6CA1A3D1A1 | assistant 1 | panel_extremes | negative |  |
| IT-C545370B12 | both | panel_model_disagreement | negative | negative |
| IT-DEDCEB8953 | assistant 2 | panel_model_disagreement | positive |  |
| IT-AF5AA3DFA9 | assistant 2 | probability_sample | negative | negative |
| IT-6071B04D7D | assistant 2 | probability_sample | positive | positive |
| IT-CCB33ED9FC | assistant 2 | panel_model_disagreement | negative | negative |
| IT-F325334165 | assistant 2 | panel_model_disagreement | negative | negative |
| IT-4B7D137741 | assistant 2 | probability_sample | positive | positive |
| IT-4C61B006DB | assistant 2 | panel_coldwarm_cold | neutral | positive |
| IT-7CC9565B77 | assistant 2 | probability_sample | positive | positive |
| IT-BC57474D97 | assistant 2 | probability_sample | positive | positive |
| IT-E58D157188 | assistant 2 | probability_sample | positive | positive |
| IT-58EE30B8BB | assistant 2 | probability_sample | negative | negative |
| IT-57B426F115 | assistant 2 | panel_extremes | positive | positive |
| IT-3AAC14C751 | assistant 2 | panel_extremes | mixed | mixed |
| IT-877071D221 | assistant 2 | probability_sample | cannot_tell | cannot_tell |
| IT-D172627655 | assistant 2 | panel_model_disagreement | negative | negative |
| IT-0FE7EC23D0 | assistant 2 | panel_model_disagreement | neutral | negative |
| IT-DB19840162 | assistant 2 | probability_sample | neutral | negative |
| IT-97BD46E8E4 | assistant 2 | probability_sample | negative | negative |
| IT-9514E19C5F | assistant 2 | panel_model_disagreement | negative | negative |
| IT-2FAA491705 | assistant 2 | panel_extremes | positive | positive |
| IT-33C8A35A9D | assistant 2 | panel_extremes | cannot_tell | cannot_tell |
