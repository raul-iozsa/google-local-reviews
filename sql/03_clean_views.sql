-- Clean views without the third-party reviews that have no user and no rating.
-- Views rather than deletes, so the raw tables stay complete.

CREATE OR REPLACE VIEW reviews_global_clean AS
SELECT * FROM reviews_global WHERE user_id IS NOT NULL;

CREATE OR REPLACE VIEW reviews_stratified_clean AS
SELECT * FROM reviews_stratified WHERE user_id IS NOT NULL;
