-- Phase 6: the text-vs-stars gap by state, controlling for star rating, review
-- length (20 quantiles) and business category. Uses the stratified sample.

DROP TABLE IF EXISTS phase6_gap_strat;

CREATE TABLE phase6_gap_strat AS
WITH base AS (
    SELECT r.review_id, r.rating, r.state, b.category,
           length(r.text)           AS text_len,
           s.vader_compound::float8 AS compound
    FROM sentiment_stratified s
    JOIN reviews_stratified_clean r USING (review_id)
    LEFT JOIN businesses_clean b ON b.gmap_id = r.gmap_id
    WHERE r.state <> 'other'
),
q AS (
    SELECT *, ntile(20) OVER (PARTITION BY rating ORDER BY text_len) AS lq
    FROM base
),
e AS (SELECT rating, lq, avg(compound) AS e FROM q GROUP BY rating, lq)
SELECT q.review_id, q.state, q.category, q.rating, q.text_len,
       q.compound,
       q.compound - e.e AS gap
FROM q JOIN e USING (rating, lq);

CREATE INDEX idx_p6s_state_cat ON phase6_gap_strat (state, category);


-- Q1: raw state gap (rating and length adjusted, not category)
SELECT state,
       count(*)                                             AS n,
       round(avg(gap)::numeric, 4)                          AS mean_gap,
       round((stddev_samp(gap)/sqrt(count(*)))::numeric, 4) AS se
FROM phase6_gap_strat
GROUP BY state
ORDER BY mean_gap DESC;


-- Q2: category-standardized state gap (same method as Phase 3)
WITH cells AS (
    SELECT state, category, count(*) AS n, avg(gap) AS mean_gap, var_samp(gap) AS var_gap
    FROM phase6_gap_strat
    WHERE category IS NOT NULL AND category <> ''
    GROUP BY state, category
),
common AS (
    SELECT category FROM cells WHERE n >= 100
    GROUP BY category HAVING count(DISTINCT state) = 51
),
wt AS (
    SELECT c.category, sum(c.n)::numeric AS w
    FROM cells c JOIN common k USING (category) GROUP BY c.category
),
tot AS (SELECT sum(w) AS tw FROM wt)
SELECT c.state,
       round((sum(w.w * c.mean_gap) / (SELECT tw FROM tot))::numeric, 4)                     AS std_gap,
       round(sqrt(sum(power(w.w/(SELECT tw FROM tot), 2) * c.var_gap / c.n))::numeric, 4)    AS std_se
FROM cells c JOIN wt w USING (category)
GROUP BY c.state
ORDER BY std_gap DESC;
