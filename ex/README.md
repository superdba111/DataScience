# Market Pulse: solution README

This file describes my submission. The original assignment text is in `ASSIGNMENT.md` (the packet's `README.md`, renamed so this README can be the entry point, otherwise unchanged). `DATA_CONTRACT.md` is unchanged. The AWS design brief is `docs/AWS_DESIGN.md`.

## What it does

This is a small, repeatable pipeline built with **Python 3.11 (standard library only) and SQLite**:

1. **Ingest** one delivery batch at a time, reading only the files listed in `scenario.json`. It normalizes timestamps to UTC, validates every row, and stores each valid revision in an append-only history table. Every input row gets a logged outcome: `accepted`, `duplicate`, `stale_revision` or `rejected`.
2. **Curate**: `latest_price` is a SQL view that selects the highest valid `source_revision` per `(market, hub_id, interval_start_utc)`.
3. **Report**: `sql/hourly_report.sql` builds the hub × hour grid for the report window and LEFT JOINs DA and RT onto it. It is exported to CSV.
4. **Run summary**: a JSON summary per run. It keeps **run status** (`succeeded`/`failed`) separate from **report status** (`complete`/`incomplete`, with a list of gaps).

## Run it

No dependencies to install. Requires Python ≥ 3.11, whose `datetime.fromisoformat` accepts `Z`. SQLite ≥ 3.25 is required for window functions and is bundled with Python.

```bash
# Required sequence: empty state -> batch_01 -> batch_02 -> batch_02 replay, then diff
scripts/run_demo.sh

# Tests
python3 -m unittest discover -s tests -t . -v

# Single step by hand
python3 -m market_pulse.pipeline --state out/state.db --batch batch_01 \
    --report-out output/hourly_after_batch_01.csv
```

The demo deletes `out/` (the state location) first, so it always starts empty. Exit codes:

- `0`: ingestion and exports succeeded. The report may still be incomplete; see `data_quality.report_status`.
- `2`: ingestion failed. This covers file-level problems (missing file, bad header, undecodable file, malformed CSV quoting) and any unexpected error. The transaction is rolled back, the run is marked `failed`, and a JSON failure summary goes to stderr.
- `3`: ingestion committed, but building the report or writing a report, latest-price or summary file failed. Prices stay committed, the summary (printed to stderr) says `export_status: failed`, and re-running the same batch is safe (every row becomes a `duplicate`) and rewrites the files.

### Outputs (committed in `output/`)

| File | Contents |
| --- | --- |
| `hourly_after_batch_01.csv`, `hourly_after_batch_02.csv` | Trader-facing hourly view (12 rows each) |
| `latest_after_batch_0X.csv` | Latest-price snapshot with lineage (57, then 59 rows) |
| `run_summary_batch_01.json`, `run_summary_batch_02.json`, `run_summary_batch_02_replay.json` | Structured run logs |

CSV conventions: null is an empty cell, and booleans are `true`/`false`. Prices are rounded to 6 decimal places only at output.

### Result vs the public checks

| State | Rows read | Accepted / dup / rejected | Latest rows (DA+RT) | Publishable diffs | Report |
| --- | --- | --- | --- | --- | --- |
| After batch_01 | 61 | 57 / 1 / 3 | 57 (11+46) | 9 / 12 | incomplete (2 hours RT 3/4, 1 hour DA missing) |
| After batch_02 | 6 | 4 / 2 / 0 | 59 (11+48) | 11 / 12 | incomplete (SOUTH 02:00 DA missing) |
| Replay batch_02 | 6 | 0 / 6 / 0 | 59 | 11 / 12 | unchanged (verified by `diff` in the demo) |

All four public examples match. For example, NORTH 00:00 goes from 41 → 46 (diff 6), and NORTH 01:00 goes from 3/4 with a null diff to 4/4 with diff 0.

## Design decisions

- **Business key = interval start.** `interval_start = UTC(interval_end) − duration`. This puts an RT interval ending `00:00Z` in the 23:00 hour. Timestamps are stored as canonical `YYYY-MM-DDTHH:MM:SSZ` text, so string order equals time order and `+00:00`, `Z` and `-05:00` forms all collapse to the same key.
- **History table plus a latest-price view, rather than overwriting.** `price_revision` has primary key `(market, hub, interval_start, revision)`, which makes replays no-ops. Because "latest" is computed from the history (`ROW_NUMBER() … ORDER BY source_revision DESC`), an older revision arriving later cannot win, and a replay cannot undo a correction. Delivery order and `published_at` play no part in it.
- **Validate before selecting a winner.** A blank-price rev 1 is rejected and is never a candidate. The rev 2 in batch 2 then simply becomes the latest. The rejected row stays in `ingest_row_log` / `rejected_record` with its file, line and reason.
- **Row outcomes.** `duplicate` means the same key, revision and value is already stored (this covers both within-file and cross-run duplicates). `stale_revision` means the row is valid and new to history but older than the current winner, so it is kept for lineage and does not win. `rejected` comes with a reason code. A same key and revision with a *different* value is rejected as `conflicting_revision`. That case is out of scope per the contract, but I would rather fail loudly than overwrite.
- **Replay counting.** A replay counts every row as `duplicate`. The run summary also reports `previously_ingested_in_run` per file (matched by sha256), so an operator can see that a whole file was re-sent.
- **Lineage.** Every curated row carries `source_file`, `source_row` (the physical CSV line, header = 1), `file_sha256` and `first_run_id`. The raw layer is the original fixture files.
- **Atomicity.** Ingestion is one SQLite transaction, so any failure leaves state unchanged and marks the run `failed`. Exports happen after the commit and are reported separately (`export_status`). An export failure does not undo accepted prices.
- **Strict CSV parsing.** Malformed quoting (e.g. an unterminated quote) fails the file and rolls back the whole batch. It is never guessed into a valid row.
- **Completeness ≠ success.** The hourly SQL starts from a generated `hub × hour` grid, so missing data appears as `NULL` / `0` and never as a missing row or a zero price. The run summary's `data_quality.report_status` and `gaps` say what is missing.
- **No infinite results.** The contract says large prices are valid and must not be capped, so the RT mean is computed as `AVG(price / 4) * 4`. A plain `AVG` sums first and turns four prices near the float maximum into `inf`. If RT mean minus DA is still outside the float range (e.g. `1e308 − (−1e308)`), the difference is left null and `data_quality.gaps` reports `rt_minus_da not representable` for that hour. It is never published as `inf`.
- **Market from file.** A DA row inside `real_time.csv` is rejected (`market_file_mismatch`). This catches vendor mix-ups instead of trusting the column.

## Assumptions

- The report window and the expected 4 RT intervals per hour come from `scenario.json` (`60 / RT interval minutes`).
- Fully blank CSV lines are ignored. A row with the wrong number of fields is rejected, not treated as a file failure.
- Prices outside the report window are still ingested. The window applies only to the report.
- Hubs are reference data reloaded from `hubs.csv` on every run.

## Known limitations

- `latest_price` is a view, which is fine for this fixture. At production scale it would be a maintained table (see `docs/AWS_DESIGN.md`).
- No as-of ("what did we know at 09:00") query, although the history table and `first_run_id` make it possible.
- No concurrency control beyond SQLite's single writer. Simultaneous writers are out of scope.
- No freshness/lateness metric is computed locally. `delivered_at` is recorded per run, and the AWS design describes vendor lag vs pipeline lag.
- Rejection reasons report the *first* failing check only.
- `source_revision` is limited to SQLite's signed 64-bit range. Larger values are rejected as `invalid_revision`, because the contract gives no upper bound.
- Export files are overwritten in place, not via temp file plus rename, so a crash mid-write can leave a truncated CSV. Re-running the batch rewrites it.
- If the process is killed (not just failing with an exception), the run row stays `running`. The AWS design handles this with a separately committed file receipt and a stuck-receipt alarm.

## If I had another hour

1. Add a `--fail-on-incomplete` flag or a separate exit code, so a scheduler can alert on an incomplete report without treating it as a crashed run.
2. Add a small `explain` command that, given a hub and hour, prints every revision and rejected row behind the number. This is the "can I trust it?" answer for a trader.
3. Add a lateness metric per interval (`delivered_at − interval_end`) to the run summary.
4. Add a property-style test that shuffles row order within a file and checks that the result is the same. I checked this by hand during review, but there is no automated test for it.

## Time spent and assistance

- Approximate time: **about 2 hours**.
- AI assistance: I used Claude (Claude Code) to help draft code, tests and documentation, and a second AI tool (Codex) to review the result independently. Its findings led to the strict-CSV, revision-range, export-status and numeric-overflow fixes and to corrections in the AWS brief. I checked the result by reviewing the code, running the test suite, running the demo sequence, diffing the replay outputs, and comparing every public row-count and result example in `DATA_CONTRACT.md` by hand against `output/`.

## Layout

```
market_pulse/validation.py   pure row parsing/validation (reason codes)
market_pulse/pipeline.py     ingest, report, run summary, CLI
sql/schema.sql               tables + latest_price / rejected_record views
sql/hourly_report.sql        trader-facing hourly query (parameterized window)
tests/test_pipeline.py       17 focused tests (aggregation, numeric overflow, revisions/replay, invalid/missing, file/export failures, fixtures)
scripts/run_demo.sh          required 3-step sequence + replay diff
docs/AWS_DESIGN.md           AWS diagram, pillars table, failure/recovery, rejected alternative
docs/REVIEW_GUIDE.md         how to verify this submission step by step
ASSIGNMENT.md                original assignment (packet README)
output/                      sample outputs after batch_01 / batch_02 / replay
```
