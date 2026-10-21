"""Row-level parsing and validation.

Every function here is pure: it takes raw strings and returns either a
normalized record or a rejection reason. No I/O, so it is easy to unit test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

EXPECTED_COLUMNS = (
    "market",
    "hub_id",
    "interval_end",
    "price_usd_per_mwh",
    "source_revision",
    "published_at",
)

UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"

# The contract says "positive integer" with no upper bound; SQLite INTEGER is
# signed 64-bit, so larger values are rejected rather than crashing the batch.
MAX_REVISION = 2**63 - 1


@dataclass(frozen=True)
class PriceRecord:
    market: str
    hub_id: str
    interval_start_utc: str
    interval_end_utc: str
    price_usd_per_mwh: float
    source_revision: int
    published_at_utc: str


class RowRejected(ValueError):
    """Raised with a short, stable reason code plus a human-readable detail."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def to_utc_text(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(UTC_FMT)


def parse_aware_timestamp(value: str, field: str) -> datetime:
    """Parse ISO 8601 and insist on an explicit offset (or Z)."""
    text = (value or "").strip()
    if not text:
        raise RowRejected(f"missing_{field}", f"{field} is blank")
    try:
        # Python 3.11 fromisoformat accepts 'Z' and +HH:MM offsets.
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise RowRejected(f"unparseable_{field}", f"{field}={text!r} is not ISO 8601")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RowRejected(f"naive_{field}", f"{field}={text!r} has no UTC offset")
    try:
        return dt.astimezone(timezone.utc)
    except OverflowError:
        # e.g. 0001-01-01T00:00:00+01:00 falls before datetime.min in UTC.
        raise RowRejected(f"out_of_range_{field}",
                          f"{field}={text!r} is outside the supported date range")


def validate_row(
    raw: dict[str, str],
    *,
    expected_market: str,
    interval_minutes: dict[str, int],
    allowed_hubs: set[str],
) -> PriceRecord:
    """Validate one CSV row. Returns a normalized record or raises RowRejected.

    Checks run in a fixed order so the first, most fundamental problem is the
    reported reason.
    """
    market = (raw.get("market") or "").strip()
    if market not in interval_minutes:
        raise RowRejected("unknown_market", f"market={market!r}")
    if market != expected_market:
        raise RowRejected(
            "market_file_mismatch",
            f"market={market!r} found in a {expected_market} file",
        )

    hub_id = (raw.get("hub_id") or "").strip()
    if hub_id not in allowed_hubs:
        raise RowRejected("unknown_hub", f"hub_id={hub_id!r} not in hubs.csv")

    end = parse_aware_timestamp(raw.get("interval_end", ""), "interval_end")
    minutes = interval_minutes[market]
    if end.second or end.microsecond or end.minute % minutes:
        raise RowRejected(
            "misaligned_interval_end",
            f"{to_utc_text(end)} is not on a {minutes}-minute UTC boundary",
        )
    try:
        start = end - timedelta(minutes=minutes)
    except OverflowError:
        raise RowRejected("out_of_range_interval_end",
                          f"{to_utc_text(end)} leaves no room for a {minutes}-minute interval start")

    price_text = (raw.get("price_usd_per_mwh") or "").strip()
    if not price_text:
        raise RowRejected("missing_price", "price_usd_per_mwh is blank")
    try:
        price = float(price_text)
    except ValueError:
        raise RowRejected("nonnumeric_price", f"price_usd_per_mwh={price_text!r}")
    if not math.isfinite(price):
        # Negative, zero and large prices are valid; NaN/inf are not.
        raise RowRejected("nonfinite_price", f"price_usd_per_mwh={price_text!r}")

    rev_text = (raw.get("source_revision") or "").strip()
    try:
        revision = int(rev_text)
    except ValueError:
        raise RowRejected("invalid_revision", f"source_revision={rev_text!r}")
    if revision < 1:
        raise RowRejected("invalid_revision", f"source_revision={rev_text!r} must be >= 1")
    if revision > MAX_REVISION:
        raise RowRejected("invalid_revision",
                          f"source_revision={rev_text!r} exceeds supported maximum {MAX_REVISION}")

    published = parse_aware_timestamp(raw.get("published_at", ""), "published_at")

    return PriceRecord(
        market=market,
        hub_id=hub_id,
        interval_start_utc=to_utc_text(start),
        interval_end_utc=to_utc_text(end),
        price_usd_per_mwh=price,
        source_revision=revision,
        published_at_utc=to_utc_text(published),
    )
