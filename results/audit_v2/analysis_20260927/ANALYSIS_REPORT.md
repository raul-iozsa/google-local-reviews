# Completed human sentiment audit — 27 September 2026

The 450-item sheet is complete and passes the project's structural and rubric-freeze checks. The analysis below uses the user's labels exactly as submitted. No labels, tags, notes, review texts or codebook rules were changed during analysis. There is one human annotator; independent inter-annotator agreement was not measured.

## Completion and integrity

- All 450 items have valid sentiment labels; all supplied tags are recognized.
- Item IDs and review texts match the generated sample. The frozen codebook and run manifest remain unchanged. The pilot file also matches its freeze-time hash.
- The second-annotator sheet is blank. The explicit single-annotator option was used; no second labels or agreement statistic were manufactured.
- There are 119 rows with tags and 34 with notes. Implied-star fields are all blank, as agreed.
- All 450 model predictions are present and match the saved model configuration and text hashes.
- A separate arithmetic calculation reproduced the analysis script's model-disagreement counts and denominators for every panel.

Across the full work assignment, the labels are 319 positive, 104 negative, 6 neutral, 17 mixed and 4 cannot-tell. These counts describe the assignment, not population prevalence: 200 items were deliberately selected diagnostic cases.

## Primary results: the 250-item probability sample

Only these 250 items support prevalence estimates for the defined sampling frame: clean global-sample reviews with at least 20 characters, after documented exposure exclusions. The frame contains 5,033,861 records. The 701,509 shorter nonempty reviews are out of scope. These are not direct estimates for all raw Google reviews.

| Human label | Count | Share |
|---|---:|---:|
| Positive | 202 | 80.8% |
| Negative | 38 | 15.2% |
| Neutral | 3 | 1.2% |
| Mixed | 6 | 2.4% |
| Cannot tell | 1 | 0.4% |

The prespecified three-way comparison uses the 243 positive/negative/neutral items. The six mixed and one cannot-tell items remain in the distribution above but are excluded from model-error calculations.

| Model | Disagrees with human label | Disagreement rate | Wilson 95% interval | Agreement rate |
|---|---:|---:|---:|---:|
| VADER | 33 / 243 | 13.6% | 9.8–18.5% | 86.4% |
| BERT | 17 / 243 | 7.0% | 4.4–10.9% | 93.0% |

BERT has 16 fewer disagreements, an observed difference of 6.6 percentage points. On the same 243 items, both models agree with the human on 200; BERT alone agrees on 26; VADER alone agrees on 10; and neither agrees on 7. The marginal intervals above are not an interval for the paired difference, and no significance claim is based on comparing their overlap.

The largest class-specific contrast is for negative text: VADER agrees on 19 of 38 human-negative items, whereas BERT agrees on 32 of 38. For human-positive text, the figures are 188/202 and 193/202. There are only three neutral items, too few for a reliable neutral-class conclusion.

The prespecified forced-binary sensitivity analysis includes 240 human-positive/negative items: VADER disagrees on 23/240 (9.6%) and BERT on 9/240 (3.8%). It uses different decision rules and a different denominator, so it should not replace the primary three-way result.

Interpret these as agreement with this annotator's judgments, not independently established accuracy against ground truth.

## Diagnostic panels — separate descriptive results

| Panel | Comparable items | VADER disagreements | BERT disagreements |
|---|---:|---:|---:|
| Extreme star–VADER disagreements | 45 of 50 | 38/45 (84.4%) | 17/45 (37.8%) |
| Model-disagreement panel | 41 of 50 | 34/41 (82.9%) | 10/41 (24.4%) |
| Cold-category panel | 50 | 4/50 (8.0%) | 3/50 (6.0%) |
| Warm-category panel | 50 | 1/50 (2.0%) | 0/50 (0.0%) |

These cases were selected because of their model behavior or category. Their rates are not representative estimates, and none is pooled into the probability-sample rate. The model-disagreement panel was selected using forced binary predictions; the table uses the primary three-way definitions.

BERT agrees more often in these selected hard cases, but still disagrees substantially in the extremes panel. Its output is therefore not a substitute for human adjudication.

### Cold versus warm

The cold group received 49 positive and one neutral label; the warm group received 50 positive labels. Of the 50 length-matched pairs, 49 are positive/positive and one is neutral/positive. The observed positive-share contrast, cold minus warm, is −2 percentage points.

At this coarse categorical level, both groups are overwhelmingly positive. This does not establish that the groups express equally intense positivity, or disprove the earlier continuous-score contrast: the human categories have little resolution near this ceiling. This selected, five-star, matched-length comparison is exploratory and not causal.

## Exploratory checks and limits

**Notes and rubric consistency.** The 34 notes were inspected. Several reveal uncertainty or possible misapplication of the frozen rules. Specific cases are listed separately in `RUBRIC_REVIEW_20260927.md`. They have not been relabelled after seeing model results. The primary results above remain the as-collected analysis. Any later adjudication should preserve these originals, record a separate decision log, and be reported as a secondary sensitivity analysis.

**Tags.** Counts across all 450 items are: mixed_content 69; no_sentiment_words 23; not_english 21; very_long 11; off_topic 5; slang_or_emoji 5; quotes_complaint 4; sarcasm 2; cannot_assess_language 2. Tags overlap and were optional. Blanks are not independently verified absence. The no-sentiment-words and off-topic definitions were not applied consistently in every noted case, so their raw subgroup counts should not be presented as established explanations of model failures. Two sarcasm cases and five slang/emoji cases are also too few for broad claims.

For illustration only, among the 17 comparable random-sample reviews tagged mixed_content, each model disagrees on five. Thus the strong BERT advantage among selected diagnostic mixed-content cases should not be generalized to all mixed-content reviews from those selected cases alone. Detailed raw tag counts are retained in the exploratory JSON.

**Input truncation.** Four random-sample items exceed the 256-token model window. Three have comparable human labels and both models agree with all three; the fourth is excluded by its human label. Excluding the four leaves 240 comparable items, with VADER 33 disagreements and BERT 17. The extremes panel contains 28 truncated items, so interpretation of that panel must acknowledge that humans saw the whole review while BERT saw only its initial window. These counts do not identify a causal truncation effect.

**AI discussion during annotation.** Some main-sheet snippets were discussed with the assistant while annotation was underway, mostly as rubric guidance. Four identifiable snippets were found in the completed sheet, one in the random sample. Excluding that one leaves 242 comparable random-sample items: VADER disagrees on 33 (13.6%) and BERT on 16 (6.6%). The observed ranking is unchanged. This is a post-hoc sensitivity check and not a complete audit of all possible assistance. Describe the collection as single-human annotation with some AI rubric assistance, not a strictly unassisted independent human study.

**No second annotator.** Reliability between people cannot be estimated from this run. The Wilson intervals measure sampling uncertainty under the sampling design; they do not incorporate annotator uncertainty, rubric ambiguity, coverage exclusions, or past AI assistance.

## What this adds to the project

The project now has a completed human reference rather than relying solely on star ratings or model-to-model agreement. Under the frozen three-way rule, BERT aligns more closely than VADER with this annotator in the probability sample. The hard-case panels show that BERT still has limitations. The matched category panel shows nearly universal positive labels and cannot settle subtler differences in positivity intensity.

There is no need for the user to fill the second sheet themselves. The primary analysis is complete as a single-annotator analysis; the separately documented rubric flags and exploratory limitations should accompany any write-up.
