-- Raw tables for the two review samples and the business metadata.
-- scripts/run_load_and_verify.py runs these same statements; this file is the readable copy.

-- CASCADE: the clean views depend on these tables.
DROP TABLE IF EXISTS reviews_stratified CASCADE;
DROP TABLE IF EXISTS reviews_global CASCADE;
DROP TABLE IF EXISTS businesses CASCADE;

CREATE TABLE reviews_stratified (
    review_id   BIGSERIAL PRIMARY KEY,   -- generated here; not in the CSV
    user_id     TEXT,
    gmap_id     TEXT,
    state       TEXT,
    rating      SMALLINT,
    review_time TIMESTAMP,               -- already converted from epoch ms by load_reviews.py
    text        TEXT,
    resp_time   TIMESTAMP,               -- owner's reply time; NULL when there was no reply
    resp_text   TEXT
);

CREATE TABLE reviews_global (
    review_id   BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    gmap_id     TEXT,
    state       TEXT,
    rating      SMALLINT,
    review_time TIMESTAMP,
    text        TEXT,
    resp_time   TIMESTAMP,
    resp_text   TEXT
);

-- No primary key on gmap_id: duplicate businesses are removed later (02b).
CREATE TABLE businesses (
    gmap_id         TEXT,
    name            TEXT,
    state           TEXT,   -- real US state, taken from the filename
    category        TEXT,   -- first/primary category only; source has a list
    price           TEXT,   -- '$', '$$' etc., or NULL
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    avg_rating      NUMERIC,
    num_of_reviews  INTEGER,
    -- The source calls this field "state", but it is an open/closed status.
    business_status TEXT
);
