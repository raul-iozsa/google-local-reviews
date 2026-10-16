# What 666 million Google reviews say - and where they mislead you

**A state's average rating says as much about what businesses it has as about how
its reviewers rate, and a widely used sentiment tool misses about half the
complaints a person picks out. An analysis of samples from 666 million Google Maps
reviews of US businesses, up to September 2021.**

**The question:** what do Google review ratings and texts tell you about places and
businesses, and where do they mislead?

**What I did:** took the UCSD Google Local dataset (666,324,103 reviews of 4,963,111
US businesses), drew three samples of 10–12 million reviews each, loaded them into
PostgreSQL, and answered four questions with SQL and Python. I then labelled 450
reviews by hand to check the sentiment models against a person's reading.

**Tools:** PostgreSQL · Python (psycopg2, scikit-learn, PyTorch / Transformers,
VADER) · matplotlib

**Contents:** [In short](#in-short) · [Findings](#findings) ·
[What I got wrong](#what-i-got-wrong) · [Data and method](#data-and-method) ·
[Caveats](#caveats) · [Repository](#repository)

## In short

- **Business mix explains a large part of the differences between states.** Hawaii
  and Vermont have the highest average ratings and Mississippi the lowest, but
  states differ in what there is to review. Scored on one shared mix of business
  types, the gap between states shrinks by 42% (comparing the same 66 types before
  and after) and Vermont falls from <!-- metric:vermont_shift -->2nd to 41st<!-- /metric:vermont_shift -->.
- **The state ranking isn't stable.** Rank the states on one random half of
  business types, then on the other half, and the two rankings agree only weakly
  (ρ = <!-- metric:p3_split -->0.445<!-- /metric:p3_split -->).
- **Ratings dip before a business closes, but tell closed and open businesses
  apart only weakly.**
  In their last six months, closed businesses' ratings fall <!-- metric:closure_did_range -->0.09–0.11<!-- /metric:closure_did_range --> stars more than similar open businesses'. The tested
  rating signals separate the two groups barely better than chance (AUC <!-- metric:closure_auc_range -->0.53–0.58<!-- /metric:closure_auc_range -->,
  where 0.50 is a coin flip).
- **Owners reply to the extremes.** <!-- metric:response_1 -->17.79%<!-- /metric:response_1 --> of 1-star and <!-- metric:response_5 -->16.45%<!-- /metric:response_5 --> of 5-star
  reviews get a reply, against about 9% of 3- and 4-star ones. Businesses that
  start replying gain <!-- metric:response_gain -->+0.067<!-- /metric:response_gain --> stars over similar businesses that don't:
  an association, not proof that replying causes it.
- **The popular sentiment tool VADER misses complaints.** Against star ratings it
  is right on <!-- metric:vader_5star -->98%<!-- /metric:vader_5star --> of 5-star reviews but <!-- metric:vader_2star -->44%<!-- /metric:vader_2star --> of 2-star ones. In my
  hand-labelled check, it agreed on only <!-- metric:audit_vader_negatives -->19 of 38<!-- /metric:audit_vader_negatives --> reviews I judged
  negative; BERT agreed on <!-- metric:audit_bert_negatives -->32<!-- /metric:audit_bert_negatives -->.
- **Some business types read colder than their stars.** At the same star rating,
  reviews of post offices and plumbers read colder, and reviews of wineries and
  bridal shops warmer. A second model, BERT, agrees on the direction.

---

## Findings

The full version of each finding, with every supporting number, is in
[docs/FINDINGS.md](docs/FINDINGS.md). The complete output tables are the phase
reports in [`results/`](results/).

### 1. Business mix, not reviewer generosity, drives much of the state ranking

Categories are rated very differently: periodontists average about 4.95 stars,
fast food restaurants about 3.7. So a state's raw average partly measures what
it has to review. Scoring every state on one shared mix of the 66 business types
found in all 50 states and DC (direct standardization):

| | Spread between top and bottom state |
|---|---|
| Raw average, all categories | 0.1750 stars |
| Raw average, the same 66 categories | 0.1450 |
| Every state scored on the same mix | **0.0846** |

With the categories held fixed, reweighting cuts the spread by **41.7%**.
Vermont falls from <!-- metric:vermont_shift -->2nd to 41st<!-- /metric:vermont_shift -->, Colorado from 27th to last, and
California rises from 17th to 3rd.

![State rank shift](results/charts/05_state_rank_shift.png)

What's left isn't one clear ranking. Ranked on two random halves of the 66
categories, states agree only at ρ = <!-- metric:p3_split -->0.445<!-- /metric:p3_split -->, well below an approximate noise-only estimate of <!-- metric:p3_noise -->0.941<!-- /metric:p3_noise -->. States are generous about some kinds of business and harsh
about others. Extrapolated to the full set of 66 (Spearman–Brown), the ranking's
reliability is <!-- metric:p3_full -->0.616<!-- /metric:p3_full -->: broadly informative, not a league table. The same test on how warmly people *write* gives <!-- metric:p6_full -->≈0.90<!-- /metric:p6_full -->,
though the two tests use different samples. These are businesses located in each
state, not reviewers living there. Details in the
[Phase 3 report](results/03_phase3_state_comparison_report.txt).

### 2. Closing businesses: ratings decline, but tell closed and open businesses apart only weakly

I followed 27,955 permanently closed businesses in five states, and 71,804 open
ones matched on business type and size, through every one of their reviews. The
data doesn't record when a business closed, so each one is measured up to its
last review, and each business is compared with its own earlier ratings.

In their last six months, closed businesses' ratings fall <!-- metric:closure_did_range -->0.09–0.11<!-- /metric:closure_did_range --> stars
more than the open businesses' over the same period. The 2020 and 2021 estimates
are clear; 2019, the only year before COVID, rests on just 135 open businesses
and its interval includes zero, so the data can't show the pattern predates the
pandemic.

![Closure AUC](results/charts/07_closure_auc.png)

Used to tell closed businesses from open ones, the tested rating signals are
weak: AUC <!-- metric:closure_auc_range -->0.53–0.58<!-- /metric:closure_auc_range --> across the signals and years, where 0.50 is a coin flip.
The change in rating on its own gives about 0.53–0.55; the recent rating level
does slightly better. This is a retrospective check of these signals, not a
test of whether closures can be predicted at all. Details in the
[Phase 4A report](results/04a_phase4_closure_report.txt).

### 3. Owner replies: fastest to the angriest, and a small association with later ratings

![Owner response rate](results/charts/04_owner_response_rate.png)

Owners reply to <!-- metric:response_1 -->17.79%<!-- /metric:response_1 --> of 1-star and <!-- metric:response_5 -->16.45%<!-- /metric:response_5 --> of 5-star reviews, against
9.3–9.6% in the middle, and they reply fastest to angry ones: a median of 1.58
days for 1-star reviews against 2.13 for 4-star. (51,428 replies are dated before
the review they answer, possibly because reviews were edited later; they're left
out of the timing.)

Do replies help? A simple before/after comparison is misleading, because ratings
drift back towards normal on their own after an unusually bad or good year. So
businesses that started replying are compared with never-repliers that started
at the same rating in the same year. Repliers end up <!-- metric:response_gain -->+0.067<!-- /metric:response_gain --> stars ahead, and
ahead in 53 of the 60 comparison groups. That is an association: owners who reply
may also differ in ways the data can't see. Details in the
[Phase 4B report](results/04b_phase4_responses_report.txt).

### 4. Measuring sentiment: VADER is lopsided, and business types differ

Four ways of reading a review's sentiment, tested against star ratings on 40,000
reviews, half from 1–2 star reviews and half from 4–5 star ones:

| Method | How it works | Accuracy |
|---|---|---|
| Linear SVM | trained on 400,000 separate reviews | 93.3% |
| BERT | a pretrained language model, not retrained here | 92.0% |
| Naive Bayes | trained on the same 400,000 | 90.9% |
| VADER | a scored word list plus rules | 75.5% |

Some evaluation texts also occur in the training reviews; excluding them keeps the
ranking the same, but a fully deduplicated benchmark would need retraining
([details](docs/FINDINGS.md#6-vader-agrees-with-star-ratings-far-more-on-praise-than-on-complaints)).

VADER's average hides two very different results: <!-- metric:vader_5star -->98%<!-- /metric:vader_5star --> on 5-star reviews, <!-- metric:vader_2star -->44%<!-- /metric:vader_2star --> on 2-star ones. A likely reason: praise usually contains an obvious positive
word, while complaints are often plain facts ("the room was hot"). It beats
every trained model on 4- and 5-star reviews.

<!-- human-audit-headline:begin -->
**A hand-labelled check shows the same weakness.** Among the randomly chosen reviews I labelled without seeing their stars or the model scores, 38 were negative: VADER agreed on 19 of them (50.0%), BERT on 32 (84.2%). Because 83.1% of the 243 comparable labels were positive, answering "positive" every time would already agree 83.1% of the time; VADER agrees on 86.4% and BERT on 93.0%. A post-hoc paired test makes BERT's lead over VADER unlikely to be chance (exact McNemar p = 0.011). One person did the labelling, with some items discussed with AI; the full results are in [docs/HUMAN_AUDIT.md](docs/HUMAN_AUDIT.md).
<!-- human-audit-headline:end -->

![Accuracy by star](results/charts/09_sentiment_accuracy_by_star.png)

The same word-list behaviour shows in a single review. A 5-star taco review
reading "so fire 🔥🔥🔥…" with 33 flame emoji scores −0.9969, close to the most
negative possible, because VADER reads 🔥 as the word "fire".

Measured against what is typical for the same star rating and review length,
some business types read colder than their stars (post offices, plumbers, smog
inspections) and some warmer (wineries, escape rooms, bridal shops). BERT shows
the same direction on matched 5-star reviews (<!-- metric:bert_cold -->−0.29<!-- /metric:bert_cold --> against VADER's <!-- metric:vader_cold -->−0.73<!-- /metric:vader_cold -->),
so it isn't only a VADER quirk, though the two numbers can't say how much of the
gap is real. Details in the [Phase 5](results/05_phase5_sentiment_comparison_report.txt)
and [Phase 6](results/06_phase6_gap_report.txt) reports and in
[docs/HUMAN_AUDIT.md](docs/HUMAN_AUDIT.md).

---

## What I got wrong

**Three predictions written down before the Phase 6 queries ran turned out
wrong:** that the coldest business types would be about illness and death (they
are everyday chores like gas stations and post offices), that food and
hospitality would read warmest (it is personal services like bridal shops), and
that the state ranking of writing warmth would be as unstable as the rating ranking
(it is much more stable).

**Fifteen mistakes were found and fixed along the way.** Three examples:

| Mistake | How it was caught |
|---|---|
| Reported "20 duplicate reviews". That was the query's `LIMIT 20`; the real count is 14,070 | Re-counted with `COUNT(*)` |
| Ranked BERT first at 94.2%, but it had been allowed to skip 9.2% of reviews while every other method answered all of them. The fair figure is 92.0% | A coverage check found 36,318 rows, not 40,000 |
| Reported closed businesses rating 0.18 stars lower. Pooling the years made it look bigger (a Simpson's paradox); within each year the gap is 0.04–0.11 | Checked the gap year by year |

## Data and method

| | |
|---|---|
| Source | [UCSD Google Local](https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/) (McAuley Lab), full state files |
| Corpus | 666,324,103 reviews · 4,963,111 businesses · up to September 2021 |
| State comparisons | 10,362,952 reviews, 200,000 per state |
| Whole-corpus figures | 9,994,108 reviews, a uniform ~1.5% sample |
| Closures and replies | 12,332,584 reviews: every review of 99,759 businesses in five states |
| Human check | 450 reviews labelled by hand (250 random, 200 selected diagnostic cases), plus a 25-review pilot |

SQL does the aggregation and standardization in PostgreSQL; Python handles
sampling, the models, the statistics and the charts. Recurring methods: scoring
every group on the same business mix (direct standardization), split-half
reliability, before/after comparisons against matched groups
(difference-in-differences), and AUC to test whether an average difference can
rank individual cases. 75,544 rows missing both user ID and rating, and
26,573 duplicate business rows, were excluded. The key numbers in this README are
filled in from the saved results and checked automatically
([docs/REPRODUCING.md](docs/REPRODUCING.md)).

## Caveats

- **The data ends in September 2021,** and 2021 is a partial year.
- **Reviewers are self-selected:** people mostly review when delighted or furious.
- **The closure and reply results are associations, not causes,** and closure
  dates are inferred from each business's last review.
- **States are where businesses are,** not where reviewers live.
- **"Business type" is the first category listed** for each business.
- **Star ratings and sentiment are different targets.** Most sentiment figures
  are VADER scores; BERT re-checks the main conclusions.
- **The human check has one annotator,** 25 of whose items were discussed with AI
  while labelling (the results hold without them), and only the 250 random
  reviews support estimates for the eligible review population (clean reviews of
  20+ characters).
- **Error margins treat reviews as independent,** although many share a business
  or a reviewer, so they may be too narrow.

## Repository

```
sql/          tables, checks, and one file per analysis
scripts/      sampling, loading, analyses, models, charts, checks
results/      one report per phase, csv/ result tables, charts/, the human audit
docs/         detailed findings, human audit, rebuild steps
tests/        tests that break copies of the outputs to confirm the checks notice
```

Check the saved results without the database or raw data:

```bash
python scripts/verify_project.py
```

Rebuilding everything from the 51 GB raw archive is described in
[docs/REPRODUCING.md](docs/REPRODUCING.md). Data provenance and the review text
included in the repository are covered in [DATA_USAGE.md](DATA_USAGE.md).

**Citation.** The UCSD McAuley Lab asks users of the data to cite:

> Jiacheng Li, Jingbo Shang, Julian McAuley. *UCTopic: Unsupervised
> Contrastive Learning for Phrase Representations and Topic Mining.* ACL 2022.

> An Yan, Zhankui He, Jiacheng Li, Tianyang Zhang, Julian McAuley.
> *Personalized Showcases: Generating Multi-Modal Explanations for
> Recommendations.* SIGIR 2023.

## A note on tooling

Built with Claude Code as a pair programmer. I set the questions and scope,
labelled the 450 audit reviews myself, and reviewed the outputs; the SQL, the
Python and the charts were written with AI assistance. Several of the mistakes
above were found in external reviews of the finished work.
