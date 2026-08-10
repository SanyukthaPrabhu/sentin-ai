"""
download_nasa_power.py
======================
One-shot script to download all 6 required weather features for Sentin-AI
from the NASA POWER REST API.

Parameters downloaded (Jan 2023 â€“ Dec 2024, Bengaluru):
  T2M           â€” Temperature at 2 Meters (Â°C)
  RH2M          â€” Relative Humidity at 2 Meters (%)
  IMERG_PRECTOT â€” Total Precipitation (mm/day)
  T2MDEW        â€” Dew/Frost Point at 2 Meters (Â°C)
  WS10M         â€” Wind Speed at 10 Meters (m/s)
  ALLSKY_KT     â€” All Sky Insolation Clearness Index (unitless)

Output:
  data/weather_cache/nasa_power_full.csv

Usage:
  python scripts/download_nasa_power.py
  python scripts/download_nasa_power.py --lat 12.9767 --lon 77.5753 --start 20230101 --end 20241231
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "weather_cache"
OUT_CSV = OUT_DIR / "nasa_power_full.csv"

# NASA POWER API endpoint
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# The 6 features the LSTM weather block uses
# PRECTOTCORR = bias-corrected total precipitation (available in all communities)
# IMERG_PRECTOT is only in SB community and returns -999 for RE community
PARAMETERS = "T2M,RH2M,PRECTOTCORR,T2MDEW,WS10M,ALLSKY_KT"

# Bengaluru centre coordinates
DEFAULT_LAT   = 12.9767
DEFAULT_LON   = 77.5753
DEFAULT_START = "20230101"
DEFAULT_END   = "20241231"


def download(lat: float, lon: float, start: str, end: str) -> str:
    """
    Call NASA POWER API and return the raw CSV text.
    Retries up to 3 times on transient errors.
    """
    try:
        import urllib.request
        import urllib.parse
    except ImportError:
        raise RuntimeError("urllib not available â€” this is a standard library module.")

    params = urllib.parse.urlencode({
        "parameters": PARAMETERS,
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "start":      start,
        "end":        end,
        "format":     "CSV",
    })
    url = f"{NASA_POWER_URL}?{params}"
    print(f"[NASA POWER] Requesting: {url[:120]}...")

    last_err = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            print(f"[NASA POWER] Download successful ({len(raw):,} bytes).")
            return raw
        except Exception as e:
            last_err = e
            print(f"[NASA POWER] Attempt {attempt}/3 failed: {e}. Retrying in 5s...")
            time.sleep(5)

    raise RuntimeError(f"NASA POWER download failed after 3 attempts: {last_err}")


def save(raw_csv: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CSV.write_text(raw_csv, encoding="utf-8")
    print(f"[NASA POWER] Saved â†’ {OUT_CSV}")

    # Quick sanity check: count data rows
    lines = [l for l in raw_csv.splitlines() if l.strip() and not l.startswith("-") and not l.startswith("NA")]
    # Find header line
    header_line = None
    data_lines  = 0
    for line in lines:
        if "T2M" in line and "RH2M" in line:
            header_line = line
        elif header_line and line[0].isdigit():
            data_lines += 1
    print(f"[NASA POWER] Header: {header_line}")
    print(f"[NASA POWER] Data rows: {data_lines} (expect ~730 for 2 years)")
    if data_lines < 700:
        print("[WARN] Fewer rows than expected â€” check the downloaded file manually.")


def main():
    parser = argparse.ArgumentParser(description="Download NASA POWER weather data for Sentin-AI")
    parser.add_argument("--lat",   type=float, default=DEFAULT_LAT,   help="Latitude (default: Bengaluru)")
    parser.add_argument("--lon",   type=float, default=DEFAULT_LON,   help="Longitude (default: Bengaluru)")
    parser.add_argument("--start", type=str,   default=DEFAULT_START, help="Start date YYYYMMDD (default: 20230101)")
    parser.add_argument("--end",   type=str,   default=DEFAULT_END,   help="End date YYYYMMDD (default: 20241231)")
    args = parser.parse_args()

    print("=" * 60)
    print(" Sentin-AI | NASA POWER 6-Feature Download")
    print("=" * 60)
    print(f"  Location : lat={args.lat}, lon={args.lon}")
    print(f"  Period   : {args.start} -> {args.end}")
    print(f"  Features : {PARAMETERS}")
    print(f"  Output   : {OUT_CSV}")
    print("=" * 60)

    raw = download(args.lat, args.lon, args.start, args.end)
    save(raw)

    print("\nâœ… Done. Next step:")
    print("   python src/nasa_power_parser.py --csv data/weather_cache/nasa_power_full.csv")


if __name__ == "__main__":
    main()
