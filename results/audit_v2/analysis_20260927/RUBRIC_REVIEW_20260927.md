# Rubric-consistency observations — 27 September 2026

These are a targeted review of the submitted notes and associated texts, not an independent blind annotation of all 450 reviews. Model predictions were available during the analysis, so proposed adjudications must not replace the original labels silently. No submitted cells were changed. The primary report uses the originals.

## Sentiment cases worth recording

**IT-E94E7659E0 — meal-plan business, submitted `mixed`.** The final update explicitly says the company response changed the reviewer's attitude, praises the response and announces a rating revision. The frozen rule uses the final, currently endorsed assessment. On the wording, `positive` with `mixed_content` is more consistent with that rule than the submitted rationale of choosing mixed because the earlier text was negative and the annotator was unsure. This recommendation comes from the text and rubric, not from treating the stated star number as the sentiment label.

**IT-ABB3CC126A — car detailing, submitted `mixed`.** The text describes delay, rubbish moved into the trunk and poor cleaning, with one limited concession. It also contains an internal inconsistency about the outside of the car. The note says mixed was chosen partly because the annotator could not tell. `Negative` with `mixed_content` is a plausible, arguably closer application of the dominant-assessment rule. The inconsistent wording makes this less clear-cut than the update case. Preserve the original rather than treating this reviewer's assessment as a definitive correction.

## Tag definitions need care in interpretation

| Item ID | Submitted tag / note | Observation |
|---|---|---|
| IT-21F684BF24 | `no_sentiment_words` | Calling a business "con artists" is explicit negative evaluation. The tag is not a test of whether a sentiment lexicon recognizes each word. |
| IT-388A9544BC | `no_sentiment_words`; note interprets "Dynamite" as good | That use is an evaluative colloquial expression; `slang_or_emoji` is a more natural tag. |
| IT-FEFC4C328E | `no_sentiment_words`; uncertainty about "bomb" | In the submitted positive reading, slang carries the evaluation. Again, `slang_or_emoji` is more natural than treating the expression as non-evaluative. |
| IT-4FF28AD964 | `off_topic` because no personal experience was described | The text defends the named towing company. A personal transaction is not required for sentiment about a business; that rationale does not establish off-topic content. |
| IT-3AAC14C751 | `off_topic` because not related to an experience | Hiring/firing decisions and company conduct can be about the business. Lack of a first-person shopping experience alone is insufficient for the tag. |

These observations particularly limit interpreting optional tags as explanatory variables. They do not automatically invalidate the main sentiment choices or prevent analysis. The remaining borderline notes need not be forced into certainty: real ambiguity is one reason the absence of a second annotator matters.

## Preserving the result

Keep the current completed CSV as the primary annotation record. If adjudications are later made, save a new version and record item ID, old and new values, reason, adjudicator, and the fact that this occurred after model comparison. Recalculate secondary results under a new output filename. Do not alter the frozen codebook retrospectively or present AI-reviewed labels as a second independent human set.
