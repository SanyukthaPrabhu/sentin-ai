"""
phri_engine.py
==============
Step 5 of the Sentin-AI build order.

Responsibilities:
  - Accept weather features + YOLO visual features as input
  - Normalise them into the same (30, 10) window format the LSTM expects
  - Load the trained LSTM and run inference → raw PHRI score
  - Apply confidence adjustment based on data completeness
  - Return a PHRIResult dataclass with score, confidence, and metadata

Two operating modes:
  1. HISTORICAL  — pass a date range, load from weather_features.csv
  2. REAL-TIME   — pass a dict of live weather + YOLO detections

Usage (as a module):
  from phri_engine import PHRIEngine
  engine = PHRIEngine()
  result = engine.score_realtime(weather_dict, yolo_dict)
  print(result.phri_score)     # e.g. 0.73

Usage (CLI — historical mode):
  python src/phri_engine.py --date 2024-08-15
"""

import argparse
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).resolve().parent.parent
WEATHER_DIR  = ROOT / "data" / "weather_cache"
MODEL_PATH   = ROOT / "models" / "lstm_phri.h5"
FEATURES_CSV = WEATHER_DIR / "weather_features.csv"

WINDOW_SIZE  = 30   # days — must match lstm_model.py

# ── Feature order must exactly match lstm_model.py / nasa_power_parser.py ──
LSTM_FEATURES = [
    "temperature_2m_c",
    "relative_humidity_pct",
    "precipitation_imerg_mm",
    "dew_frost_point_c",
    "wind_speed_10m_ms",
    "all_sky_insolation_clearness",
    "stagnant_water_count",
    "stagnant_water_area_px",
    "garbage_count",
    "vegetation_anomaly_score",
]

# Normalization bounds learned from 2023-2024 Bengaluru data
# Update these after running nasa_power_parser on real data
FEATURE_BOUNDS = {
    "temperature_2m_c"           : (15.0, 38.0),
    "relative_humidity_pct"      : (20.0, 100.0),
    "precipitation_imerg_mm"     : (0.0,  80.0),
    "dew_frost_point_c"          : (5.0,  28.0),
    "wind_speed_10m_ms"          : (0.0,  12.0),
    "all_sky_insolation_clearness": (0.0,  1.0),
    "stagnant_water_count"       : (0.0,  50.0),
    "stagnant_water_area_px"     : (0.0,  50000.0),
    "garbage_count"              : (0.0,  30.0),
    "vegetation_anomaly_score"   : (0.0,  1.0),
}


# ── Result dataclass ───────────────────────────────────────────────────────
@dataclass
class PHRIResult:
    phri_score      : float                  # 0.0 – 1.0
    confidence      : float                  # 0.0 – 1.0 (data completeness)
    risk_level      : str                    # LOW / MEDIUM / HIGH / CRITICAL
    visual_complete : bool                   # True if YOLO features were real
    weather_complete: bool                   # True if all weather cols present
    window_end_date : Optional[date] = None  # last day of the 30-day window
    raw_features    : Optional[np.ndarray] = field(default=None, repr=False)

    def __str__(self):
        return (
            f"PHRI={self.phri_score:.3f}  Risk={self.risk_level}  "
            f"Confidence={self.confidence:.2f}  "
            f"Visual={'✅' if self.visual_complete else '⚠ placeholder'}  "
            f"Date={self.window_end_date}"
        )


# ── Risk level thresholds ──────────────────────────────────────────────────
def _risk_level(score: float) -> str:
    if score < 0.40: return "LOW"
    if score < 0.60: return "MEDIUM"
    if score < 0.75: return "HIGH"
    return "CRITICAL"


# ── Normalizer ─────────────────────────────────────────────────────────────
def _normalize(value: float, feat_name: str) -> float:
    lo, hi = FEATURE_BOUNDS[feat_name]
    if hi == lo:
        return 0.0
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def _normalize_window(window: np.ndarray) -> np.ndarray:
    """
    Normalize a (30, 10) raw feature window column-by-column
    using FEATURE_BOUNDS.
    """
    out = window.copy().astype(np.float32)
    for j, feat in enumerate(LSTM_FEATURES):
        lo, hi = FEATURE_BOUNDS[feat]
        rng = hi - lo if (hi - lo) != 0 else 1.0
        out[:, j] = np.clip((out[:, j] - lo) / rng, 0.0, 1.0)
    return out


# ── Main engine class ──────────────────────────────────────────────────────
class PHRIEngine:
    """
    Loads the trained LSTM once and exposes two scoring methods:
      .score_historical(target_date)  — from saved weather_features.csv
      .score_realtime(weather, yolo)  — from live API dicts
    """

    def __init__(self, model_path: Path = MODEL_PATH):
        self._model      = None
        self._model_path = model_path
        self._df_hist    = None   # lazy-loaded historical features

    # ── Model loader (lazy) ────────────────────────────────────────────────
    def _load_model(self):
        if self._model is not None:
            return
        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found: {self._model_path}\n"
                "Run Step 4 first:  python src/lstm_model.py"
            )
        import tensorflow as tf
        self._model = tf.keras.models.load_model(str(self._model_path))
        print(f"[PHRIEngine] Model loaded from {self._model_path.name}")

    # ── Historical features loader (lazy) ──────────────────────────────────
    def _load_history(self):
        if self._df_hist is not None:
            return
        if not FEATURES_CSV.exists():
            raise FileNotFoundError(
                f"{FEATURES_CSV} not found.\n"
                "Run Step 1 first:  python src/nasa_power_parser.py"
            )
        self._df_hist = pd.read_csv(FEATURES_CSV, index_col=0, parse_dates=True)
        print(f"[PHRIEngine] Historical features loaded: "
              f"{self._df_hist.index[0].date()} → {self._df_hist.index[-1].date()}")

    # ── Inference (shared) ─────────────────────────────────────────────────
    def _infer(self, window_raw: np.ndarray) -> float:
        """
        window_raw : (30, 10) unnormalized feature array.
        Returns     : PHRI score float ∈ [0, 1].
        """
        self._load_model()
        window_norm = _normalize_window(window_raw)
        X = window_norm[np.newaxis, :, :]          # (1, 30, 10)
        score = float(self._model.predict(X, verbose=0)[0, 0])
        return round(score, 4)

    # ── Mode 1: Historical scoring ─────────────────────────────────────────
    def score_historical(self, target_date: date) -> PHRIResult:
        """
        Score a past date using the saved weather_features.csv.
        The 30-day window ends on target_date.
        YOLO visual features will be placeholder zeros unless
        gee_pipeline + yolo_inference have been run (Phase 4).
        """
        self._load_history()
        df = self._df_hist

        end_ts   = pd.Timestamp(target_date)
        start_ts = end_ts - pd.Timedelta(days=WINDOW_SIZE - 1)

        if start_ts < df.index[0]:
            raise ValueError(
                f"Not enough history before {target_date}. "
                f"Earliest available: {df.index[0].date() + timedelta(days=WINDOW_SIZE)}"
            )
        if end_ts > df.index[-1]:
            raise ValueError(
                f"{target_date} is beyond available data ({df.index[-1].date()})."
            )

        window_df = df.loc[start_ts:end_ts, LSTM_FEATURES]
        if len(window_df) < WINDOW_SIZE:
            raise ValueError(f"Window has only {len(window_df)} days (need {WINDOW_SIZE}).")

        window_raw = window_df.values[-WINDOW_SIZE:].astype(np.float32)

        # Check if visual features are real or placeholder
        visual_complete   = bool(window_raw[:, 6:].sum() > 0)
        weather_complete  = True   # from CSV, assumed complete after Step 1

        # Confidence penalty if YOLO not yet wired
        confidence = 1.0 if visual_complete else 0.70

        score = self._infer(window_raw)

        return PHRIResult(
            phri_score       = score,
            confidence       = confidence,
            risk_level       = _risk_level(score),
            visual_complete  = visual_complete,
            weather_complete = weather_complete,
            window_end_date  = target_date,
            raw_features     = window_raw,
        )

    # ── Mode 2: Real-time scoring ──────────────────────────────────────────
    def score_realtime(self,
                       weather: dict,
                       yolo: Optional[dict] = None) -> PHRIResult:
        """
        Score using live data dicts.

        weather (required) — keys map to LSTM weather features:
          {
            "temperature_2m_c"            : float,   # today's value
            "relative_humidity_pct"       : float,
            "precipitation_imerg_mm"      : float,
            "dew_frost_point_c"           : float,
            "wind_speed_10m_ms"           : float,
            "all_sky_insolation_clearness": float,
          }

        yolo (optional) — from yolo_inference.py output:
          {
            "stagnant_water_count"   : int,
            "stagnant_water_area_px" : float,
            "garbage_count"          : int,
            "vegetation_anomaly_score": float,
          }

        The window is built by appending today's live row to the last
        29 days from weather_features.csv, then running inference.
        """
        self._load_history()

        # Build today's feature row
        today_row = np.zeros(10, dtype=np.float32)
        weather_cols = LSTM_FEATURES[:6]
        for j, col in enumerate(weather_cols):
            today_row[j] = float(weather.get(col, 0.0))

        visual_complete = yolo is not None and any(
            v > 0 for v in yolo.values()
        ) if yolo else False

        if yolo:
            today_row[6]  = float(yolo.get("stagnant_water_count", 0))
            today_row[7]  = float(yolo.get("stagnant_water_area_px", 0))
            today_row[8]  = float(yolo.get("garbage_count", 0))
            today_row[9]  = float(yolo.get("vegetation_anomaly_score", 0))

        # Pull last 29 days from history
        df = self._df_hist
        past_29 = df.iloc[-29:][LSTM_FEATURES].values.astype(np.float32)

        # Stack: (29, 10) history + (1, 10) today = (30, 10)
        window_raw = np.vstack([past_29, today_row[np.newaxis, :]])

        weather_keys   = set(weather.keys())
        required_keys  = set(weather_cols)
        missing        = required_keys - weather_keys
        weather_complete = len(missing) == 0
        if missing:
            print(f"[PHRIEngine] ⚠  Missing weather keys: {missing} — using 0.0")

        confidence = 1.0 if (visual_complete and weather_complete) else \
                     0.85 if weather_complete else 0.60

        score = self._infer(window_raw)

        return PHRIResult(
            phri_score       = score,
            confidence       = confidence,
            risk_level       = _risk_level(score),
            visual_complete  = visual_complete,
            weather_complete = weather_complete,
            window_end_date  = date.today(),
            raw_features     = window_raw,
        )


# ── CLI ────────────────────────────────────────────────────────────────────
def run_cli(target_date_str: str):
    engine = PHRIEngine()
    target = date.fromisoformat(target_date_str)
    print(f"\nScoring historical date: {target}")
    result = engine.score_historical(target)
    print(f"\n{'='*50}")
    print(f"  {result}")
    print(f"{'='*50}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentin-AI PHRI Engine")
    parser.add_argument(
        "--date", type=str,
        default=str(date.today() - timedelta(days=1)),
        help="Target date for historical scoring (YYYY-MM-DD)"
    )
    args = parser.parse_args()
    run_cli(args.date)