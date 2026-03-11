-- =============================================================
-- Open3Words Database Schema
-- PostgreSQL 15 + PostGIS
-- =============================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram fuzzy matching

-- ── Wordlist Table ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wordlist (
    id          SERIAL PRIMARY KEY,
    word        VARCHAR(30) UNIQUE NOT NULL,
    word_index  INTEGER UNIQUE NOT NULL,
    category    VARCHAR(30),
    length      INTEGER GENERATED ALWAYS AS (char_length(word)) STORED,
    metaphone   VARCHAR(20),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wordlist_word     ON wordlist (word);
CREATE INDEX idx_wordlist_index    ON wordlist (word_index);
CREATE INDEX idx_wordlist_trgm     ON wordlist USING gin (word gin_trgm_ops);
CREATE INDEX idx_wordlist_metaphone ON wordlist (metaphone);

-- ── Grid Cells (spatial cache) ──────────────────────────────

CREATE TABLE IF NOT EXISTS grid_cells (
    id          BIGSERIAL PRIMARY KEY,
    word1       VARCHAR(30) NOT NULL,
    word2       VARCHAR(30) NOT NULL,
    word3       VARCHAR(30) NOT NULL,
    words       VARCHAR(100) GENERATED ALWAYS AS (word1 || '.' || word2 || '.' || word3) STORED,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    geom        GEOMETRY(Point, 4326),
    z_index     BIGINT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_grid_cells_words  ON grid_cells (words);
CREATE INDEX idx_grid_cells_geom   ON grid_cells USING GIST (geom);
CREATE INDEX idx_grid_cells_z      ON grid_cells (z_index);

-- Trigger to auto-compute geom from lat/lon
CREATE OR REPLACE FUNCTION update_grid_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom := ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_grid_cells_geom
    BEFORE INSERT OR UPDATE ON grid_cells
    FOR EACH ROW EXECUTE FUNCTION update_grid_geom();

-- ── Word Aliases (alternate spellings, abbreviations) ───────

CREATE TABLE IF NOT EXISTS word_aliases (
    id          SERIAL PRIMARY KEY,
    alias       VARCHAR(30) NOT NULL,
    canonical   VARCHAR(30) NOT NULL REFERENCES wordlist(word),
    type        VARCHAR(20) DEFAULT 'spelling',  -- spelling, abbreviation, phonetic
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_word_aliases_alias ON word_aliases (alias);

-- ── API Usage / Analytics ───────────────────────────────────

CREATE TABLE IF NOT EXISTS api_usage (
    id          BIGSERIAL PRIMARY KEY,
    endpoint    VARCHAR(50) NOT NULL,
    method      VARCHAR(10) NOT NULL,
    status_code INTEGER,
    latency_ms  REAL,
    client_ip   INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_usage_time     ON api_usage (created_at DESC);
CREATE INDEX idx_api_usage_endpoint ON api_usage (endpoint);

-- ── Location Proofs (blockchain mirror) ─────────────────────

CREATE TABLE IF NOT EXISTS location_proofs (
    id              BIGSERIAL PRIMARY KEY,
    proof_id        VARCHAR(66) UNIQUE NOT NULL,   -- 0x + 64 hex
    location_hash   VARCHAR(66) NOT NULL,
    prover_address  VARCHAR(42) NOT NULL,
    words           VARCHAR(100),
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    tx_hash         VARCHAR(66),
    verified        BOOLEAN DEFAULT FALSE,
    witness_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_proofs_words   ON location_proofs (words);
CREATE INDEX idx_proofs_prover  ON location_proofs (prover_address);

-- ── Favorites / Saved Locations ─────────────────────────────

CREATE TABLE IF NOT EXISTS saved_locations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     VARCHAR(64),
    words       VARCHAR(100) NOT NULL,
    label       VARCHAR(100),
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    geom        GEOMETRY(Point, 4326),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_saved_user  ON saved_locations (user_id);
CREATE INDEX idx_saved_geom  ON saved_locations USING GIST (geom);

CREATE TRIGGER trg_saved_locations_geom
    BEFORE INSERT OR UPDATE ON saved_locations
    FOR EACH ROW EXECUTE FUNCTION update_grid_geom();

-- ── Helper: nearby cells query ──────────────────────────────
-- Example usage:
--   SELECT words, lat, lon,
--          ST_Distance(geom, ST_SetSRID(ST_MakePoint(-0.1278, 51.5074), 4326)::geography) AS dist_m
--   FROM grid_cells
--   WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(-0.1278, 51.5074), 4326)::geography, 1000)
--   ORDER BY dist_m LIMIT 10;
