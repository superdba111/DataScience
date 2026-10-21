# Data contract and public examples

This contract is intentionally explicit. There are no secret market rules to discover.

## Files and delivery order

| File | Contents |
| --- | --- |
| `data\scenario.json` | Report window, interval lengths, and delivery order. |
| `data\hubs.csv` | The two allowed, fictional hubs. |
| `data\batch_01\day_ahead.csv` | Initial hourly DA prices. |
| `data\batch_01\real_time.csv` | Initial 15-minute RT prices, including known quality issues. |
| `data\batch_02\day_ahead.csv` | One DA price correction. |
| `data\batch_02\real_time.csv` | Late/repaired intervals, an RT correction, and repeated records. |

Treat each batch as a delivery containing only the listed files. Do not read batch 2 when processing batch 1 just because both directories are on disk. Rows within a file are not an ordering guarantee.

The manifest uses a directory name plus file names, rather than OS-specific joined paths. Join them using your platform's path utilities.

The report window is **2026-08-17 22:00 UTC through 2026-08-18 04:00 UTC**, start inclusive and end exclusive. It contains six complete hours for each of two hubs: **12 hourly output rows**. This is a historical fixture, not a feed to compare with today's clock.

## Input schema

Both markets use this CSV schema. All fields are required.

| Field | Meaning and validity |
| --- | --- |
| `market` | `DA` or `RT`. |
| `hub_id` | A hub listed in `hubs.csv`. |
| `interval_end` | ISO 8601 interval-ending timestamp with an explicit UTC offset or `Z`. |
| `price_usd_per_mwh` | A finite numeric price. A blank or nonnumeric value is invalid. **Negative prices, zero, and large positive prices are valid.** |
| `source_revision` | Positive integer revision for this market/hub/interval. Larger means newer. |
| `published_at` | ISO 8601 provider publication timestamp with an explicit offset or `Z`. This is not the interval's business time. |

Normalize timestamps to UTC. DA intervals last 60 minutes; RT intervals last 15 minutes. Valid interval ends align to the corresponding UTC hour or quarter hour. For this fixture there are no daylight-saving transitions or offset-free local timestamps to resolve.

Report invalid rows with a useful reason and source file/row reference, while continuing to process valid rows. File-level read/parse failures should be visible failures, not successful empty loads. You do not need a generalized schema-management framework.

## Time and revision semantics

**Interval start = normalized UTC interval end minus that market's interval duration.**

An interval's canonical business key is `(market, hub_id, interval_start_utc)`. For each key, select the highest valid `source_revision` received in the processed batches. Validate before selecting a winning record.

An older revision delivered after a newer one must not win. Repeating the same valid key/revision/value is a duplicate, including when equivalent timestamps use different UTC offsets. `published_at`, input order, and ingestion time do not override the revision number.

The fixtures have no conflicting valid values for the same key and revision. Conflict resolution, deletions, historical "what did we know at the time?" queries, and simultaneous writers are outside the implementation scope.

Preserve the winning revision and sufficient source lineage to explain a corrected price. A simple input path/row reference or retained source record is enough. Rejected source rows remain part of the ingestion history even if a later valid revision repairs the corresponding interval.

For example, an RT interval ending at `2026-08-18T00:00:00Z` starts at `2026-08-17T23:45:00Z`. It belongs to the **23:00 hour on August 17**, not the 00:00 hour on August 18.

Likewise, `2026-08-17T19:45:00-05:00` and `2026-08-18T00:45:00Z` identify the same interval end. The update file deliberately uses this equivalence.

This report means **latest known from the processed deliveries**. It does not attempt to recreate an earlier publication-time snapshot.

## Required hourly SQL view

Produce one row per configured hub and UTC hour. Column names below make the result easy to review; the internal storage schema is your choice.

| Column | Definition |
| --- | --- |
| `hub_id` | Configured hub. |
| `hour_start_utc` | UTC start of the hour, determined from interval starts, not interval ends. |
| `da_price_usd_per_mwh` | Latest valid DA price for that exact hub/hour, or null. |
| `rt_mean_usd_per_mwh` | Arithmetic mean of available, latest valid RT prices in the hour, or null if none. |
| `rt_minus_da_usd_per_mwh` | RT mean minus DA price **only when all four RT intervals and DA are present**; otherwise null. |
| `rt_intervals_present` | Count of distinct valid RT business intervals, not delivery rows or revisions. |
| `rt_intervals_expected` | `4` for every hour in this report window. |
| `rt_complete` | True exactly when all four expected RT intervals are present. |
| `da_available` | True when a valid DA price is available. |

All RT intervals have equal duration, so a simple arithmetic mean is intentional. No volume weighting is needed.

An incomplete hour may show an observed RT mean, but its incomplete flag and null difference must remain visible. If DA is missing, retain the hour and its RT values; do not let an inner join hide it. If all RT intervals are missing, retain the hour with count zero and null RT mean/difference.

Do not forward-fill, interpolate, substitute zero for null, cap a valid spike, or drop negative prices. These would change the trader's meaning.

UTC `Z` and `+00:00` representations are equivalent. Use numeric values for prices; at least six decimal places for repeating means is sufficient. CSV may represent null as an empty cell and booleans as `true`/`false` or documented `1`/`0`.

## Disclosed data situations

Batch 1 contains one exact RT duplicate and three invalid RT rows: a blank price, an unknown hub, and an unparseable interval timestamp. One other RT interval has not arrived. One DA hour is absent and stays absent.

Batch 2 supplies the delayed RT interval, a valid higher revision for the blank-price interval, one RT price correction, and one DA price correction. It also repeats the RT correction and includes its older version after the newer one. These are ordinary retry/correction cases, not traps.

The gaps and corrections are intentionally small enough to inspect by hand.

### Public row-count checks

| State | Input rows in this delivery, excluding headers | Latest valid price rows, DA and RT combined | Hourly rows |
| --- | --- | --- | --- |
| After batch 1 | 61: 11 DA and 50 RT | 57: 11 DA and 46 RT | 12 |
| After batch 2 | 6: 1 DA and 5 RT | 59: 11 DA and 48 RT | 12 |
| After replaying batch 2 | Same six delivery rows again | Still 59 | Still 12 |

The latest-price counts are logical counts; an append-only history table may have more physical rows. Batch 1 has three rejected rows and one duplicate. How you classify replay attempts in per-run counters is your choice; explain it rather than trying to match an unspecified counter convention.

### Public result examples

Times below are UTC hour starts.

| Hub and hour | After batch 1 | After batch 2 |
| --- | --- | --- |
| NORTH_HUB, Aug 18 00:00 | DA 40; RT mean 41; difference 1; 4/4 RT. | DA 40; RT mean 46; difference 6; 4/4 RT. |
| NORTH_HUB, Aug 18 01:00 | DA 45; RT mean 44.666667; **null difference**; 3/4 RT. | DA 45; RT mean 45; difference 0; 4/4 RT. |
| SOUTH_HUB, Aug 18 00:00 | DA 35; RT mean -2.5; difference -37.5; 4/4 RT. | Unchanged. Negative prices are valid. |
| SOUTH_HUB, Aug 18 02:00 | DA null; RT mean 47; difference null; 4/4 RT; DA unavailable. | Unchanged. Complete RT does not imply a complete comparison. |

After the updates, all 12 hours have complete RT coverage, but only 11 have a publishable RT-minus-DA difference. Historical rejections should still be explainable. Successful processing is not the same as having every expected price.
