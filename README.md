# Flambeau Outage Timing Analysis

## Objective
Recommend the best 2-week window in 2027 for a planned Flambeau hydro
outage, based on historical opportunity cost (lost generation revenue).

## Data Sources
- `flambeau_gen.csv` — provided, Flambeau generation in MW, ~4-day
  cadence, some missing values
- MISO Day-Ahead ExPost LMP reports (public), 2016–2025:
  - 2016-01 through 2022-12: monthly zip archives
  - 2023-01-01 through 2025-12-31: daily CSVs
  - Filtered to Node == DPC.FLAMBEAU, Value == LMP
  - All hours reported in fixed EST (no DST adjustment)

## Data Collection
`scripts/download_lmp.py` downloads and caches all files locally,
skipping any already present (safe to re-run).

## Data Preparation
[TODO: describe load_flambeau_lmp — melt HE 1..HE 24 into long
(timestamp, LMP) rows, one row per hour]

## Merge Strategy
[TODO: once decided — how hourly LMP reconciles with ~4-day generation]

## Exploratory Findings
[TODO: what the seasonality/revenue patterns showed]

## Recommendation
[TODO: final 3 windows, revenue estimates, uncertainty]

## Assumptions & Limitations
[TODO: annual seasonality assumption, year range chosen, etc.]