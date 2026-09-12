"""Flambeau generation loading, interpolation, and revenue computation.

`data/raw/flambeau_gen.csv` is a sparse-in-time series of Flambeau MW
readings taken roughly every 4 days. This module:

1. Loads it defensively (`"undefined"` -> NaN, timestamps -> UTC).
2. Trims the unusable 2015 leading block.
3. Reindexes to a continuous hourly UTC grid and interpolates.
4. Joins to the hourly LMP series and produces both hourly revenue and
   daily revenue keyed by local Central calendar date.

## Why interpolate instead of forward-fill?

Hydro plant output tracks river flow. River flow moves on multi-day
timescales, so linear interpolation between 4-day samples is a
physically better approximation than a step function. The forward-fill
variant is still worth computing as a sensitivity check because it is
what a naive reader might reach for; if the two agree to within a few
percent on any 14-day window, the interpolation choice does not drive
the answer.

## The bias this introduces

A single scalar reading every 4 days is expanded to a flat MW profile
within each day, so any within-day price-following behavior by the
plant is erased. Practically:

- If Flambeau shapes output toward high-price hours, we UNDERSTATE the
  true revenue (and therefore the lost revenue during an outage).
- If Flambeau runs run-of-river with no shaping, the bias is ~0.

Direction is knowable, magnitude is not. This is called out in the
report and in the README.

## Output contract

`build_hourly_revenue` returns a DataFrame indexed by tz-aware UTC
hour with columns `mw`, `lmp`, `revenue`. `build_daily_revenue` returns
a DataFrame indexed by local Central calendar `date` with column
`revenue` (sum over the 24 hours whose Central-local date matches).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CENTRAL_TZ = "America/Chicago"

# The provided CSV starts 2015-02-01 but every 2015 value is the sentinel
# "undefined". First usable reading is 2016-01-03.
FIRST_USABLE_DATE = pd.Timestamp("2016-01-03", tz="UTC")


def load_generation_csv(path: Path) -> pd.DataFrame:
    """Load `flambeau_gen.csv` into a clean DataFrame.

    Steps:
      1. `pd.read_csv(path, na_values=["undefined"], parse_dates=["Timestamp"])`.
      2. Ensure the timestamp column is tz-aware in UTC. The provided
         file uses trailing `Z`, so pandas parses it with `utc=True`
         automatically; assert `df["Timestamp"].dt.tz is not None`.
      3. Rename `"Flambeau (MW)"` to `"mw"` and set the timestamp as
         the index (named `utc_time`). Sort by index.
      4. Assert monotone-increasing index and no duplicates.
      5. Return the frame (still containing the 2015 NaN block; trimming
         is `trim_to_usable_range`'s job).
    """
    raise NotImplementedError


def trim_to_usable_range(gen: pd.DataFrame) -> pd.DataFrame:
    """Drop the 2015 leading NaN block and assert no interior NaNs.

    Steps:
      1. Slice to `gen.index >= FIRST_USABLE_DATE`.
      2. Assert `gen["mw"].isna().sum() == 0` on the trimmed frame.
         (An interior NaN means the input file changed since analysis;
         fail loudly rather than silently interpolating over it.)
      3. Assert the diff between consecutive timestamps is always
         `Timedelta("4D")` +/- one hour of daylight-saving jitter.
      4. Return the trimmed frame.
    """
    raise NotImplementedError


def interpolate_hourly(gen: pd.DataFrame) -> pd.DataFrame:
    """Expand the 4-day-cadence series to a continuous hourly UTC grid.

    Steps:
      1. Build the target index:
             new_index = pd.date_range(
                 start=gen.index.min().floor("h"),
                 end=gen.index.max().ceil("h"),
                 freq="h", tz="UTC",
             )
      2. Reindex the frame onto `new_index`. This introduces NaNs at
         every hour that was not an original sample.
      3. Fill with `gen["mw"].interpolate(method="time")`. `method="time"`
         is important - it uses the actual datetime spacing rather than
         treating every gap as equal.
      4. Assert no remaining NaNs.
      5. Return a single-column frame `mw` on the hourly UTC index.

    A `method="ffill"` variant for the sensitivity check is a
    one-liner at the caller.
    """
    raise NotImplementedError


def build_hourly_revenue(
    gen_hourly: pd.DataFrame,
    lmp_hourly: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join generation and LMP on their shared UTC hourly index and
    compute per-hour revenue.

    Steps:
      1. `df = gen_hourly.join(lmp_hourly, how="inner")`. Inner join
         because we only want hours that have both an MW value and an
         LMP - reject any implicit extrapolation.
      2. `df["revenue"] = df["mw"] * df["lmp"]`. Units check: MW *
         $/MWh over a 1-hour interval = $ exactly. If you ever generalize
         to sub-hourly data, multiply by the interval length in hours.
      3. Assert no NaN in any column.
      4. Return `df` with columns `["mw", "lmp", "revenue"]`.
    """
    raise NotImplementedError


def build_daily_revenue(hourly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly revenue into daily totals keyed by local Central
    calendar date.

    Why Central-local dates: the plant and its operator (DPC) live in
    Wisconsin. Outage windows are administratively defined by local
    calendar days, and 14-day sums line up cleanly with local midnight
    boundaries.

    Steps:
      1. Convert the index to Central time:
             local = hourly.index.tz_convert(CENTRAL_TZ)
      2. Group hourly revenue by `local.date` and sum.
      3. Return a DataFrame indexed by `date` (dtype `datetime64[ns]` or
         plain `date` - pick one and stick with it) with column
         `revenue`.
      4. Assert the resulting series is contiguous daily (no missing
         calendar dates) between its first and last date.
    """
    raise NotImplementedError
