"""MISO Day-Ahead ExPost LMP acquisition for the DPC.FLAMBEAU node.

This module builds a tidy hourly LMP series for a single MISO node from
MISO's public bulk market-report surface. It is deliberately narrow: it
never lists a report directory, never parses HTML, and never guesses
file names - it constructs the two documented URL templates for the
range of dates the caller asks for.

## URL conventions (verified against live MISO surface)

Two file kinds cover the entire history we care about, with a clean
cutover at the end of 2022:

- Monthly zip, 2015-02 through 2022-12:
      https://docs.misoenergy.org/marketreports/YYYYMM_da_expost_lmp_csv.zip
  Each zip contains one daily CSV per market date, same schema as the
  standalone daily files.
- Daily CSV, 2023-01-01 onward:
      https://docs.misoenergy.org/marketreports/YYYYMMDD_da_expost_lmp.csv

Both formats have identical inner structure: 4 preamble lines, then a
header row `Node,Type,Value,HE 1,HE 2,...,HE 24`, then many rows. For
each node MISO publishes three rows: `LMP`, `MCC` (marginal congestion),
and `MLC` (marginal loss). We only need `LMP`.

## Time convention (this is the easy-to-miss bit)

The 4th preamble line of every file reads:

    All Hours-Ending are Eastern Standard Time (EST)

That is a **fixed UTC-5 offset year-round**, not `America/New_York`.
Consequences:

- DST transition days have exactly 24 HE columns. There is no missing
  spring-forward hour and no duplicate fall-back hour.
- Do NOT localize timestamps to `America/New_York`; pandas will try to
  "correct" a nonexistent local-time hour and either raise or shift.
- The mapping is:
      HE h covers wall-clock interval [h - 1, h) EST
      utc_start = file_date_midnight_utc + (h - 1) hours + 5 hours

## Output contract for build_lmp_hourly

A DataFrame with:

- index: `utc_start` (tz-aware `UTC`, hourly, unique, monotonic).
- column: `lmp` (float, $/MWh). Nothing else.

Downstream code (see `src.gen.build_hourly_revenue`) joins this to the
interpolated generation series on `utc_start`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

MISO_BASE = "https://docs.misoenergy.org/marketreports"

TARGET_NODE = "DPC.FLAMBEAU"
TARGET_TYPE = "Gennode"
TARGET_VALUE = "LMP"

# Inclusive cutover. Dates <= this come from monthly zips; dates > this
# come from standalone daily CSVs. Both endpoints have been HEAD-checked.
ZIP_LAST_DAY = date(2022, 12, 31)

# 4 lines of preamble before the real header. Confirmed for both a 2024
# daily file and a monthly-zip inner file.
CSV_SKIPROWS = 4

# One request session should be shared across all downloads. Kept module
# level and lazily initialized so tests can monkeypatch it.
_SESSION = None


def get_session():
    """Return a shared `requests.Session` with a real User-Agent set.

    Notes for the implementer:
    - MISO's CDN is anonymous but occasionally throttles bare-`python`
      user agents; set something identifiable like
      `"flambeau-outage-analysis (educational)"`.
    - Configure a `requests.adapters.HTTPAdapter` with
      `urllib3.util.Retry` for a handful of retries with backoff on 5xx
      and connection errors. Do NOT retry 404 - a genuine 404 means
      MISO simply did not publish that date and we should record it,
      not spin.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# URL builders. Pure string construction from the documented convention.
# No page parsing, no listing, no discovery. These are the only two
# entry points into the MISO surface used by this module.
# ---------------------------------------------------------------------------


def daily_url(d: date) -> str:
    """Return the URL of the standalone daily ExPost LMP CSV for date `d`.

    Example: `daily_url(date(2024, 5, 24))` ->
    `.../marketreports/20240524_da_expost_lmp.csv`.
    """
    raise NotImplementedError


def monthly_zip_url(year: int, month: int) -> str:
    """Return the URL of the monthly zip archive for (year, month).

    Example: `monthly_zip_url(2019, 3)` ->
    `.../marketreports/201903_da_expost_lmp_csv.zip`.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Low-level parsers. Each returns a "long" hourly frame with columns
# `utc_start` and `lmp` for the DPC.FLAMBEAU / LMP row only - MCC and
# MLC rows are dropped. Any per-file validation belongs here so failures
# are localized to the file that caused them.
# ---------------------------------------------------------------------------


def parse_daily_csv_bytes(raw: bytes, file_date: date) -> pd.DataFrame:
    """Parse the bytes of one daily ExPost LMP CSV.

    Steps:
      1. Read with `pd.read_csv(io.BytesIO(raw), skiprows=CSV_SKIPROWS,
         thousands=",")`. `thousands=","` matters because scarcity-event
         prices are occasionally quoted with commas.
      2. Filter to rows where `Node == TARGET_NODE` and
         `Value == TARGET_VALUE`. Assert exactly one row remains; if
         zero, raise (missing target); if >1, raise (schema drift).
      3. Melt the 24 `HE 1` ... `HE 24` columns into long form
         (`he`, `lmp`).
      4. Coerce `he` -> int by stripping the `"HE "` prefix. Coerce
         `lmp` with `pd.to_numeric(errors="coerce")` and assert no NaN
         appeared (defense against a stray non-numeric cell).
      5. Compute UTC start:
             utc_start = Timestamp(file_date, tz="UTC")
                         + Timedelta(hours=(he - 1) + 5)
         This encodes the fixed-EST convention (see module docstring).
      6. Sort by `utc_start`, drop `he`, return a DataFrame with columns
         `["utc_start", "lmp"]` and 24 rows.
    """
    raise NotImplementedError


def fetch_day(d: date) -> pd.DataFrame | None:
    """Fetch and parse a single standalone daily CSV.

    Return `None` on HTTP 404 (some dates are missing on MISO's surface).
    Raise on any other HTTP error. Caller is responsible for logging
    the missing date to a "gaps" list.
    """
    raise NotImplementedError


def fetch_month_from_zip(year: int, month: int) -> tuple[pd.DataFrame, list[date]]:
    """Download a monthly zip, extract every daily CSV inside, and return
    the concatenated hourly frame plus a list of any missing dates
    (dates in that month whose inner CSV was absent from the zip).

    Implementation notes:
      1. Download the zip bytes with `get_session().get(url).content`.
         For 5-7 MB archives this fits in memory fine.
      2. Open with `zipfile.ZipFile(io.BytesIO(bytes_))`.
      3. Iterate `zf.namelist()`. Filenames inside are of the form
         `YYYYMMDD_da_expost_lmp.csv`; parse the date from the name
         rather than trusting alphabetical order.
      4. For each inner CSV, read its bytes with `zf.read(name)` and
         pass to `parse_daily_csv_bytes`.
      5. Track which calendar dates in the month never appeared; return
         those in the missing list.
      6. Concatenate the per-day frames with `pd.concat`, sort by
         `utc_start`, return.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# High-level orchestration + caching.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildReport:
    """Summary of a `build_lmp_hourly` run, for logging and validation.

    Fields:
        n_hours: total hourly rows returned.
        n_days: distinct market dates covered.
        missing_days: dates the caller asked for that MISO did not publish.
        cache_hits: how many months/days were served from the parquet cache.
        cache_misses: how many months/days required an HTTP download.
    """

    n_hours: int
    n_days: int
    missing_days: list[date]
    cache_hits: int
    cache_misses: int


def build_lmp_hourly(
    start: date,
    end: date,
    cache_dir: Path,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, BuildReport]:
    """Assemble the hourly LMP frame for `DPC.FLAMBEAU` between `start`
    and `end` inclusive, using the zip source for dates <= ZIP_LAST_DAY
    and the daily source for dates > ZIP_LAST_DAY.

    Caching strategy (implementer):
      - Persist extracted rows only, never the raw archives. Two
        artifacts:
            {cache_dir}/lmp_month_YYYYMM.parquet   for zip-era months
            {cache_dir}/lmp_day_YYYYMMDD.parquet   for daily-era days
        Each holds the 24-row hourly frame for that unit.
      - Concatenate the union at the end and slice to [start, end].
      - `force_refresh=True` re-downloads even if a cache file exists.

    Networking guidance (implementer):
      - Use a small thread pool (4-8 workers) with the shared session.
        MISO throttles bare bursts; 4-8 concurrent is polite and fast.
      - Progress: print or `tqdm` per unit; a full 2016-01..today build
        is ~84 zips + ~1300 daily files and takes 30-60 minutes wall
        clock on a normal home connection.

    Returns:
        (frame, report). `frame` has index `utc_start` (tz=UTC) and one
        column `lmp`. It contains exactly 24 rows per successful market
        date, no duplicates, and no NaNs.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Validation helpers. Run these in the acquisition notebook after
# build_lmp_hourly finishes; they should all pass without any manual
# inspection required.
# ---------------------------------------------------------------------------


def validate_lmp_frame(
    frame: pd.DataFrame,
    expected_start: date,
    expected_end: date,
    known_missing: Iterable[date] = (),
) -> None:
    """Run the standard acquisition sanity checks.

    Should verify:
      1. `frame.index.tz` is UTC.
      2. Index is unique and monotonically increasing.
      3. Every market date in [expected_start, expected_end] except
         those in `known_missing` has exactly 24 hourly rows.
      4. No NaN in `lmp`.
      5. `lmp` values are in a sane physical range (roughly -$500 to
         +$5000 for MISO). This catches unit or sign bugs immediately.
      6. Spot-check that known extreme events have known extreme prices,
         e.g. 2021-02-15 (Winter Storm Uri) has a very high mean.

    Raise `AssertionError` with a clear message on any failure.
    """
    raise NotImplementedError
