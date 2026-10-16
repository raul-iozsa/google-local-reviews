-- Phase 3: state rankings, raw and standardized for business category.
-- phase3_reviews = stratified clean sample (~200k per state) joined to category.
-- scripts/run_phase3.py runs these same queries; this file is the readable copy.


-- Q1: raw state ranking
SELECT
    state,
    count(*) AS n,
    round(avg(rating)::numeric, 3) AS mean_rating,
    round((stddev_samp(rating) / sqrt(count(*)))::numeric, 4) AS se,
    round(100.0 * count(*) FILTER (WHERE rating = 1) / count(*), 2) AS pct_1star,
    round(100.0 * count(*) FILTER (WHERE rating = 5) / count(*), 2) AS pct_5star,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY text_len) AS median_len
FROM phase3_reviews
GROUP BY state
ORDER BY mean_rating DESC;


-- Q2: category-standardized ranking (direct standardization). Each state's
-- per-category means are recombined with one shared set of weights: the pooled
-- mix of the 66 categories with 100+ reviews in all 51 states.
WITH cells AS (
    SELECT state, category,
           count(*)                                                   AS n,
           avg(rating)::numeric                                       AS mean_r,
           var_samp(rating)::numeric                                  AS var_r,
           (count(*) FILTER (WHERE rating = 1))::numeric / count(*)    AS p1,
           (count(*) FILTER (WHERE rating = 5))::numeric / count(*)    AS p5
    FROM phase3_reviews
    GROUP BY state, category
),
common AS (
    SELECT category
    FROM cells
    WHERE n >= 100
    GROUP BY category
    HAVING count(DISTINCT state) = 51
),
wt AS (
    SELECT c.category, sum(c.n)::numeric AS w
    FROM cells c JOIN common k USING (category)
    GROUP BY c.category
),
tot AS (SELECT sum(w) AS tw FROM wt)
SELECT
    c.state,
    round(sum(w.w * c.mean_r) / (SELECT tw FROM tot), 3)                        AS std_mean_rating,
    round(sqrt(sum(power(w.w / (SELECT tw FROM tot), 2) * c.var_r / c.n)), 4)   AS std_se,
    round(100 * sum(w.w * c.p1) / (SELECT tw FROM tot), 2)                      AS std_pct_1star,
    round(100 * sum(w.w * c.p5) / (SELECT tw FROM tot), 2)                      AS std_pct_5star
FROM cells c
JOIN wt w USING (category)
GROUP BY c.state
ORDER BY std_mean_rating DESC;


-- Q3: rank change between raw and standardized
WITH cells AS (
    SELECT state, category, count(*) AS n, avg(rating)::numeric AS mean_r
    FROM phase3_reviews GROUP BY state, category
),
common AS (
    SELECT category FROM cells WHERE n >= 100
    GROUP BY category HAVING count(DISTINCT state) = 51
),
wt AS (
    SELECT c.category, sum(c.n)::numeric AS w
    FROM cells c JOIN common k USING (category) GROUP BY c.category
),
tot AS (SELECT sum(w) AS tw FROM wt),
raw AS (
    SELECT state, avg(rating)::numeric AS m FROM phase3_reviews GROUP BY state
),
std AS (
    SELECT c.state, sum(w.w * c.mean_r) / (SELECT tw FROM tot) AS m
    FROM cells c JOIN wt w USING (category) GROUP BY c.state
)
SELECT
    raw.state,
    round(raw.m, 3)                                        AS raw_mean,
    rank() OVER (ORDER BY raw.m DESC)                      AS raw_rank,
    round(std.m, 3)                                        AS std_mean,
    rank() OVER (ORDER BY std.m DESC)                      AS std_rank,
    (rank() OVER (ORDER BY raw.m DESC))
      - (rank() OVER (ORDER BY std.m DESC))                AS rank_change
FROM raw JOIN std USING (state)
ORDER BY abs((rank() OVER (ORDER BY raw.m DESC))
           - (rank() OVER (ORDER BY std.m DESC))) DESC;


-- Q4: restaurants only, as a simple check
SELECT
    state,
    count(*) AS n,
    round(avg(rating)::numeric, 3) AS restaurant_mean_rating,
    round((stddev_samp(rating) / sqrt(count(*)))::numeric, 4) AS se
FROM phase3_reviews
WHERE category = 'Restaurant'
GROUP BY state
ORDER BY restaurant_mean_rating DESC;


-- Q5: reviews per capita (businesses located in the state, not reviews by residents)
SELECT
    t.state,
    t.total_reviews,
    p.population,
    round(t.total_reviews::numeric / p.population, 2) AS reviews_per_capita
FROM state_review_totals t
JOIN state_population p USING (state)
ORDER BY reviews_per_capita DESC;
