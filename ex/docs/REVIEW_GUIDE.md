# Review guide: how to verify this submission

This guide is for a reviewer (person or AI) checking the solution against `ASSIGNMENT.md` (the assignment) and `DATA_CONTRACT.md`. Run all commands from the project root `ex/`. The only requirement is Python 3.11 or newer.

## 1. Run everything

```bash
scripts/run_demo.sh                                   # empty state -> batch_01 -> batch_02 -> batch_02 replay
python3 -m unittest discover -s tests -t . -v         # expect: Ran 17 tests ... OK
```

The demo must print `replay left hourly results and latest-price dataset unchanged`. It runs `diff -q` on the hourly CSV and the latest-price CSV produced after the replay, and exits non-zero if they differ.

## 2. Check against the contract's public examples

| Contract check | Where to look | Expected |
| --- | --- | --- |
| Latest rows after batch_01 | `output/run_summary_batch_01.json` → `state.latest_price_rows_by_market` | DA 11, RT 46 (57) |
| Latest rows after batch_02 and after replay | `run_summary_batch_02*.json` | DA 11, RT 48 (59) both times |
| Hourly rows | `output/hourly_after_batch_0*.csv` | 12 data rows each |
| Batch 1: 3 rejected, 1 duplicate | `run_summary_batch_01.json` | `rejected: 3` (missing_price, unknown_hub, unparseable_interval_end), `duplicate: 1` |
| NORTH 2026-08-18T00:00 | hourly CSVs | 40 / 41 / 1 / 4 after batch 1, then 40 / 46 / 6 / 4 after batch 2 |
| NORTH 2026-08-18T01:00 | hourly CSVs | 45 / 44.666667 / *(empty)* / 3 / false after batch 1, then 45 / 45 / 0 / 4 / true after batch 2 |
| SOUTH 2026-08-18T00:00 | hourly CSVs | 35 / -2.5 / -37.5 / 4 both times |
| SOUTH 2026-08-18T02:00 | hourly CSVs | DA empty, RT 47, diff empty, 4/4, `da_available=false` both times |
| After batch 2 | `run_summary_batch_02.json` → `data_quality` | `hours_rt_complete: 12`, `hours_with_publishable_difference: 11`, `report_status: incomplete` |

## 3. Requirement-to-implementation map

| Requirement (assignment / contract) | Implementation | Evidence |
| --- | --- | --- |
| Read only the listed files for one batch | `ingest_batch()` looks up the batch in `scenario.json` and reads only `batch["files"]` | `pipeline.py` |
| Normalize timestamps to UTC with an explicit offset | `parse_aware_timestamp()`. A timestamp without an offset is rejected as `naive_*`; one outside the supported date range as `out_of_range_*` | `validation.py`, tests `test_invalid_rows_get_specific_reasons`, `test_extreme_timestamps_are_rejected_not_raised` |
| Interval start = end − duration, with alignment checked | `validate_row()` | test `test_interval_start_is_end_minus_duration_and_offsets_normalize` |
| Negative, zero and spike prices are valid | Only blank, non-numeric and NaN/inf prices are rejected | test `test_negative_zero_and_spike_prices_are_valid` |
| Highest valid revision wins, and an older revision can't undo a correction | Append-only `price_revision` + `latest_price` view (`ROW_NUMBER ... ORDER BY source_revision DESC`) | `sql/schema.sql`, test `test_correction_wins_and_older_revision_arriving_later_does_not` |
| Replay and offset-equivalent duplicates create no new rows | Primary key `(market, hub_id, interval_start_utc, source_revision)` and the `duplicate` outcome | test `test_replay_and_offset_equivalent_duplicates_are_idempotent`, demo diff |
| Invalid rows stay identifiable with their source and reason | `ingest_row_log` (file, line, sha256, reason, raw JSON) and the `rejected_record` view | test `test_rejected_row_repaired_later_stays_in_history` |
| Lineage from a curated row back to its input | `source_file`, `source_row`, `file_sha256` and `first_run_id` on each curated row | `output/latest_after_batch_02.csv` |
| File-level failures are visible, not loaded as empty | `FileLevelError` (bad header, missing file, encoding, malformed CSV quoting) triggers a rollback, marks the run `failed`, and exits with code 2 | tests `test_bad_header_fails_run_and_rolls_back`, `test_malformed_quoting_in_second_file_fails_run_and_cli` |
| Run success vs export success | Report building and exports run after the commit. Any failure there gives `export_status=failed` and exit 3, prices stay committed, and a re-run recovers | tests `test_export_failure_keeps_prices_and_rerun_recovers`, `test_report_failure_after_commit_is_structured_export_failure` |
| Every hub and hour appears, even with no data | `hourly_report.sql`: recursive hours CTE × `hub` table, then LEFT JOINs | test `test_grid_keeps_every_hub_and_hour_with_nulls_not_zeros` |
| Difference only when RT is 4/4 and DA is present | `CASE` in `hourly_report.sql` | test `test_complete_rt_without_da_has_no_difference` |
| Hour bucketed by interval start | `strftime('%Y-%m-%dT%H:00:00Z', interval_start_utc)` | test `test_rt_interval_ending_on_the_hour_belongs_to_previous_hour` |
| Run summary that separates "run completed" from "report complete" | `run_status` vs `data_quality.report_status` + `gaps` | `output/run_summary_*.json` |
| AWS brief (diagram, services, data layout, 6 pillars, failure/recovery, rejected alternative) | `docs/AWS_DESIGN.md` | |
| README items (run commands, runtime, time, assumptions, limitations, next hour, AI disclosure) | `README.md` | |

## 4. Things a reviewer may want to probe

- Ad-hoc inspection: `sqlite3 out/state.db "select * from ingest_row_log where outcome != 'accepted'"`.
- Row order independence: shuffle the data rows inside a copy of a batch file. The latest prices should not change, because the winner is the max revision and order plays no part.
- Known gaps, documented in README.md: no as-of query, only the first rejection reason per row is recorded, no local lateness metric, and `latest_price` is a view rather than a maintained table.
- Failure paths: run `python3 -m market_pulse.pipeline` with a malformed CSV (exit 2, nothing applied) or an unwritable `--report-out` (exit 3, prices committed, re-run recovers).
