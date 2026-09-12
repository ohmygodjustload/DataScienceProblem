# Flambeau Outage Timing Analysis

Recommend the best 2-week window in 2027 for a planned Flambeau hydro
plant maintenance outage, where "best" means lowest opportunity cost
(lost generation revenue = MW that would have been produced * LMP for
that hour).

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate      # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter lab
```

Then run the notebooks in order:

1. `notebooks/01_acquisition.ipynb` - download MISO LMPs (slow, ~30-60 min
   first time; cached to `data/processed/lmp_hourly.parquet` afterward).
2. `notebooks/02_eda.ipynb` - exploratory data analysis of LMP and
   generation.
3. `notebooks/03_windows.ipynb` - enumerate 2-week windows, rank by
   expected lost revenue with uncertainty, and produce the 3 candidate
   recommendations.

The presentation deliverable is `deliverable/flambeau_outage_timing.ipynb`.

## Methodology (short version)

### Data sources

- `data/raw/flambeau_gen.csv` (provided): Flambeau generation in MW,
  ~4-day cadence, timestamped in UTC.
- MISO Day-Ahead Market ExPost LMP reports (public, anonymous HTTP):
  - Monthly zips 2016-01 through 2022-12: `YYYYMM_da_expost_lmp_csv.zip`
  - Daily CSVs 2023-01-01 onward: `YYYYMMDD_da_expost_lmp.csv`
  - Within each daily CSV, we keep the row where
    `Node == "DPC.FLAMBEAU"` and `Value == "LMP"`.
  - Hours are labeled hour-ending in fixed **Eastern Standard Time
    year-round** (no DST). See `## Assumptions` below.

Acquisition constructs those known file paths directly from the
documented convention; there is no scraping of any listing page.

### Year range

- **Primary analysis: 2016-2025 (10 complete calendar years).** The
  2015 slice of `flambeau_gen.csv` is entirely `undefined`. 2026 stops
  on 2026-07-29, which would give windows in Jan-Jul 11 samples and
  windows in Aug-Dec only 10, silently biasing the window comparison,
  so 2026 is used only for the price/output level anchor and as an
  out-of-sample check.

### Merging mismatched granularity

- Each 4-day generation sample is expanded to hourly via time-based
  linear interpolation. Justification: hydro output tracks river flow,
  which moves on multi-day timescales, so linear interpolation between
  4-day samples is physically more defensible than a step function. A
  forward-fill sensitivity check is included; because a 14-day sum is
  approximately (mean MW) * (sum of LMPs), window-level answers should
  barely move.
- Hourly revenue: `MW * LMP` (1-hour intervals => MW * $/MWh = $).
- Daily revenue is keyed by local Central calendar date, so any 14-day
  outage window is a `.rolling(14).sum()` on the daily series.

### Handling price-level drift (2022 fuel spike, inflation)

- Rank windows on their **share of annual revenue**, not raw dollars.
  This removes fuel-price inflation and any multi-year hydrology
  trend.
- Convert winning shares to dollars using a recent-years level anchor:
  the mean annual revenue over 2023-2025. This is explicitly *not* a
  forecast - it is a "recent-year dollars" figure so the reader has an
  interpretable magnitude.

### What "best" means, and how we quantify uncertainty

The problem statement asks for a window where lost revenue is
"consistently low." That is two criteria in one word:

1. **Low on average** across the years we have data for.
2. **Not too volatile** year to year - a window whose historical
   cost swings widely isn't "consistent," even if its mean is small.

For each candidate window we report both, using four numbers per
window. Read left to right, they answer four different questions.

- **Expected cost** = mean of the 10 historical costs, scaled to
  recent-year dollars. Answers *"what will this typically cost?"*
- **Standard deviation** (sample SD, dividing by n-1). Roughly, the
  typical distance a year's cost sat from the mean. A small SD means
  "this window's cost didn't move much year to year." Answers
  *"how consistent is it?"*
- **10th-90th percentile range**. Sort the 10 historical costs; take
  the values at rank 1 and rank 9. This is a robust "usual good year
  to usual bad year" band that doesn't get pulled around by a single
  outlier the way SD does. The 90th percentile alone (the "P90 cost")
  is the useful downside number: *only one year in ten was worse.*
- **Bootstrap 95% CI on the mean**. With only ~10 samples per window,
  the mean itself is uncertain. Bootstrapping is a Monte Carlo:
  resample 10 years with replacement, take the mean, do that 2000
  times, keep the middle 95% of those means. That range is where the
  true long-run mean plausibly sits. Answers *"how much am I hurt by
  having only 10 years of data?"*

We present three recommended windows. At least one is chosen by
minimum P90 (a downside-focused pick) so the interviewer sees the
tradeoff between "lowest average" and "lowest bad-year."

### Guard against picking noise

- ~365 heavily overlapping candidate windows, only ~10 historical
  years, so the raw argmin is optimistically biased.
- Mitigations: identify a low *plateau* on the cost-vs-start-date
  curve rather than a single point; the 3 recommendations are chosen
  as non-overlapping alternatives near distinct local minima; and
  leave-one-year-out validation is reported so the reader can see how
  much of the apparent saving survives out-of-sample.

## Assumptions

- **Hour labeling.** MISO market reports state at the top of every
  file that "All Hours-Ending are Eastern Standard Time (EST)". This
  is a fixed UTC-5 offset year-round - not `America/New_York` - so DST
  transition days have exactly 24 hourly columns and no fall-back
  duplicate hour. `HE h` covers the wall-clock interval `[h-1, h)`
  EST, i.e. UTC start `= file_date + (h - 1) hours + 5 hours`.
- **No operational, weather, or other constraints on window choice.**
  Per the ticket, any 2-week window in 2027 is eligible.
- **Flat within-day MW profile from interpolation.** If Flambeau
  shapes its output toward high-price hours, our estimate
  *understates* revenue (and therefore lost revenue). The direction of
  this bias is known even though its magnitude is not.
- **Opportunity cost is energy-market revenue only.** Capacity
  payments, RECs, and ancillary-service revenue are out of scope.
- **Negative-price hours correctly reduce cost.** Under the ticket's
  definition, being offline during a negative-LMP hour is a saving,
  not a loss; the estimator handles this naturally by summing signed
  revenue.

## Repo layout

```
requirements.txt           - pinned Python dependencies
data/raw/flambeau_gen.csv  - provided generation data (in repo)
data/raw/miso/             - downloaded MISO files (git-ignored)
data/processed/            - parquet cache of extracted rows (git-ignored)
src/miso_lmp.py            - MISO LMP acquisition and hourly reshape
src/gen.py                 - generation loading, interpolation, revenue
src/windows.py             - window enumeration, ranking, uncertainty
notebooks/01_acquisition.ipynb
notebooks/02_eda.ipynb
notebooks/03_windows.ipynb
deliverable/flambeau_outage_timing.ipynb - final 10-min presentation
```
