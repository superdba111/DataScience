-- Market Pulse state schema (SQLite).
-- Layers:
--   raw      : the original fixture files on disk (immutable; referenced by path + sha256 + row)
--   history  : price_revision   -- append-only, one row per valid (key, revision)
--   curated  : latest_price     -- view: highest valid revision per business key
--   audit    : ingest_run, ingested_file, ingest_row_log, rejected_record (view)

CREATE TABLE IF NOT EXISTS hub (
    hub_id      TEXT PRIMARY KEY,
    description TEXT
);

CREATE TABLE IF NOT EXISTS ingest_run (
    run_id          TEXT PRIMARY KEY,
    batch_directory TEXT NOT NULL,
    delivered_at    TEXT,              -- provider delivery time from the manifest
    started_at      TEXT NOT NULL,     -- pipeline clock
    finished_at     TEXT,
    status          TEXT NOT NULL,     -- running | succeeded | failed
    error           TEXT
);

CREATE TABLE IF NOT EXISTS ingested_file (
    run_id        TEXT NOT NULL REFERENCES ingest_run(run_id),
    source_file   TEXT NOT NULL,       -- e.g. batch_01/real_time.csv (relative to data dir)
    file_sha256   TEXT NOT NULL,
    rows_read     INTEGER NOT NULL,
    PRIMARY KEY (run_id, source_file)
);

-- Append-only history of every distinct valid revision ever accepted.
-- The primary key makes replays idempotent: same key + revision cannot be stored twice.
CREATE TABLE IF NOT EXISTS price_revision (
    market              TEXT    NOT NULL CHECK (market IN ('DA', 'RT')),
    hub_id              TEXT    NOT NULL REFERENCES hub(hub_id),
    interval_start_utc  TEXT    NOT NULL,   -- canonical 'YYYY-MM-DDTHH:MM:SSZ'
    source_revision     INTEGER NOT NULL CHECK (source_revision >= 1),
    interval_end_utc    TEXT    NOT NULL,
    price_usd_per_mwh   REAL    NOT NULL,
    published_at_utc    TEXT    NOT NULL,
    -- lineage back to the raw layer
    source_file         TEXT    NOT NULL,
    source_row          INTEGER NOT NULL,   -- physical line number in the CSV (header = 1)
    file_sha256         TEXT    NOT NULL,
    first_run_id        TEXT    NOT NULL REFERENCES ingest_run(run_id),
    PRIMARY KEY (market, hub_id, interval_start_utc, source_revision)
);

-- One line per input row per run: what happened to it and why.
CREATE TABLE IF NOT EXISTS ingest_row_log (
    run_id        TEXT    NOT NULL REFERENCES ingest_run(run_id),
    source_file   TEXT    NOT NULL,
    source_row    INTEGER NOT NULL,
    file_sha256   TEXT    NOT NULL,
    outcome       TEXT    NOT NULL,  -- accepted | duplicate | stale_revision | rejected
    reason        TEXT,              -- rejection / classification code
    detail        TEXT,
    raw_record    TEXT    NOT NULL,  -- JSON of the original CSV row
    PRIMARY KEY (run_id, source_file, source_row)
);

-- Curated layer: latest valid price per business key. A view, so it can
-- never drift from the history and a replay cannot "undo" a correction.
CREATE VIEW IF NOT EXISTS latest_price AS
SELECT market, hub_id, interval_start_utc, interval_end_utc, price_usd_per_mwh,
       source_revision, published_at_utc, source_file, source_row, file_sha256, first_run_id
FROM (
    SELECT pr.*,
           ROW_NUMBER() OVER (
               PARTITION BY market, hub_id, interval_start_utc
               ORDER BY source_revision DESC
           ) AS rn
    FROM price_revision AS pr
)
WHERE rn = 1;

-- Every distinct rejected source row (first time it was seen).
CREATE VIEW IF NOT EXISTS rejected_record AS
SELECT source_file, source_row, file_sha256, reason, detail, raw_record,
       MIN(run_id) AS first_run_id
FROM ingest_row_log
WHERE outcome = 'rejected'
GROUP BY file_sha256, source_file, source_row;
