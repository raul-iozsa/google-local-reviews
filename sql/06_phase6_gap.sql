-- Phase 6: where review text and star rating disagree.
--
-- ============================================================================
-- PRE-REGISTERED PREDICTIONS -- written before any query below was run.
-- Scored in results/06_phase6_gap_report.txt. Not to be edited after the fact.
-- ============================================================================
-- P1. The categories whose text is most COLDER than their stars will be ones
--     whose subject matter is illness, death or damage: funeral homes,
--     hospitals / emergency rooms, oncology, veterinarians, collision repair,
--     pest control, criminal / bail services.
-- P2. That cold gap is a LEXICON ARTIFACT, not reviewer sentiment. A 5-star
--     funeral-home review ("they helped us through my father's death") is
--     full of words VADER scores negative. Test: pre-trained BERT, which
--     reads context, will call 5-star reviews from those categories positive
--     at close to the rate it does for 5-star reviews elsewhere.
-- P3. The categories whose text is most WARMER than their stars will be food
--     and hospitality, where people describe pleasant things (the view, the
--     food) even when the rating is middling.
-- P4. Longer reviews push VADER's compound toward +/-1 (it sums valence), so
--     part of every category's gap is its review-length mix. Controlling for
--     length will SHRINK the category gaps but NOT substantially reorder
--     them (Spearman rho between controlled and uncontrolled > 0.8).
-- P5. The STATE gap, after Phase 3's category standardization, will be as
--     unstable as state "generosity" was in Phase 3: split-half reliability
--     below 0.6.
-- ============================================================================
--
-- gap = VADER compound minus the mean compound for the same star rating.
-- gap_lenctl does the same within star rating x length bucket.
-- Uses the global clean sample.


-- One row per scored review, with both gap definitions.
DROP TABLE IF EXISTS phase6_gap_global;

CREATE TABLE phase6_gap_global AS
WITH base AS (
    SELECT r.review_id, r.rating, r.state, b.category,
           length(r.text)                          AS text_len,
           CASE WHEN length(r.text) <  50 THEN 1
                WHEN length(r.text) < 150 THEN 2
                WHEN length(r.text) < 400 THEN 3
                ELSE 4 END                         AS len_bucket,
           s.vader_compound::float8                AS compound
    FROM sentiment s
    JOIN reviews_global_clean r USING (review_id)
    LEFT JOIN businesses_clean b ON b.gmap_id = r.gmap_id
),
exp_r  AS (SELECT rating, avg(compound) AS e FROM base GROUP BY rating),
exp_rl AS (SELECT rating, len_bucket, avg(compound) AS e FROM base GROUP BY rating, len_bucket)
SELECT base.*,
       base.compound - exp_r.e  AS gap,
       base.compound - exp_rl.e AS gap_lenctl
FROM base
JOIN exp_r  USING (rating)
JOIN exp_rl USING (rating, len_bucket);

CREATE INDEX idx_p6g_cat ON phase6_gap_global (category);

-- The same gap within 20 length quantiles per star rating (read by run_phase6_bert_check.py).
DROP TABLE IF EXISTS phase6_gap_fine;

CREATE TABLE phase6_gap_fine AS
WITH q AS (
    SELECT review_id, rating, category, compound,
           ntile(20) OVER (PARTITION BY rating ORDER BY text_len) AS lq
    FROM phase6_gap_global
),
e AS (SELECT rating, lq, avg(compound) AS e FROM q GROUP BY rating, lq)
SELECT q.review_id, q.category, q.compound - e.e AS gap_fine
FROM q JOIN e USING (rating, lq);

CREATE INDEX idx_p6f_cat ON phase6_gap_fine (category);


-- Q1: category gap (categories with 1,000+ scored reviews)
SELECT category,
       count(*)                                          AS n,
       round(avg(rating)::numeric, 3)                    AS mean_star,
       round(avg(gap)::numeric, 4)                       AS mean_gap,
       round((stddev_samp(gap)/sqrt(count(*)))::numeric, 4) AS se,
       round(avg(gap_lenctl)::numeric, 4)                AS mean_gap_lenctl
FROM phase6_gap_global
WHERE category IS NOT NULL AND category <> ''
GROUP BY category
HAVING count(*) >= 1000
ORDER BY mean_gap;


-- Q2: VADER score and gap by review length
SELECT len_bucket,
       count(*)                                  AS n,
       round(avg(abs(compound))::numeric, 4)     AS mean_abs_compound,
       round(avg(gap)::numeric, 4)               AS mean_gap
FROM phase6_gap_global
GROUP BY len_bucket ORDER BY len_bucket;
