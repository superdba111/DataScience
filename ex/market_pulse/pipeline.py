"""Ingest one delivery batch into SQLite state and publish the hourly report.

Usage:
    python -m market_pulse.pipeline --state out/state.db --batch batch_01 \
        --report-out output/hourly_after_batch_01.csv

One invocation = one run. Ingestion is one SQLite transaction: either the whole
batch is applied or nothing is (a failure rolls back, marks the run failed and
exits 2). Report/export files are written after the commit; if that step fails
the prices stay committed, the summary says export_status=failed, and the
command exits 3. Re-running the batch is safe (all rows become duplicates).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .validation import EXPECTED_COLUMNS, RowRejected, validate_row

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

FILE_MARKET = {"day_ahead.csv": "DA", "real_time.csv": "RT"}

# Columns of the hourly view that are booleans (SQLite returns 0/1).
BOOL_COLUMNS = {"rt_complete", "da_available"}


class FileLevelError(RuntimeError):
    """A whole file could not be read/parsed. Must fail the run, not load empty."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def connect(state_path: Path) -> sqlite3.Connection:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_path, isolation_level=None)  # explicit BEGIN/COMMIT
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((SQL_DIR / "schema.sql").read_text())
    return conn


def load_scenario(data_dir: Path) -> dict:
    return json.loads((data_dir / "scenario.json").read_text())


def load_hubs(data_dir: Path, scenario: dict) -> list[dict]:
    with open(data_dir / scenario["hubs_file"], newline="") as fh:
        return list(csv.DictReader(fh))


def read_delivery_file(path: Path) -> tuple[str, list[tuple[int, dict]]]:
    """Return (sha256, [(line_number, row_dict), ...]). Raise on file-level problems."""
    if not path.is_file():
        raise FileLevelError(f"missing file listed in manifest: {path}")
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileLevelError(f"{path}: not UTF-8 ({exc})")
    # strict=True turns malformed quoting into csv.Error instead of guessing.
    # A stream (not splitlines) keeps newlines inside quoted fields intact.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise FileLevelError(f"{path}: empty file (no header)")
    except csv.Error as exc:
        raise FileLevelError(f"{path}:{reader.line_num}: malformed CSV ({exc})")
    if tuple(h.strip() for h in header) != EXPECTED_COLUMNS:
        raise FileLevelError(f"{path}: unexpected header {header}")
    rows = []
    while True:
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise FileLevelError(f"{path}:{reader.line_num}: malformed CSV ({exc})")
        line_no = reader.line_num
        if not any(v.strip() for v in values):
            continue  # ignore fully blank lines
        if len(values) != len(EXPECTED_COLUMNS):
            # Keep it as a row-level reject so it is still visible.
            rows.append((line_no, {"_wrong_field_count": str(len(values)), "_raw": values}))
            continue
        rows.append((line_no, dict(zip(EXPECTED_COLUMNS, values))))
    return sha, rows


def ingest_batch(conn: sqlite3.Connection, data_dir: Path, batch_dir: str) -> dict:
    """Apply one batch to state. Returns a run summary dict."""
    scenario = load_scenario(data_dir)
    batch = next((b for b in scenario["batches"] if b["directory"] == batch_dir), None)
    if batch is None:
        raise FileLevelError(f"batch {batch_dir!r} not in scenario.json manifest")

    interval_minutes = scenario["interval_minutes"]
    hubs = load_hubs(data_dir, scenario)
    allowed_hubs = {h["hub_id"] for h in hubs}

    run_id = f"{utc_now()[:19].replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    started = utc_now()
    conn.execute(
        "INSERT INTO ingest_run (run_id, batch_directory, delivered_at, started_at, status) "
        "VALUES (?, ?, ?, ?, 'running')",
        (run_id, batch_dir, batch.get("delivered_at"), started),
    )

    counts: Counter = Counter()
    reasons: Counter = Counter()
    files_summary = []
    try:
        conn.execute("BEGIN")
        conn.executemany(
            "INSERT INTO hub (hub_id, description) VALUES (?, ?) "
            "ON CONFLICT(hub_id) DO UPDATE SET description = excluded.description",
            [(h["hub_id"], h.get("description")) for h in hubs],
        )
        for file_name in batch["files"]:
            expected_market = FILE_MARKET.get(file_name)
            if expected_market is None:
                raise FileLevelError(f"unknown file type in manifest: {file_name}")
            rel = f"{batch_dir}/{file_name}"
            sha, rows = read_delivery_file(data_dir / batch_dir / file_name)
            previously = conn.execute(
                "SELECT MIN(run_id) FROM ingested_file WHERE file_sha256 = ?", (sha,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO ingested_file (run_id, source_file, file_sha256, rows_read) "
                "VALUES (?, ?, ?, ?)",
                (run_id, rel, sha, len(rows)),
            )
            files_summary.append(
                {"source_file": rel, "sha256": sha, "rows_read": len(rows),
                 "previously_ingested_in_run": previously}
            )
            for line_no, raw in rows:
                outcome, reason, detail = _apply_row(
                    conn, raw, run_id=run_id, rel=rel, sha=sha, line_no=line_no,
                    expected_market=expected_market, interval_minutes=interval_minutes,
                    allowed_hubs=allowed_hubs,
                )
                counts["rows_read"] += 1
                counts[outcome] += 1
                if outcome == "rejected":
                    reasons[reason] += 1
                conn.execute(
                    "INSERT INTO ingest_row_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, rel, line_no, sha, outcome, reason, detail,
                     json.dumps(raw, sort_keys=True)),
                )
        conn.execute("COMMIT")
    except Exception as exc:
        conn.execute("ROLLBACK")
        conn.execute(
            "UPDATE ingest_run SET status = 'failed', finished_at = ?, error = ? WHERE run_id = ?",
            (utc_now(), f"{type(exc).__name__}: {exc}", run_id),
        )
        raise

    conn.execute(
        "UPDATE ingest_run SET status = 'succeeded', finished_at = ? WHERE run_id = ?",
        (utc_now(), run_id),
    )
    return {
        "run_id": run_id,
        "batch_directory": batch_dir,
        "delivered_at": batch.get("delivered_at"),
        "run_status": "succeeded",
        "files": files_summary,
        "row_counts": {
            "rows_read": counts["rows_read"],
            "accepted_new_revision": counts["accepted"],
            "stale_revision": counts["stale_revision"],
            "duplicate": counts["duplicate"],
            "rejected": counts["rejected"],
        },
        "rejections_by_reason": dict(sorted(reasons.items())),
    }


def _apply_row(conn, raw, *, run_id, rel, sha, line_no, expected_market,
               interval_minutes, allowed_hubs) -> tuple[str, str | None, str | None]:
    """Validate and store one row. Returns (outcome, reason, detail)."""
    if "_wrong_field_count" in raw:
        return "rejected", "wrong_field_count", f"{raw['_wrong_field_count']} fields"
    try:
        rec = validate_row(raw, expected_market=expected_market,
                           interval_minutes=interval_minutes, allowed_hubs=allowed_hubs)
    except RowRejected as rej:
        return "rejected", rej.reason, rej.detail

    key = (rec.market, rec.hub_id, rec.interval_start_utc)
    current_max = conn.execute(
        "SELECT MAX(source_revision) FROM price_revision "
        "WHERE market = ? AND hub_id = ? AND interval_start_utc = ?",
        key,
    ).fetchone()[0]
    existing = conn.execute(
        "SELECT price_usd_per_mwh, source_file, source_row FROM price_revision "
        "WHERE market = ? AND hub_id = ? AND interval_start_utc = ? AND source_revision = ?",
        (*key, rec.source_revision),
    ).fetchone()
    if existing is not None:
        if existing["price_usd_per_mwh"] == rec.price_usd_per_mwh:
            older = (f"; older than current revision {current_max}"
                     if current_max > rec.source_revision else "")
            return ("duplicate", "same_key_revision_value",
                    f"already stored from {existing['source_file']}:{existing['source_row']}{older}")
        # Out of scope per contract, but never silently overwrite: reject loudly.
        return ("rejected", "conflicting_revision",
                f"rev {rec.source_revision} already stored with price "
                f"{existing['price_usd_per_mwh']} from {existing['source_file']}:{existing['source_row']}")

    conn.execute(
        "INSERT INTO price_revision (market, hub_id, interval_start_utc, source_revision, "
        "interval_end_utc, price_usd_per_mwh, published_at_utc, source_file, source_row, "
        "file_sha256, first_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rec.market, rec.hub_id, rec.interval_start_utc, rec.source_revision,
         rec.interval_end_utc, rec.price_usd_per_mwh, rec.published_at_utc,
         rel, line_no, sha, run_id),
    )
    if current_max is not None and current_max > rec.source_revision:
        # Kept in history for lineage, but the view keeps the newer revision.
        return "stale_revision", "older_than_current", f"current revision is {current_max}"
    return "accepted", None, None


def hourly_report(conn: sqlite3.Connection, scenario: dict) -> list[dict]:
    window = scenario["report_window"]
    rt_minutes = scenario["interval_minutes"]["RT"]
    params = {
        "window_start": _canonical(window["start_utc"]),
        "window_end": _canonical(window["end_utc"]),
        "rt_expected": 60 // rt_minutes,
    }
    rows = [dict(r) for r in
            conn.execute((SQL_DIR / "hourly_report.sql").read_text(), params).fetchall()]
    for r in rows:
        # RT mean minus DA can exceed the float range even when both inputs are
        # valid (e.g. 1e308 - -1e308). Never publish inf; report_quality flags it.
        diff = r["rt_minus_da_usd_per_mwh"]
        if diff is not None and not math.isfinite(diff):
            r["rt_minus_da_usd_per_mwh"] = None
    return rows


def _canonical(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_quality(report: list[dict]) -> dict:
    """Summarize whether the trader report is complete (distinct from run success)."""
    gaps = []
    for r in report:
        problems = []
        if not r["rt_complete"]:
            problems.append(f"rt {r['rt_intervals_present']}/{r['rt_intervals_expected']}")
        if not r["da_available"]:
            problems.append("da missing")
        if (r["rt_complete"] and r["da_available"]
                and r["rt_minus_da_usd_per_mwh"] is None):
            problems.append("rt_minus_da not representable")
        if problems:
            gaps.append({"hub_id": r["hub_id"], "hour_start_utc": r["hour_start_utc"],
                         "issues": problems})
    publishable = sum(1 for r in report if r["rt_minus_da_usd_per_mwh"] is not None)
    return {
        "report_status": "complete" if not gaps else "incomplete",
        "hourly_rows": len(report),
        "hours_rt_complete": sum(1 for r in report if r["rt_complete"]),
        "hours_da_available": sum(1 for r in report if r["da_available"]),
        "hours_with_publishable_difference": publishable,
        "gaps": gaps,
    }


def state_counts(conn: sqlite3.Connection) -> dict:
    latest = {m: n for m, n in conn.execute(
        "SELECT market, COUNT(*) FROM latest_price GROUP BY market")}
    return {
        "latest_price_rows": sum(latest.values()),
        "latest_price_rows_by_market": latest,
        "price_revision_history_rows": conn.execute(
            "SELECT COUNT(*) FROM price_revision").fetchone()[0],
        "distinct_rejected_source_rows": conn.execute(
            "SELECT COUNT(*) FROM rejected_record").fetchone()[0],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        if not rows:
            return
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _fmt(k, v) for k, v in r.items()})


def _fmt(col: str, value):
    if value is None:
        return ""  # null stays an empty cell, never 0
    if col in BOOL_COLUMNS:
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(round(value, 6))
    return value


def export_latest(conn: sqlite3.Connection, path: Path) -> None:
    rows = [dict(r) for r in conn.execute(
        "SELECT market, hub_id, interval_start_utc, interval_end_utc, price_usd_per_mwh, "
        "source_revision, source_file, source_row FROM latest_price "
        "ORDER BY market, hub_id, interval_start_utc")]
    write_csv(path, rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", required=True, type=Path, help="SQLite state file")
    ap.add_argument("--batch", required=True, help="batch directory name from scenario.json")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--report-out", type=Path, help="write hourly report CSV here")
    ap.add_argument("--latest-out", type=Path, help="write latest-price snapshot CSV here")
    ap.add_argument("--summary-out", type=Path,
                    help="write run summary JSON here (default: <state dir>/runs/<run_id>.json)")
    args = ap.parse_args(argv)

    try:
        # connect() is inside the try so a bad --state path (missing dir,
        # read-only file) gets the same JSON error as an ingest failure.
        conn = connect(args.state)
        summary = ingest_batch(conn, args.data_dir, args.batch)
    except Exception as exc:
        # Any partial batch was rolled back and its run marked failed by ingest_batch.
        error = str(exc) if isinstance(exc, FileLevelError) else f"{type(exc).__name__}: {exc}"
        print(json.dumps({"run_status": "failed", "batch_directory": args.batch,
                          "error": error}, indent=2), file=sys.stderr)
        return 2

    # Ingestion is committed from here on. Any later problem (building the
    # report or writing outputs) is reported as an export failure and never
    # undoes accepted prices.
    summary["export_status"] = "succeeded"
    summary_path = args.summary_out or args.state.parent / "runs" / f"{summary['run_id']}.json"
    try:
        scenario = load_scenario(args.data_dir)
        report = hourly_report(conn, scenario)
        summary["state"] = state_counts(conn)
        summary["data_quality"] = report_quality(report)
        if args.report_out:
            write_csv(args.report_out, report)
        if args.latest_out:
            export_latest(conn, args.latest_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    except Exception as exc:
        summary["export_status"] = "failed"
        summary["export_error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(summary, indent=2), file=sys.stderr)
        return 3

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
