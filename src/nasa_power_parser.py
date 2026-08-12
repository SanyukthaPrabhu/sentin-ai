"""
nasa_power_parser.py
====================
Step 1 of the Sentin-AI build order.

Responsibilities:
  - Load the NASA POWER CSV downloaded for Bengaluru (2023-2024)
  - Clean and validate all 10 feature columns
  - Engineer derived features (rolling stats, lag features)
  - Build 30-day sliding window sequences ready for LSTM input
  - Save:
      data/weather_cache/weather_features.csv   <- cleaned daily rows
      data/weather_cache/lstm_sequences.npy     <- (N, 30, 10) array
      data/weather_cache/lstm_labels.npy        <- (N,) placeholder labels

Usage:
  python src/nasa_power_parser.py
  python src/nasa_power_parser.py --csv data/weather_cache/YOUR_FILE.csv
"""

import argparse
import os
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
WEATHER_DIR = ROOT / "data" / "weather_cache"
OUT_CSV     = WEATHER_DIR / "weather_features.csv"
OUT_SEQ     = WEATHER_DIR / "lstm_sequences.npy"
OUT_LABELS  = WEATHER_DIR / "lstm_labels.npy"

# ── NASA POWER column names -> our internal names ───────────────────────────
# Adjust left-hand keys if your downloaded CSV uses different headers.
COLUMN_MAP = {
    "T2M"          : "temperature_2m_c",
    "T2M_MAX"      : "temp_max_c",
    "T2M_MIN"      : "temp_min_c",
    "RH2M"         : "relative_humidity_pct",
    "PRECTOTCORR"  : "precipitation_imerg_mm",
    "IMERG_PRECTOT": "precipitation_imerg_mm",   # alternate NASA POWER export name
    "T2MDEW"       : "dew_frost_point_c",
    "QV2M"         : "specific_humidity_kgkg",   # reserve feature
    "WS10M"        : "wind_speed_10m_ms",
    "PS"           : "surface_pressure_kpa",      # reserve feature
    "ALLSKY_KT"    : "all_sky_insolation_clearness",
}

# The 10 features the LSTM actually uses (matches README Section 2 table)
LSTM_FEATURES = [
    "temperature_2m_c",
    "relative_humidity_pct",
    "precipitation_imerg_mm",
    "dew_frost_point_c",
    "wind_speed_10m_ms",
    "all_sky_insolation_clearness",
    # 4 visual slots — filled with 0.0 until YOLO is wired in
    "stagnant_water_count",
    "stagnant_water_area_px",
    "garbage_count",
    "vegetation_anomaly_score",
]

WINDOW_SIZE = 30   # days per LSTM input sequence
HORIZON     = 14   # days ahead to look for outbreak label

# IDSP weekly labels ground truth
IDSP_LABELS_CSV = ROOT / "data" / "idsp_bulletins" / "parsed" / "weekly_labels.csv"


# ── 1. Loader ──────────────────────────────────────────────────────────────
def load_nasa_power_csv(csv_path: Path) -> pd.DataFrame:
    """
    NASA POWER CSVs have a multi-line header before the actual data.
    Data rows start after the line beginning with '-END HEADER-'.
    Handles both comma and whitespace delimiters.
    """
    print(f"[1/5] Loading  {csv_path.name} ...")

    with open(csv_path, "r") as f:
        lines = f.readlines()

    # Find data start
    start = 0
    for i, line in enumerate(lines):
        if "-END HEADER-" in line:
            start = i + 1
            break

    if start == 0:
        # No header block — assume pure CSV from row 0
        df = pd.read_csv(csv_path)
    else:
        from io import StringIO
        data_block = "".join(lines[start:])
        # Try comma first, then whitespace
        try:
            df = pd.read_csv(StringIO(data_block))
            if df.shape[1] < 3:
                raise ValueError
        except Exception:
            df = pd.read_csv(StringIO(data_block), delim_whitespace=True)

    print(f"    Raw shape: {df.shape}  |  Columns: {list(df.columns)}")
    return df


# ── 2. Cleaner ─────────────────────────────────────────────────────────────
def clean_and_rename(df: pd.DataFrame) -> pd.DataFrame:
    """Rename NASA columns, build date index, handle missing values (-999)."""
    print("[2/5] Cleaning and renaming columns ...")

    # Rename known columns; ignore extras
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Build a proper date column
    # NASA POWER CSV typically has YEAR, MO (month), DY (day) columns
    date_cols_present = all(c in df.columns for c in ["YEAR", "MO", "DY"])
    if date_cols_present:
        df["date"] = pd.to_datetime(
            df[["YEAR", "MO", "DY"]].rename(columns={"YEAR": "year", "MO": "month", "DY": "day"})
        )
        df = df.drop(columns=["YEAR", "MO", "DY"], errors="ignore")
    elif "date" not in df.columns:
        # Fallback: assume rows are sequential days from 2023-01-01
        df["date"] = pd.date_range("2023-01-01", periods=len(df), freq="D")
        print("    [WARN] No date columns found - synthesised from 2023-01-01")

    df = df.set_index("date").sort_index()

    # NASA POWER uses -999 as missing sentinel
    df = df.replace(-999, np.nan)
    df = df.replace(-999.0, np.nan)

    # Report missingness
    missing = df.isnull().sum()
    if missing.any():
        print(f"    Missing values (will forward-fill):\n{missing[missing > 0]}")
    df = df.ffill().bfill()

    print(f"    Clean shape: {df.shape}  |  Date range: {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── 3. Feature engineering ─────────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling statistics and lag features to enrich the weather signal.
    Also add the 4 YOLO visual feature columns (zero-filled placeholders).
    """
    print("[3/5] Engineering features ...")

    # Rolling 7-day stats on precipitation (key outbreak trigger)
    df["precip_7d_sum"]  = df["precipitation_imerg_mm"].rolling(7, min_periods=1).sum()
    df["precip_7d_mean"] = df["precipitation_imerg_mm"].rolling(7, min_periods=1).mean()

    # Lag features: yesterday's humidity and temperature
    df["humidity_lag1"] = df["relative_humidity_pct"].shift(1).bfill()
    df["temp_lag1"]     = df["temperature_2m_c"].shift(1).bfill()

    # Heat-humidity index (simple proxy for mosquito breeding conditions)
    # HHI = T + 0.33 * RH/100 * 6.105 * exp(17.27*T/(237.7+T)) - 4.0
    T   = df["temperature_2m_c"]
    RH  = df["relative_humidity_pct"]
    df["heat_humidity_index"] = T + 0.33 * (RH / 100) * 6.105 * np.exp(17.27 * T / (237.7 + T)) - 4.0

    # Merge YOLO visual features if yolo_features.csv is available
    yolo_csv = ROOT / "data" / "raw_imagery" / "yolo_features.csv"
    if yolo_csv.exists():
        print(f"    [YOLO] Found yolo_features.csv. Merging visual features...")
        try:
            yolo_df = pd.read_csv(yolo_csv)
            yolo_df["date"] = pd.to_datetime(yolo_df["date"])
            yolo_df = yolo_df.set_index("date").sort_index()
            
            # Reindex to match the daily weather index, forward/backward filling nearest date
            yolo_df_aligned = yolo_df.reindex(df.index, method="nearest", limit=15)
            yolo_df_aligned = yolo_df_aligned.fillna(0.0)
            
            for col in ["stagnant_water_count", "stagnant_water_area_px",
                        "garbage_count", "vegetation_anomaly_score"]:
                df[col] = yolo_df_aligned[col]
            print(f"    [YOLO] Merged visual features from {len(yolo_df)} image dates.")
        except Exception as e:
            print(f"    [YOLO] Error merging visual features: {e}. Using zero-filled placeholders.")
            for col in ["stagnant_water_count", "stagnant_water_area_px",
                        "garbage_count", "vegetation_anomaly_score"]:
                df[col] = 0.0
    else:
        print("    [YOLO] yolo_features.csv not found — using zero-filled placeholders.")
        for col in ["stagnant_water_count", "stagnant_water_area_px",
                    "garbage_count", "vegetation_anomaly_score"]:
            df[col] = 0.0

    # Zero-fill any other LSTM feature columns missing from this CSV export
    # (e.g. T2MDEW / WS10M / ALLSKY_KT not included in a 5-column download)
    missing_lstm = [f for f in LSTM_FEATURES if f not in df.columns]
    if missing_lstm:
        print(f"    [WARN] Following LSTM features absent from CSV - zero-filled: {missing_lstm}")
        print("    Tip: re-download from NASA POWER with all required parameters to improve accuracy.")
        for col in missing_lstm:
            df[col] = 0.0

    print(f"    Final columns ({len(df.columns)}): {list(df.columns)}")
    return df


# ── 4. Sequence builder ────────────────────────────────────────────────────
def _load_idsp_outbreak_dates() -> set:
    """
    Load IDSP weekly outbreak records and return a set of all dates
    (as datetime.date objects) that fall within an outbreak week (label==1).
    Used to assign binary labels to the 14-day forward prediction horizon.
    """
    if not IDSP_LABELS_CSV.exists():
        print(f"    [WARN] {IDSP_LABELS_CSV} not found — all labels will be 0.")
        return set()

    df = pd.read_csv(IDSP_LABELS_CSV, parse_dates=["week_start", "week_end"])
    outbreak_dates = set()
    for _, row in df[df["label"] == 1].iterrows():
        # Expand each outbreak week into individual dates
        d = row["week_start"].date()
        while d <= row["week_end"].date():
            outbreak_dates.add(d)
            d += pd.Timedelta(days=1).to_pytimedelta()
    print(f"    [IDSP] Loaded {len(outbreak_dates)} outbreak days from {len(df[df['label']==1])} outbreak weeks.")
    return outbreak_dates


def build_sequences(df: pd.DataFrame, window: int = WINDOW_SIZE, horizon: int = HORIZON):
    """
    Sliding window over LSTM_FEATURES to produce (N, window, 10) array
    with FORWARD-LOOKING labels aligned to IDSP weekly outbreak ground truth.

    For each sample i:
      Input   : days [ i  …  i + window - 1 ]   (30 days of weather + YOLO)
      Horizon : days [ i + window  …  i + window + horizon - 1 ]   (next 14 days)
      Label   : 1 if ANY IDSP outbreak day falls in the horizon, else 0

    This makes the LSTM genuinely predictive:
      "Given the last 30 days of conditions, will an outbreak begin in the next 14 days?"

    The scaler (col_min, col_max) is computed here over the FULL feature matrix
    and saved to models/feature_scaler.npz for consistent inference normalisation.
    NOTE: lstm_model.py re-fits the scaler on TRAIN ONLY before saving — this
    provides a complete-dataset scaler as a fallback for historical scoring.
    """
    print(f"[4/5] Building {window}-day sequences with {horizon}-day forward labels ...")

    # Validate all required LSTM features are present
    missing_feats = [f for f in LSTM_FEATURES if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Missing LSTM feature columns: {missing_feats}")

    feature_matrix = df[LSTM_FEATURES].values.astype(np.float32)
    dates = df.index  # DatetimeIndex

    # ── Compute and save scaler over FULL dataset (pre-split) ────────────────
    # lstm_model.py will re-fit on train split only and overwrite this file.
    col_min   = feature_matrix.min(axis=0)
    col_max   = feature_matrix.max(axis=0)
    feature_matrix_norm = feature_matrix

    # Save scaler (full-dataset version; will be overwritten by train-only scaler later)
    MODELS_DIR = ROOT / "models"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    scaler_path = MODELS_DIR / "feature_scaler.npz"
    np.savez(scaler_path, col_min=col_min, col_max=col_max)
    print(f"    [Scaler] Saved (full-dataset) -> {scaler_path}")
    print(f"    [Scaler] col_min: {col_min.round(3)}")
    print(f"    [Scaler] col_max: {col_max.round(3)}")

    # ── Load IDSP outbreak dates for forward-looking label assignment ───
    outbreak_dates = _load_idsp_outbreak_dates()

    # ── Sliding window over normalised feature matrix ─────────────────
    sequences, labels, alignment_rows = [], [], []

    # Need enough room for window + horizon
    n_total = len(feature_matrix_norm)
    for i in range(n_total - window - horizon + 1):
        seq_start_date    = dates[i].date()
        seq_end_date      = dates[i + window - 1].date()
        horizon_start     = dates[i + window].date()
        horizon_end       = dates[min(i + window + horizon - 1, n_total - 1)].date()

        # Forward-looking label: 1 if any IDSP outbreak day in [horizon_start, horizon_end]
        label = 0
        if outbreak_dates:
            d = horizon_start
            while d <= horizon_end:
                if d in outbreak_dates:
                    label = 1
                    break
                d += pd.Timedelta(days=1).to_pytimedelta()

        sequences.append(feature_matrix_norm[i : i + window])
        labels.append(float(label))
        alignment_rows.append({
            "seq_index":     i,
            "seq_start":     str(seq_start_date),
            "seq_end":       str(seq_end_date),
            "horizon_start": str(horizon_start),
            "horizon_end":   str(horizon_end),
            "label":         label,
        })

    X = np.array(sequences, dtype=np.float32)   # (N, window, 10)
    y = np.array(labels,    dtype=np.float32)   # (N,)

    pos = int(y.sum()); neg = int((y == 0).sum())
    print(f"    Sequences shape: {X.shape}  |  Labels shape: {y.shape}")
    print(f"    Label distribution — Positive: {pos} ({100*y.mean():.1f}%)  Negative: {neg}")
    if outbreak_dates and pos == 0:
        print("    [WARN] No positive labels generated. Check that horizon dates overlap IDSP outbreak weeks.")

    # Save alignment CSV for traceability
    alignment_df = pd.DataFrame(alignment_rows)
    alignment_path = WEATHER_DIR / "label_alignment.csv"
    alignment_df.to_csv(alignment_path, index=False)
    print(f"    [Alignment] Saved -> {alignment_path}")

    return X, y


# ── 5. Save ────────────────────────────────────────────────────────────────
def save_outputs(df: pd.DataFrame, X: np.ndarray, y: np.ndarray):
    print("[5/5] Saving outputs ...")
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV)
    np.save(OUT_SEQ, X)
    np.save(OUT_LABELS, y)
    print(f"    [OK] {OUT_CSV}")
    print(f"    [OK] {OUT_SEQ}  shape={X.shape}")
    print(f"    [OK] {OUT_LABELS}  shape={y.shape}")


# ── Main ───────────────────────────────────────────────────────────────────
def run(csv_path: Path):
    df_raw   = load_nasa_power_csv(csv_path)
    df_clean = clean_and_rename(df_raw)
    df_feat  = engineer_features(df_clean)
    X, y     = build_sequences(df_feat)
    save_outputs(df_feat, X, y)
    print("\nnasa_power_parser.py complete - ready for Step 2 (idsp_parser.py)")
    return df_feat, X, y


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse NASA POWER CSV for Sentin-AI")
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to NASA POWER CSV file (default: first .csv in data/weather_cache/)"
    )
    args = parser.parse_args()

    if args.csv:
        csv_file = Path(args.csv)
    else:
        # Auto-detect: pick first CSV in weather_cache/
        candidates = list(WEATHER_DIR.glob("*.csv"))
        candidates = [c for c in candidates if c.name not in ["weather_features.csv", "label_alignment.csv"]]
        if not candidates:
            raise FileNotFoundError(
                f"No CSV found in {WEATHER_DIR}. "
                "Download from https://power.larc.nasa.gov and place it there, "
                "or pass --csv path/to/file.csv"
            )
        csv_file = candidates[0]
        print(f"Auto-detected: {csv_file.name}")

    run(csv_file)
