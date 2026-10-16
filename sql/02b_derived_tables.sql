-- Derived tables used by Phases 3, 4 and 6.


-- One row per business. 26,573 gmap_ids appear twice as identical rows, so
-- DISTINCT ON loses nothing, and the primary key keeps duplicates out.
DROP TABLE IF EXISTS businesses_clean CASCADE;

CREATE TABLE businesses_clean AS
SELECT DISTINCT ON (gmap_id)
       gmap_id, name, state, category, price, latitude, longitude,
       avg_rating, num_of_reviews, business_status
FROM businesses
ORDER BY gmap_id;

ALTER TABLE businesses_clean ADD PRIMARY KEY (gmap_id);


-- The stratified clean sample joined to each business's category.
DROP TABLE IF EXISTS phase3_reviews;

CREATE TABLE phase3_reviews AS
SELECT r.state,
       b.category,
       r.rating,
       length(r.text) AS text_len
FROM reviews_stratified_clean r
JOIN businesses_clean b ON b.gmap_id = r.gmap_id
WHERE r.state <> 'other'
  AND b.category IS NOT NULL
  AND b.category <> '';

CREATE INDEX idx_p3_state_cat ON phase3_reviews (state, category);
