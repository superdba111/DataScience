-- Trader-facing hourly DA vs RT comparison.
-- Parameters: :window_start, :window_end   ('YYYY-MM-DDTHH:MM:SSZ', start inclusive, end exclusive)
--             :rt_expected                  (RT intervals per hour, 4)
--
-- The hub x hour grid is generated first and everything else is LEFT JOINed,
-- so missing data shows up as NULL / count 0 rather than a missing row.
WITH RECURSIVE hours(hour_start_utc) AS (
    SELECT :window_start
    UNION ALL
    SELECT strftime('%Y-%m-%dT%H:%M:%SZ', hour_start_utc, '+1 hour')
    FROM hours
    WHERE strftime('%Y-%m-%dT%H:%M:%SZ', hour_start_utc, '+1 hour') < :window_end
),
grid AS (
    SELECT h.hub_id, hr.hour_start_utc
    FROM hub AS h
    CROSS JOIN hours AS hr
),
da AS (
    -- DA interval start is already the hour start.
    SELECT hub_id, interval_start_utc AS hour_start_utc, price_usd_per_mwh
    FROM latest_price
    WHERE market = 'DA'
),
rt AS (
    -- Bucket by interval START: an RT interval ending 00:00 belongs to the 23:00 hour.
    -- Average price/n, then scale back: a plain AVG sums first, so four valid
    -- prices near the float maximum would overflow to inf. Scaling by 4 is exact.
    SELECT hub_id,
           strftime('%Y-%m-%dT%H:00:00Z', interval_start_utc) AS hour_start_utc,
           AVG(price_usd_per_mwh / :rt_expected) * :rt_expected AS rt_mean,
           COUNT(DISTINCT interval_start_utc)  AS rt_present
    FROM latest_price
    WHERE market = 'RT'
    GROUP BY hub_id, strftime('%Y-%m-%dT%H:00:00Z', interval_start_utc)
)
SELECT
    g.hub_id,
    g.hour_start_utc,
    da.price_usd_per_mwh                                   AS da_price_usd_per_mwh,
    ROUND(rt.rt_mean, 6)                                   AS rt_mean_usd_per_mwh,
    CASE WHEN COALESCE(rt.rt_present, 0) = :rt_expected AND da.price_usd_per_mwh IS NOT NULL
         THEN ROUND(rt.rt_mean - da.price_usd_per_mwh, 6)
    END                                                    AS rt_minus_da_usd_per_mwh,
    COALESCE(rt.rt_present, 0)                             AS rt_intervals_present,
    :rt_expected                                           AS rt_intervals_expected,
    COALESCE(rt.rt_present, 0) = :rt_expected              AS rt_complete,
    da.price_usd_per_mwh IS NOT NULL                       AS da_available
FROM grid AS g
LEFT JOIN da ON da.hub_id = g.hub_id AND da.hour_start_utc = g.hour_start_utc
LEFT JOIN rt ON rt.hub_id = g.hub_id AND rt.hour_start_utc = g.hour_start_utc
ORDER BY g.hub_id, g.hour_start_utc;
