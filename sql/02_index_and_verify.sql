-- Indexes, then load checks.
-- scripts/run_load_and_verify.py runs these same indexes and checks; this file is the readable copy.

-- Indexes on the columns later queries join and filter on.
CREATE INDEX idx_stratified_gmap  ON reviews_stratified (gmap_id);
CREATE INDEX idx_stratified_time  ON reviews_stratified (review_time);
CREATE INDEX idx_stratified_state ON reviews_stratified (state);

CREATE INDEX idx_global_gmap  ON reviews_global (gmap_id);
CREATE INDEX idx_global_time  ON reviews_global (review_time);
CREATE INDEX idx_global_state ON reviews_global (state);

CREATE INDEX idx_businesses_gmap ON businesses (gmap_id);


-- Check 1: row counts (expect 10,362,952 / 9,994,108 / 4,989,684).
SELECT
    (SELECT count(*) FROM reviews_stratified) AS stratified_rows,
    (SELECT count(*) FROM reviews_global)     AS global_rows,
    (SELECT count(*) FROM businesses)         AS business_rows;


-- Check 2: review_time range.
SELECT 'stratified' AS sample, min(review_time), max(review_time) FROM reviews_stratified
UNION ALL
SELECT 'global',     min(review_time), max(review_time) FROM reviews_global;


-- Check 3: rating distribution (only 1-5 expected).
SELECT rating, count(*) AS n
FROM reviews_stratified
GROUP BY rating
ORDER BY rating;


-- Check 4: duplicate reviews (same user, business and time).
SELECT user_id, gmap_id, review_time, count(*) AS n
FROM reviews_stratified
GROUP BY user_id, gmap_id, review_time
HAVING count(*) > 1
LIMIT 20;


-- Check 5: reviews whose business is missing.
SELECT count(*) AS orphan_reviews
FROM reviews_stratified r
LEFT JOIN businesses b ON r.gmap_id = b.gmap_id
WHERE b.gmap_id IS NULL;
