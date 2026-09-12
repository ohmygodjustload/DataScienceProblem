# Ticket: Flambeau Outage Timing Analysis (Dairyland Take-Home)

## Objective
Recommend the best 2-week window in 2027 for a planned Flambeau hydro
plant maintenance outage — "best" means lowest opportunity cost
(lost generation revenue).

## Background
- DPC is a MISO member. LMP ($/MWh) is the price paid per MW generated
  at a specific grid node, and it varies by time and location.
- Flambeau revenue for any hour = MW produced × LMP for that hour.
- During the outage, Flambeau produces 0 MW, so the "cost" of the
  outage is the revenue it would have earned had it stayed online.
- Assume no operational/weather/other constraints — any 2-week window
  in 2027 is eligible.

## Data Sources
- `flambeau_gen.csv` (provided): Flambeau generation in MW, ~4-day
  cadence, contains missing values.
- MISO Day-Ahead Market ExPost LMP reports (public):
  - Daily CSVs, Jan 1 2023–present: `YYYYMMDD_da_expost_lmp.csv`
  - Monthly zip archives, Feb 2015–: `YYYYMM_da_expost_lmp_csv.zip`
    (each contains daily CSVs in the same format)
  - Within each daily file: filter to the row where node =
    `DPC.Flambeau` and value = `LMP`. Hourly columns are hour-ending
    labeled (`HE 1`...`HE 24`) — HE 14 = the 1–2pm price.

## Data Acquisition Constraint (IMPORTANT)
- No scraping or parsing of the MISO report-listing pages for links.
- File names follow a fully documented, predictable convention (see
  above) — acquisition should be limited to constructing/requesting
  those known file paths directly for a chosen date range, nothing
  beyond what's explicitly described in this ticket.
- Choose and document a reasonable year range for the analysis; the
  ticket does not mandate a specific number of years.

## Acceptance Criteria
1. **Data collection & merge**: Explain how LMP data was collected and
   prepared, and how it was merged with `flambeau_gen.csv` given the
   mismatched time granularity (hourly vs. ~4-day).
2. **EDA**: Summarize what exploratory analysis reveals about
   Flambeau's LMP and generation patterns (e.g. seasonality).
3. **Recommendation**: Provide 3 candidate 2-week outage windows for
   2027, each with an estimated lost-revenue figure and an
   uncertainty estimate.

## Explicitly Out of Scope
- No web scraping / automated link discovery.
- No predictive ML modeling required — this is historical statistical
  estimation (mean/spread across analogous past periods), not a
  forecasting task.

## Deliverable
A ~10-minute presentation (Jupyter Notebook, slides, or PDF) answering
the 3 questions above. Must be understandable to both technical and
non-technical reviewers, with visuals/charts where helpful.

## Constraints
- Individual work. Documentation, textbooks, and AI tools may be used
  for guidance — but the author must be able to explain all
  methodology and code independently afterward.