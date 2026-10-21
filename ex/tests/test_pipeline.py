"""Focused tests: time aggregation, corrections/replays, invalid and missing data.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from market_pulse import pipeline
from market_pulse.validation import RowRejected, validate_row

REPO_DATA = Path(__file__).resolve().parent.parent / "data"
HEADER = "market,hub_id,interval_end,price_usd_per_mwh,source_revision,published_at\n"
IM = {"DA": 60, "RT": 15}
HUBS = {"NORTH_HUB", "SOUTH_HUB"}


def raw(market="RT", hub="NORTH_HUB", end="2026-08-18T00:00:00Z", price="10",
        rev="1", pub="2026-08-18T00:02:00Z"):
    return {"market": market, "hub_id": hub, "interval_end": end,
            "price_usd_per_mwh": price, "source_revision": rev, "published_at": pub}


class ValidationTests(unittest.TestCase):
    def check(self, expected_reason, file_market="RT", **kw):
        with self.assertRaises(RowRejected) as ctx:
            validate_row(raw(**kw), expected_market=file_market,
                         interval_minutes=IM, allowed_hubs=HUBS)
        self.assertEqual(ctx.exception.reason, expected_reason)

    def test_interval_start_is_end_minus_duration_and_offsets_normalize(self):
        rec = validate_row(raw(end="2026-08-17T19:45:00-05:00"), expected_market="RT",
                           interval_minutes=IM, allowed_hubs=HUBS)
        self.assertEqual(rec.interval_end_utc, "2026-08-18T00:45:00Z")
        self.assertEqual(rec.interval_start_utc, "2026-08-18T00:30:00Z")
        da = validate_row(raw(market="DA", end="2026-08-18T00:00:00+00:00"),
                          expected_market="DA", interval_minutes=IM, allowed_hubs=HUBS)
        self.assertEqual(da.interval_start_utc, "2026-08-17T23:00:00Z")

    def test_negative_zero_and_spike_prices_are_valid(self):
        for p in ("-10", "0", "0.00", "9999"):
            rec = validate_row(raw(price=p), expected_market="RT",
                               interval_minutes=IM, allowed_hubs=HUBS)
            self.assertEqual(rec.price_usd_per_mwh, float(p))

    def test_invalid_rows_get_specific_reasons(self):
        self.check("missing_price", price="")
        self.check("nonnumeric_price", price="abc")
        self.check("nonfinite_price", price="nan")
        self.check("unknown_hub", hub="HUB_UNKNOWN")
        self.check("unparseable_interval_end", end="not-a-timestamp")
        self.check("naive_interval_end", end="2026-08-18T00:00:00")
        self.check("misaligned_interval_end", end="2026-08-18T00:10:00Z")
        self.check("invalid_revision", rev="0")
        self.check("invalid_revision", rev="x")
        self.check("invalid_revision", rev=str(2**63))  # beyond SQLite INTEGER
        self.check("market_file_mismatch", market="DA")  # DA row in an RT file
        with self.assertRaises(RowRejected) as ctx:
            validate_row(raw(market="DA", end="2026-08-18T00:15:00Z"), expected_market="DA",
                         interval_minutes=IM, allowed_hubs=HUBS)
        self.assertEqual(ctx.exception.reason, "misaligned_interval_end")

    def test_extreme_timestamps_are_rejected_not_raised(self):
        self.check("out_of_range_interval_end", end="0001-01-01T00:00:00Z")
        self.check("out_of_range_interval_end", end="0001-01-01T00:00:00+01:00")
        self.check("out_of_range_published_at", pub="9999-12-31T23:59:59-01:00")


class PipelineTestCase(unittest.TestCase):
    """Builds a throwaway data dir so each test controls its own deliveries."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.data.mkdir()
        shutil.copy(REPO_DATA / "hubs.csv", self.data / "hubs.csv")
        self.batches = []
        self.conn = pipeline.connect(self.tmp / "state.db")

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp)

    def add_batch(self, name, da_rows=(), rt_rows=()):
        d = self.data / name
        d.mkdir()
        (d / "day_ahead.csv").write_text(HEADER + "".join(r + "\n" for r in da_rows))
        (d / "real_time.csv").write_text(HEADER + "".join(r + "\n" for r in rt_rows))
        self.batches.append({"directory": name, "delivered_at": None,
                             "files": ["day_ahead.csv", "real_time.csv"]})
        (self.data / "scenario.json").write_text(json.dumps({
            "hubs_file": "hubs.csv",
            "report_window": {"start_utc": "2026-08-18T00:00:00Z",
                              "end_utc": "2026-08-18T02:00:00Z"},
            "interval_minutes": IM,
            "batches": self.batches,
        }))

    def run_batch(self, name):
        return pipeline.ingest_batch(self.conn, self.data, name)

    def report(self):
        scenario = pipeline.load_scenario(self.data)
        return {(r["hub_id"], r["hour_start_utc"]): r
                for r in pipeline.hourly_report(self.conn, scenario)}

    def latest(self):
        return [tuple(r) for r in self.conn.execute(
            "SELECT market, hub_id, interval_start_utc, price_usd_per_mwh, source_revision "
            "FROM latest_price ORDER BY 1, 2, 3")]


def rt(end, price, rev=1, hub="NORTH_HUB"):
    return f"RT,{hub},{end},{price},{rev},2026-08-18T05:00:00Z"


def da(end, price, rev=1, hub="NORTH_HUB"):
    return f"DA,{hub},{end},{price},{rev},2026-08-17T18:00:00Z"


FULL_HOUR_00 = [rt("2026-08-18T00:15:00Z", 10), rt("2026-08-18T00:30:00Z", 20),
                rt("2026-08-18T00:45:00Z", 30), rt("2026-08-18T01:00:00Z", 40)]


class AggregationTests(PipelineTestCase):
    def test_rt_interval_ending_on_the_hour_belongs_to_previous_hour(self):
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 20)], rt_rows=FULL_HOUR_00)
        self.run_batch("b1")
        rep = self.report()
        h0 = rep[("NORTH_HUB", "2026-08-18T00:00:00Z")]
        self.assertEqual(h0["rt_intervals_present"], 4)
        self.assertEqual(h0["rt_mean_usd_per_mwh"], 25.0)
        self.assertEqual(h0["da_price_usd_per_mwh"], 20.0)
        self.assertEqual(h0["rt_minus_da_usd_per_mwh"], 5.0)
        self.assertTrue(h0["rt_complete"] and h0["da_available"])
        # The 01:00 ending interval must not leak into the 01:00 hour.
        self.assertEqual(rep[("NORTH_HUB", "2026-08-18T01:00:00Z")]["rt_intervals_present"], 0)

    def test_grid_keeps_every_hub_and_hour_with_nulls_not_zeros(self):
        self.add_batch("b1", rt_rows=FULL_HOUR_00[:3])  # no DA, 3/4 RT
        self.run_batch("b1")
        rep = self.report()
        self.assertEqual(len(rep), 4)  # 2 hubs x 2 hours
        partial = rep[("NORTH_HUB", "2026-08-18T00:00:00Z")]
        self.assertEqual(partial["rt_intervals_present"], 3)
        self.assertEqual(partial["rt_mean_usd_per_mwh"], 20.0)  # observed mean is shown
        self.assertIsNone(partial["rt_minus_da_usd_per_mwh"])
        self.assertFalse(partial["rt_complete"])
        self.assertIsNone(partial["da_price_usd_per_mwh"])
        empty = rep[("SOUTH_HUB", "2026-08-18T01:00:00Z")]
        self.assertEqual(empty["rt_intervals_present"], 0)
        self.assertIsNone(empty["rt_mean_usd_per_mwh"])
        self.assertFalse(empty["da_available"])

    def test_complete_rt_without_da_has_no_difference(self):
        self.add_batch("b1", rt_rows=FULL_HOUR_00)
        self.run_batch("b1")
        h0 = self.report()[("NORTH_HUB", "2026-08-18T00:00:00Z")]
        self.assertTrue(h0["rt_complete"])
        self.assertIsNone(h0["rt_minus_da_usd_per_mwh"])

    def test_extreme_valid_prices_never_produce_inf(self):
        big = [rt(f"2026-08-18T00:{m}:00Z", "1e308") for m in ("15", "30", "45")]
        big.append(rt("2026-08-18T01:00:00Z", "1e308"))
        south = [rt(r.split(",")[2], "1e308", hub="SOUTH_HUB") for r in big]
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 0),
                                      da("2026-08-18T01:00:00Z", "-1e308", hub="SOUTH_HUB")],
                       rt_rows=big + south)
        self.run_batch("b1")
        rep = self.report()
        north = rep[("NORTH_HUB", "2026-08-18T00:00:00Z")]
        self.assertEqual(north["rt_mean_usd_per_mwh"], 1e308)  # plain AVG gives inf
        self.assertEqual(north["rt_minus_da_usd_per_mwh"], 1e308)
        # 1e308 - -1e308 is outside the float range: withheld and reported, not inf.
        unrep = rep[("SOUTH_HUB", "2026-08-18T00:00:00Z")]
        self.assertEqual(unrep["rt_mean_usd_per_mwh"], 1e308)
        self.assertIsNone(unrep["rt_minus_da_usd_per_mwh"])
        quality = pipeline.report_quality(list(rep.values()))
        self.assertEqual(quality["hours_with_publishable_difference"], 1)
        self.assertIn({"hub_id": "SOUTH_HUB", "hour_start_utc": "2026-08-18T00:00:00Z",
                       "issues": ["rt_minus_da not representable"]}, quality["gaps"])


class RevisionAndReplayTests(PipelineTestCase):
    def test_correction_wins_and_older_revision_arriving_later_does_not(self):
        self.add_batch("b1", rt_rows=[rt("2026-08-18T00:15:00Z", 10, rev=2)])
        self.add_batch("b2", rt_rows=[rt("2026-08-18T00:15:00Z", 99, rev=1)])
        self.run_batch("b1")
        summary = self.run_batch("b2")
        self.assertEqual(summary["row_counts"]["stale_revision"], 1)
        self.assertEqual(self.latest(), [("RT", "NORTH_HUB", "2026-08-18T00:00:00Z", 10.0, 2)])
        # Older revision is still kept in the history for lineage.
        n = self.conn.execute("SELECT COUNT(*) FROM price_revision").fetchone()[0]
        self.assertEqual(n, 2)

    def test_higher_revision_corrects_and_keeps_lineage(self):
        self.add_batch("b1", rt_rows=[rt("2026-08-18T00:15:00Z", 10)])
        self.add_batch("b2", rt_rows=[rt("2026-08-17T19:15:00-05:00", 12, rev=2)])
        self.run_batch("b1")
        self.run_batch("b2")
        row = self.conn.execute("SELECT * FROM latest_price").fetchone()
        self.assertEqual((row["price_usd_per_mwh"], row["source_revision"]), (12.0, 2))
        self.assertEqual((row["source_file"], row["source_row"]), ("b2/real_time.csv", 2))

    def test_replay_and_offset_equivalent_duplicates_are_idempotent(self):
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 20)], rt_rows=FULL_HOUR_00 + [
            rt("2026-08-17T19:15:00-05:00", 10),  # same as first row, different offset
        ])
        first = self.run_batch("b1")
        self.assertEqual(first["row_counts"]["duplicate"], 1)
        before = (self.latest(), self.report())
        replay = self.run_batch("b1")
        self.assertEqual(replay["row_counts"]["duplicate"], 6)
        self.assertEqual(replay["row_counts"]["accepted_new_revision"], 0)
        self.assertEqual((self.latest(), self.report()), before)

    def test_rejected_row_repaired_later_stays_in_history(self):
        self.add_batch("b1", rt_rows=[rt("2026-08-18T00:15:00Z", "")])
        self.add_batch("b2", rt_rows=[rt("2026-08-18T00:15:00Z", 15, rev=2)])
        s1 = self.run_batch("b1")
        self.assertEqual(s1["rejections_by_reason"], {"missing_price": 1})
        self.run_batch("b2")
        self.assertEqual(len(self.latest()), 1)
        rej = self.conn.execute("SELECT source_file, source_row, reason FROM rejected_record").fetchall()
        self.assertEqual([tuple(r) for r in rej], [("b1/real_time.csv", 2, "missing_price")])


class FileLevelFailureTests(PipelineTestCase):
    def test_bad_header_fails_run_and_rolls_back(self):
        self.add_batch("b1", rt_rows=FULL_HOUR_00)
        (self.data / "b1" / "day_ahead.csv").write_text("wrong,header\n1,2\n")
        with self.assertRaises(pipeline.FileLevelError):
            self.run_batch("b1")
        self.assertEqual(self.latest(), [])  # nothing half-applied
        status = self.conn.execute("SELECT status FROM ingest_run").fetchone()[0]
        self.assertEqual(status, "failed")

    def test_malformed_quoting_in_second_file_fails_run_and_cli(self):
        # day_ahead.csv (valid) is applied first, then real_time.csv is malformed.
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 20)],
                       rt_rows=['RT,NORTH_HUB,2026-08-18T00:15:00Z,10,1,"2026-08-18T05:00:00Z'])
        with self.assertRaisesRegex(pipeline.FileLevelError, r"real_time\.csv:2: malformed CSV"):
            self.run_batch("b1")
        self.assertEqual(self.latest(), [])
        status = self.conn.execute("SELECT status FROM ingest_run").fetchone()[0]
        self.assertEqual(status, "failed")
        err = io.StringIO()
        with redirect_stderr(err):
            code = pipeline.main(["--state", str(self.tmp / "state.db"), "--batch", "b1",
                                  "--data-dir", str(self.data)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(err.getvalue())["run_status"], "failed")


class ExportFailureTests(PipelineTestCase):
    def test_export_failure_keeps_prices_and_rerun_recovers(self):
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 20)], rt_rows=FULL_HOUR_00)
        blocker = self.tmp / "not_a_dir"
        blocker.write_text("")
        base = ["--state", str(self.tmp / "state.db"), "--batch", "b1",
                "--data-dir", str(self.data), "--summary-out", str(self.tmp / "s.json")]
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = pipeline.main(base + ["--report-out", str(blocker / "hourly.csv")])
        self.assertEqual(code, 3)
        failed = json.loads(err.getvalue())
        self.assertEqual((failed["run_status"], failed["export_status"]), ("succeeded", "failed"))
        self.assertEqual(len(self.latest()), 5)  # ingestion stays committed

        report = self.tmp / "hourly.csv"
        with redirect_stdout(io.StringIO()):
            code = pipeline.main(base + ["--report-out", str(report)])
        self.assertEqual(code, 0)
        rerun = json.loads((self.tmp / "s.json").read_text())
        self.assertEqual(rerun["row_counts"]["duplicate"], 5)
        self.assertEqual(rerun["export_status"], "succeeded")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(report.read_text())))), 4)

    def test_report_failure_after_commit_is_structured_export_failure(self):
        self.add_batch("b1", da_rows=[da("2026-08-18T01:00:00Z", 20)], rt_rows=FULL_HOUR_00)
        args = ["--state", str(self.tmp / "state.db"), "--batch", "b1",
                "--data-dir", str(self.data), "--summary-out", str(self.tmp / "s.json")]
        err = io.StringIO()
        with mock.patch.object(pipeline, "hourly_report", side_effect=RuntimeError("boom")), \
                redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = pipeline.main(args)
        self.assertEqual(code, 3)
        failed = json.loads(err.getvalue())
        self.assertEqual((failed["run_status"], failed["export_status"]), ("succeeded", "failed"))
        self.assertEqual(failed["export_error"], "RuntimeError: boom")
        self.assertEqual(len(self.latest()), 5)  # ingestion stays committed


class FixtureAcceptanceTest(unittest.TestCase):
    """End-to-end against the supplied fixtures and the public examples."""

    def test_public_examples(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            conn = pipeline.connect(tmp / "state.db")
            scenario = pipeline.load_scenario(REPO_DATA)

            def rep():
                return {(r["hub_id"], r["hour_start_utc"][11:16], r["hour_start_utc"][8:10]): r
                        for r in pipeline.hourly_report(conn, scenario)}

            pipeline.ingest_batch(conn, REPO_DATA, "batch_01")
            self.assertEqual(pipeline.state_counts(conn)["latest_price_rows"], 57)
            r1 = rep()
            n01 = r1[("NORTH_HUB", "01:00", "18")]
            self.assertEqual((n01["rt_mean_usd_per_mwh"], n01["rt_intervals_present"]), (44.666667, 3))
            self.assertIsNone(n01["rt_minus_da_usd_per_mwh"])

            pipeline.ingest_batch(conn, REPO_DATA, "batch_02")
            pipeline.ingest_batch(conn, REPO_DATA, "batch_02")
            self.assertEqual(pipeline.state_counts(conn)["latest_price_rows"], 59)
            r2 = rep()
            self.assertEqual(len(r2), 12)
            self.assertEqual(r2[("NORTH_HUB", "00:00", "18")]["rt_minus_da_usd_per_mwh"], 6.0)
            self.assertEqual(r2[("NORTH_HUB", "01:00", "18")]["rt_minus_da_usd_per_mwh"], 0.0)
            self.assertEqual(r2[("SOUTH_HUB", "00:00", "18")]["rt_mean_usd_per_mwh"], -2.5)
            s02 = r2[("SOUTH_HUB", "02:00", "18")]
            self.assertTrue(s02["rt_complete"])
            self.assertFalse(s02["da_available"])
            self.assertEqual(sum(r["rt_complete"] for r in r2.values()), 12)
            self.assertEqual(sum(r["rt_minus_da_usd_per_mwh"] is not None for r in r2.values()), 11)
            conn.close()
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
