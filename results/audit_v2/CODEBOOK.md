# Blinded review-text annotation

Rubric version 2.1 — 21 September 2026. The run's freeze record is
`_codebook_freeze.json`. Once frozen, do not edit this codebook.

Use only this codebook and your assigned CSV. Do not open files beginning
`_hidden`, including the manifest, pilot metadata and predictions, until both
annotators have finished. Do not look up businesses or ratings. If an item
is familiar, note that fact without looking up its scores.

Answer: **What sentiment does this text express about the business?**
Fill `sentiment` for every item. Other columns are optional. Preserve
`item_id` and `review_text`; sorting rows is allowed. Save as UTF-8 CSV.

| Sentiment | Definition |
|---|---|
| `positive` | Favourable overall: praise, satisfaction or recommendation. |
| `negative` | Unfavourable overall: complaint, disappointment or warning. |
| `neutral` | No clear positive or negative evaluation. For this rubric, "fine, nothing special" is neutral. |
| `mixed` | Both praise and complaint, with neither clearly dominant. If one dominates, use that sentiment. |
| `cannot_tell` | Insufficient meaning, a language you cannot assess, or text that does not evaluate the business. |

Judge the reviewer's final, currently endorsed assessment of the business.
Explicit retractions and changes of ownership matter: earlier praise that is
withdrawn does not balance a final negative verdict, and criticism of former
owners does not automatically make praise of the current business mixed.
Use `mixed` only when currently endorsed praise and criticism are genuinely
balanced. Do not infer facts beyond the text or use mixed for uncertainty.

Service and delivery complaints count when the text attributes that experience
to the business. Tag `off_topic` only when a substantial passage is unrelated
to explaining or evaluating the business experience. Background, consequences,
memories and comparisons are not automatically off-topic. A partly unrelated
review can still have a clear sentiment about the business. Use `cannot_tell`
when no assessable business evaluation remains; a purely factual business
description is `neutral`, not cannot-tell.

For a translated review containing both an original and a translation, judge
the readable text and tag `not_english` when a substantial non-English original
is present. This tag describes the input, not proof that the original has been
understood or the translation verified. If readable versions materially
conflict and you cannot resolve the intended evaluation, use `cannot_tell`
and explain briefly in notes.

Optional `tags` are separated by semicolons:

| Tag | Definition |
|---|---|
| `sarcasm` | Intended evaluation reverses the literal wording. |
| `slang_or_emoji` | Slang or emoji materially carries the evaluation. |
| `mixed_content` | Contains both praise and criticism, including historical or later retracted statements. The overall sentiment follows the final, currently endorsed assessment. |
| `off_topic` | A substantial passage is unrelated to explaining or evaluating the business experience; ordinary background, consequences and comparisons do not suffice. |
| `not_english` | Wholly or largely not English, or contains a substantial non-English original alongside a translation; includes languages you understand. |
| `cannot_assess_language` | You cannot assess the language; also choose `cannot_tell`. |
| `no_sentiment_words` | No explicit evaluative words; evaluation may be implicit or absent. Use the sentiment column to distinguish those cases. |
| `quotes_complaint` | Reports a complaint without necessarily endorsing it. |
| `very_long` | Your interpretation depends on information late in a long review. This is not the objective model-truncation flag. |

`implied_stars_optional`: leave blank in the main and second-annotator sheets
for this run. The two existing pilot entries are retained as exploratory notes
and are not used to estimate rating accuracy.
`notes`: record ambiguity, familiarity, or other useful context. If a review
is ambiguous during the main round, apply the frozen rules yourself and note
the difficulty. Do not ask an AI or the other annotator to decide individual
main-sheet labels. Technical help with files is fine.

Calibration examples (invented, not audit items):

- "Open until nine." → `neutral`: factual, with no evaluation.
- "Good for a quick stop." → `positive`: short but evaluative.
- "Excellent food, terrible service; equally pleased and disappointed." →
  `mixed` with `mixed_content`.
- An unintelligible passage or a language you cannot assess → `cannot_tell`;
  add `cannot_assess_language` when language is the reason.

A single word such as "good" is evaluative. Do not tag `no_sentiment_words`
merely because a review is short. Mixed and cannot-tell labels remain in the
human-label distribution; use them when appropriate even though they are
excluded from the three-way model-error denominator.

1. The 25-item pilot has been completed and reconciled with this rubric.
   Pilot labels are excluded from the main results.
2. The freeze record is created before any main or second-annotator labels.
   Do not rerun the freeze command or change the rubric for this run.
3. Label the 450-item main sheet in manageable sessions. Keep the rubric
   unchanged once frozen.
4. Give another person the 50-item second-annotator sheet and the frozen
   codebook only. They must not see your labels or hidden files. Primary
   results use your original labels; agreement uses both independent sets.
5. After both sets are complete, run the analysis command in `START_HERE.md`.
   If no second annotator is available, use the documented explicit option;
   the output will say agreement was not measured.

The random sample covers reviews with at least 20 characters in the clean
global sample, after known-exposure exclusions. It does not cover all review
text. Only that random sample supports prevalence estimates for this frame.
Its maximum approximate 95% sampling margin is 6.2 percentage points at
n=250; smaller usable subgroups have wider uncertainty. Human judgments
also have error that this sampling margin does not measure.

Other panels deliberately select difficult cases. Cold/warm items are paired
at five stars and within 10 displayed characters of each other. That controls
length approximately, not every difference between businesses. The contrast
is exploratory and observational. Text can reveal business type even with
metadata hidden. Model disagreement with a person does not establish ground
truth or prove a reviewer selected the wrong star rating.
