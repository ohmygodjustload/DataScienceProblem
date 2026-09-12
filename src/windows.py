"""2-week outage window enumeration, ranking, and uncertainty.

Given a daily revenue series with at least a few complete years of
history, this module ranks every possible 14-day window in 2027 by the
opportunity cost of taking that window as an outage.

## What "best" means

The problem statement says the best window is one where lost revenue
is "consistently low." That is two criteria bundled together:

- **Low expected loss.** Averaged over what history tells us,
  the outage costs less to take here than elsewhere.
- **Low variability.** The cost is not just low on average - it is
  low even in a bad year. A window whose historical cost swings
  wildly year to year is not "consistent," even if its average is
  small.

We report metrics for both. The three recommended candidates cover
both readings: some optimize the mean, at least one optimizes the
downside (P90).

## Why we normalize to shares of annual revenue

Comparing raw dollars across 2016-2025 is unfair because MISO prices
inflated with natural gas during 2022 and have receded since - a
14-day window in 2022 looks "expensive" for reasons that have nothing
to do with when in the year it fell. To remove that:

1. For each historical year `y` and candidate window `w`, take the
   14-day revenue `C[w, y]` and divide by that year's total revenue.
   The result `share[w, y]` is between 0 and 1 and is what fraction
   of a whole year of revenue the window represents.
2. Average the shares across years - that is the shape of the year,
   independent of price level.
3. To get a dollar figure a reader can act on, multiply the mean
   share by an "anchor" annual revenue (mean of 2023-2025). That is
   explicitly a level assumption, not a forecast; it says "in
   recent-year dollars, this window costs about X."

## The three uncertainty metrics, in plain English

Given a candidate window and the 10 historical shares for it (one per
year), we report three complementary numbers:

- **Standard deviation.** Roughly, the typical distance from the
  average across years. Small SD means "the cost of this window
  didn't move much year to year" - i.e., it is consistent.
- **10th-90th percentile range.** Sort the 10 historical costs;
  the range from the 2nd-lowest to the 2nd-highest is the 10-90
  band. This is a robust way to describe "a typical bad year vs. a
  typical good year." The 90th percentile alone (the "P90 cost")
  is a useful downside number: only 1 year in 10 was worse.
- **Bootstrap confidence interval.** With only 10 data points, the
  mean we compute is itself uncertain. Bootstrapping is a resampling
  trick: repeatedly pretend the 10 years are the population, draw 10
  years with replacement, take the mean, do that 2000 times, keep
  the 2.5th and 97.5th percentiles of those means. That range is
  where the true long-run mean plausibly sits. Think of it as a
  Monte Carlo for the sampling error on the mean.

## Guarding against picking noise

There are ~365 possible start dates and heavy overlap between them
(a window starting Sep 15 shares 13 days with one starting Sep 16).
With only ~10 years to average over, the single lowest number on the
curve is almost certainly a lucky one - the equivalent of running 365
A/B tests and reporting the winner without a Bonferroni-style
correction. Mitigations:

- Prefer a broad plateau on the cost curve over a sharp point when
  choosing candidates.
- Enforce non-overlap among the three recommendations so they are
  actually distinct choices.
- Run leave-one-year-out (LOYO) validation: pretend we don't have
  year `y`, pick the best window from the other nine, then score
  that window on year `y`. The gap between the in-sample expected
  cost and the LOYO actual cost is the "optimism" - how much of the
  apparent saving would evaporate in a new year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

WINDOW_DAYS = 14


# ---------------------------------------------------------------------------
# Window enumeration and per-year cost.
# ---------------------------------------------------------------------------


def enumerate_2027_windows() -> pd.DatetimeIndex:
    """Return every valid 14-day window start date in 2027.

    Steps:
      1. Build `pd.date_range("2027-01-01", "2027-12-31", freq="D")`.
      2. Return the whole thing; a window is defined by its start date
         and covers 14 consecutive days. Windows starting in mid- to
         late December wrap into early 2028; downstream code handles
         that by looking up daily revenue for the actual 14-day span.
      3. 2027 is not a leap year, so no Feb 29 (month, day) key exists,
         and every non-leap historical year maps 1-to-1.
    """
    raise NotImplementedError


def _window_dates(start: date, n: int = WINDOW_DAYS) -> list[date]:
    """Return the `n` consecutive dates starting at `start`."""
    raise NotImplementedError


def historical_window_cost(
    daily_revenue: pd.Series,
    start: date,
    year: int,
) -> float:
    """Return the total revenue over the analogue of `start` in a given
    historical year.

    The "analogue" of a 2027 start date `(m, d)` in historical year `y`
    is the window that starts on `y-m-d` and runs 14 consecutive days,
    naturally handling wrap into `y+1` for late-December windows.

    Notes:
      - 2027 has no Feb 29, so `(m, d)` is always a valid date in any
        year.
      - If any date in the 14-day span is missing from `daily_revenue`,
        raise. Silent short-summing is worse than a loud failure.
    """
    raise NotImplementedError


def build_cost_matrix(
    daily_revenue: pd.Series,
    years: list[int],
) -> pd.DataFrame:
    """Build the (start_date x year) matrix of 14-day window costs.

    Steps:
      1. For each `start` in `enumerate_2027_windows()` and each `y` in
         `years`, compute `historical_window_cost(daily_revenue, start, y)`.
      2. Return a DataFrame indexed by 2027 start date (365 rows) with
         one column per year. Values are dollars.

    Rough size: 365 x 10 = 3650 cells; a plain double loop is fast
    enough, no need for a vectorized construction.
    """
    raise NotImplementedError


def annual_revenue(daily_revenue: pd.Series, years: list[int]) -> pd.Series:
    """Return a Series `annual_revenue[y]` = sum of daily_revenue for
    calendar year `y`.

    Assert that each requested year is fully present (365 or 366 daily
    rows).
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Normalization to shares.
# ---------------------------------------------------------------------------


def to_share_matrix(
    cost_matrix: pd.DataFrame,
    annual: pd.Series,
) -> pd.DataFrame:
    """Divide each column of `cost_matrix` by that year's annual revenue.

    Result: same shape as `cost_matrix`, values in ~[0, 0.10] (a 14-day
    window is ~3.8% of a year, so most cells sit near there).
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Point estimate + uncertainty per window.
# ---------------------------------------------------------------------------


@dataclass
class WindowEstimate:
    """Per-window summary of expected cost and uncertainty.

    All dollar fields are already scaled by the 2027 level anchor.
    """

    start: date
    expected_cost: float          # mean(share) * anchor
    sd_cost: float                # std(share, ddof=1) * anchor
    p10_cost: float               # 10th percentile of empirical costs
    p90_cost: float               # 90th percentile of empirical costs
    bootstrap_lo: float           # 2.5th pct of bootstrap mean * anchor
    bootstrap_hi: float           # 97.5th pct of bootstrap mean * anchor
    n_years: int                  # sample size


def summarize_windows(
    share_matrix: pd.DataFrame,
    anchor: float,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> pd.DataFrame:
    """Compute a `WindowEstimate` per row of `share_matrix`.

    Read the module docstring for what each field means. Steps per
    row `w` (a 2027 start date), with the "why" noted:

      1. `s = share_matrix.loc[w].to_numpy()` (length `n_years`).
         These are the ~10 historical costs for this window,
         expressed as fractions of annual revenue.
      2. Expected cost = `s.mean() * anchor`.
         Multiplying by the anchor converts a dimensionless share
         back into recent-year dollars.
      3. SD of cost = `s.std(ddof=1) * anchor`.
         `ddof=1` is the sample SD (divide by n-1). It is the right
         choice when treating the 10 years as a *sample* of possible
         years rather than the entire population - which is what we
         are doing when we use it as a proxy for future years.
      4. P10, P90 = `np.quantile(s * anchor, [0.10, 0.90])`.
         Empirical 10th and 90th percentile - the "usual bad" and
         "usual good" year in the sample.
      5. Bootstrap 95% CI on the mean.
         Draw `n_bootstrap` samples of size `n_years` from `s`
         with replacement, take the mean of each sample, and return
         the 2.5th and 97.5th percentiles of that distribution of
         means times `anchor`. Use `np.random.default_rng(seed)` so
         the result is exactly reproducible. This is the honest
         answer to "how much does our small sample size hurt our
         estimate of the mean?".
      6. Assemble into a `WindowEstimate` and collect into a DataFrame
         indexed by start date.
    """
    raise NotImplementedError


def level_anchor(annual: pd.Series, anchor_years: list[int]) -> float:
    """Return the mean of `annual` over `anchor_years`.

    This is the "recent dollars" scale that converts window shares to
    dollar figures. Default choice for this project: [2023, 2024, 2025].
    Kept as a parameter so sensitivity to the anchor is easy to run.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Candidate selection and out-of-sample check.
# ---------------------------------------------------------------------------


def pick_candidate_windows(
    summary: pd.DataFrame,
    n: int = 3,
    min_gap_days: int = 14,
    rank_by: str = "expected_cost",
) -> pd.DataFrame:
    """Pick `n` non-overlapping candidate windows near distinct local
    minima on the chosen cost curve.

    ## The "consistently low" nuance

    The problem statement asks for a window whose lost revenue is
    *consistently* low. That word admits two reasonable rankings:

      - `rank_by="expected_cost"` (the mean-across-years cost). This
        answers "what will it cost, on average?"
      - `rank_by="p90_cost"` (the 90th-percentile cost). This answers
        "what will it cost in a typical bad year?" - a risk-averse
        reading, appropriate if the downside matters more than the
        mean.

    Recommended presentation: return three candidates using
    `rank_by="expected_cost"` (the primary answer), and separately
    rerun this function with `rank_by="p90_cost"` to surface a
    downside-focused alternative. If the two lists overlap, the
    winner is robust. If they diverge, that itself is useful
    information for the reviewer.

    ## Algorithm

      1. Optionally smooth `summary[rank_by]` with a 7-day centered
         rolling mean so we are picking from a broad low region
         rather than a single noisy point. This is the analog of
         asking "where is the bottom of the bathtub?" instead of
         "which single point is lowest?".
      2. Sort start dates by smoothed rank score ascending.
      3. Greedily accept the top candidate, then skip any candidate
         whose start date is within `min_gap_days` of an already
         accepted candidate. Continue until `n` are accepted.
      4. Return those rows of `summary` (with original unsmoothed
         values) in ascending order of the rank score.

    `min_gap_days=14` makes the accepted candidates fully
    non-overlapping outage options; you might allow `min_gap_days=7`
    to expose two adjacent options if you want to show sensitivity to
    the exact start date.
    """
    raise NotImplementedError


def leave_one_year_out_check(
    share_matrix: pd.DataFrame,
    anchor: float,
) -> pd.DataFrame:
    """For each year `y_held`:

      1. Compute the best window (min mean-share) using only years
         `!= y_held`.
      2. Score that window's actual cost in `y_held` (share * anchor).
      3. Compute the "true best" cost in `y_held` (min share over all
         windows * anchor) and the "in-sample optimism"
         `= (out-of-sample cost - full-sample expected cost)`.

    Return a DataFrame indexed by `y_held` with columns
    `chosen_start`, `oos_cost`, `oos_best_cost`, `optimism`.

    Reading it: if `optimism` is consistently a small fraction of
    `expected_cost`, the recommendation is robust; if it's a large
    fraction, disclose that.
    """
    raise NotImplementedError
