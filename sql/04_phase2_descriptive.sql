-- Phase 2: descriptive queries. The global sample for national figures,
-- the stratified sample for by-state figures.
-- scripts/run_phase2.py runs these same queries; this file is the readable copy.


-- Q1a: rating distribution, national
SELECT
    rating,
    count(*) AS n,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM reviews_global_clean
GROUP BY rating
ORDER BY rating;


-- Q1b: rating distribution by state
SELECT
    state,
    count(*) AS n,
    round(avg(rating)::numeric, 3) AS mean_rating,
    round(100.0 * count(*) FILTER (WHERE rating = 1) / count(*), 2) AS pct_1star,
    round(100.0 * count(*) FILTER (WHERE rating = 5) / count(*), 2) AS pct_5star
FROM reviews_stratified_clean
GROUP BY state
ORDER BY mean_rating DESC;


-- Q2: reviews per year
SELECT
    date_trunc('year', review_time)::date AS year,
    count(*) AS n
FROM reviews_global_clean
GROUP BY 1
ORDER BY 1;


-- Q3: mean rating by year, with the year-over-year change
SELECT
    year,
    mean_rating,
    round(mean_rating - LAG(mean_rating) OVER (ORDER BY year), 4) AS change_from_prior_year
FROM (
    SELECT
        date_trunc('year', review_time)::date AS year,
        avg(rating)::numeric AS mean_rating
    FROM reviews_global_clean
    GROUP BY 1
) yearly
ORDER BY year;


-- Q4: review length by rating (median as well as mean, since length is skewed)
SELECT
    rating,
    count(*) FILTER (WHERE text IS NOT NULL) AS n_with_text,
    round(avg(length(text))::numeric, 1) AS mean_length,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY length(text)) AS median_length
FROM reviews_global_clean
GROUP BY rating
ORDER BY rating;


-- Q5: mean rating by category (500+ reviews)
SELECT
    b.category,
    count(*) AS n,
    round(avg(r.rating)::numeric, 3) AS mean_rating
FROM reviews_global_clean r
JOIN businesses_clean b ON r.gmap_id = b.gmap_id
WHERE b.category IS NOT NULL AND b.category <> ''
GROUP BY b.category
HAVING count(*) >= 500
ORDER BY mean_rating DESC;


-- Q6: owner response rate by rating
SELECT
    rating,
    count(*) AS n,
    count(*) FILTER (WHERE resp_text IS NOT NULL) AS n_with_response,
    round(100.0 * count(*) FILTER (WHERE resp_text IS NOT NULL) / count(*), 2) AS pct_with_response
FROM reviews_global_clean
GROUP BY rating
ORDER BY rating;
