"""Download MISO Day-Ahead ExPost LMP files for 2016-01 through 2025-12."""
import requests
import zipfile
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "lmp"
BASE_URL = "https://docs.misoenergy.org/marketreports"

ZIP_ERA_END = (2022, 12)  # last year/month that has a zip file (12/2022)
DAILY_START = date(2023, 1, 1) # first date that has daily CSVs instead of zip files (1/1/2023)
DAILY_END = date(2025, 12, 31) # last date that has daily CSVs instead of zip files (chose last day of 2025 to round out the year) (31/12/2025)

HEADERS = {"User-Agent": "flambeau-outage-analysis (educational use only)"}

def zip_url(year: int, month: int) -> str:
    return f"{BASE_URL}/{year}{month:02d}_da_expost_lmp_csv.zip"

def day_url(d: date) -> str:
    return f"{BASE_URL}/{d.strftime('%Y%m%d')}_da_expost_lmp.csv"

def fetch_to_disk(session: requests.Session, url: str) -> None:
    local = CACHE_DIR / url.rsplit("/", 1)[-1]
    if local.exists():
        print(f"skip {local.name}")
        return

    resp = session.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    local.write_bytes(resp.content)
    print(f"got {local.name} ({len(resp.content):,} bytes)")

    if local.suffix == ".zip":
        with zipfile.ZipFile(local) as z:
            z.extractall(CACHE_DIR)
        print(f"extracted {local.name} to {CACHE_DIR}")

def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    for year in range(2016, ZIP_ERA_END[0] + 1):
        for month in range(1, 13):
            if (year, month) > ZIP_ERA_END:
                continue
            fetch_to_disk(session, zip_url(year, month))

    d = DAILY_START
    while d <= DAILY_END:
        fetch_to_disk(session, day_url(d))
        d += timedelta(days=1)

if __name__ == "__main__":
    main()