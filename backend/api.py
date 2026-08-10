"""
backend/api.py
==============
FastAPI backend for the Sentin-AI React dashboard.
Wraps all Python pipeline modules into clean REST endpoints.

Run:
  uvicorn backend.api:app --reload --port 8000
"""

import sys
import os
import base64
import traceback
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sentin-AI API",
    description="Public Health Early Warning System — FastAPI Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Module loader (cached at startup) ──────────────────────────────────────
_engine = None
_router = None
_voice  = None

def get_modules():
    global _engine, _router, _voice
    if _engine is None:
        from phri_engine    import PHRIEngine
        from disease_router import DiseaseRouter
        from gemini_voice   import GeminiVoice
        _engine = PHRIEngine()
        _router = DiseaseRouter()
        _voice  = GeminiVoice()
    return _engine, _router, _voice


# ── Pydantic request models ──────────────────────────────────────────────────
class LocationConfig(BaseModel):
    lat:           float  = 12.98
    lon:           float  = 77.58
    radius_km:     float  = 5.0
    location_name: str    = "Bengaluru, Karnataka"

class ManualWeather(BaseModel):
    temperature_2m_c:            float = 26.0
    relative_humidity_pct:       float = 72.0
    precipitation_imerg_mm:      float = 8.0
    dew_frost_point_c:           float = 18.0
    wind_speed_10m_ms:           float = 2.5
    all_sky_insolation_clearness: float = 0.5

class ManualYolo(BaseModel):
    stagnant_water_count:    int   = 0
    stagnant_water_area_px:  int   = 0
    garbage_count:           int   = 0
    vegetation_anomaly_score: float = 0.1

class ManualPipelineRequest(BaseModel):
    location:   LocationConfig = LocationConfig()
    weather:    ManualWeather  = ManualWeather()
    yolo:       ManualYolo     = ManualYolo()

class LivePipelineRequest(BaseModel):
    location: LocationConfig = LocationConfig()

class HistoricalRequest(BaseModel):
    location:   LocationConfig = LocationConfig()
    hist_date:  str            = "2024-08-15"   # YYYY-MM-DD

class StressTestRequest(BaseModel):
    disease_bucket: str = "dengue_malaria"


# ── Shared pipeline runner ────────────────────────────────────────────────────
def _encode_image(path_str) -> Optional[str]:
    """Read an image file and return its base64-encoded string, or None."""
    if path_str and Path(path_str).exists():
        with open(path_str, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None


def _run_core_pipeline(phri_result, disease_route, seir_result, bulletin,
                       weather_dict: dict, yolo_dict: dict,
                       location_name: str, live_meta: Optional[dict] = None,
                       rgb_b64: Optional[str] = None,
                       ndwi_b64: Optional[str] = None) -> dict:
    """Serialise pipeline outputs into a JSON-safe dict."""
    from seir_model import DISEASE_PARAMS

    disease_params = DISEASE_PARAMS.get(disease_route.primary_bucket, {})

    return {
        "phri": {
            "score":           round(phri_result.phri_score, 4),
            "risk_level":      phri_result.risk_level,
            "confidence":      round(getattr(phri_result, "confidence", 0.85), 3),
            "visual_complete": getattr(phri_result, "visual_complete", False),
        },
        "disease": {
            "primary_bucket":    disease_route.primary_bucket,
            "label":             disease_route.meta.get("label", "—"),
            "vector":            disease_route.meta.get("vector", "—"),
            "warning_signs":     disease_route.meta.get("warning_signs", "—"),
            "prevention":        disease_route.meta.get("prevention", "—"),
            "incubation_days":   disease_route.meta.get("incubation_days", "—"),
            "secondary_buckets": list(getattr(disease_route, "secondary_buckets", [])),
            "rules_triggered":   list(getattr(disease_route, "rules_triggered", [])),
        },
        "seir": {
            "disease_label":    DISEASE_PARAMS.get(disease_route.primary_bucket, {}).get("label", "—"),
            "peak_cases":       seir_result.peak_cases,
            "peak_day":         seir_result.peak_day,
            "total_projected":  seir_result.total_projected,
            "attack_rate_pct":  round(seir_result.attack_rate_pct, 4),
            "beta_effective":   round(seir_result.beta_effective, 4),
            "projection_days":  seir_result.projection_days,
            "new_cases_curve":  [round(v, 1) for v in seir_result.new_cases_curve[1:]],
            "population":       seir_result.population,
        },
        "bulletin": {
            "headline":        bulletin.headline,
            "health_bulletin": bulletin.health_bulletin,
            "action_items":    list(bulletin.action_items),
            "officer_note":    bulletin.officer_note,
            "fallback_used":   bulletin.fallback_used,
            "generated_date":  str(bulletin.generated_date),
        },
        "weather":       weather_dict,
        "yolo":          yolo_dict,
        "location_name": location_name,
        "live_meta":     live_meta,
        # Per-location satellite images (only present on live runs)
        "rgb_b64":       rgb_b64,
        "ndwi_b64":      ndwi_b64,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Sentin-AI API", "date": str(date.today())}


@app.post("/api/pipeline/manual")
def pipeline_manual(req: ManualPipelineRequest):
    """Run PHRI + SEIR + Groq with user-supplied weather and YOLO values."""
    try:
        engine, router, voice = get_modules()
        from seir_model import SEIRModel

        weather = req.weather.model_dump()
        yolo    = req.yolo.model_dump()
        loc     = req.location

        phri_result   = engine.score_realtime(weather, yolo)
        disease_route = router.classify(phri_result, weather, yolo)
        seir_result   = SEIRModel(
            disease_route.primary_bucket,
            lat=loc.lat, lon=loc.lon, radius_km=loc.radius_km
        ).project(phri_result.phri_score, days=14)
        bulletin = voice.generate(phri_result, disease_route, seir_result,
                                  location=loc.location_name)

        return _run_core_pipeline(
            phri_result, disease_route, seir_result, bulletin,
            weather, yolo, loc.location_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/pipeline/live")
def pipeline_live(req: LivePipelineRequest):
    """Full automated pipeline: live weather + GEE satellite + YOLO + PHRI + Groq."""
    try:
        from realtime_pipeline import run_live_pipeline
        loc = req.location

        res = run_live_pipeline(
            lat=loc.lat,
            lon=loc.lon,
            radius_km=loc.radius_km,
            location_name=loc.location_name,
        )

        phri_result   = res["phri_result"]
        disease_route = res["disease_route"]
        seir_result   = res["seir_result"]
        bulletin      = res["bulletin"]
        live_meta     = res.get("latest_meta", {})
        weather       = res.get("weather", {})
        yolo          = res.get("yolo", {})

        # Encode the per-location satellite images that were freshly downloaded
        # for THIS location — avoids the stale global /api/imagery/latest lookup
        rgb_b64  = _encode_image(live_meta.get("rgb_path"))
        ndwi_b64 = _encode_image(live_meta.get("ndwi_png_path"))

        return _run_core_pipeline(
            phri_result, disease_route, seir_result, bulletin,
            weather, yolo, loc.location_name, live_meta,
            rgb_b64=rgb_b64, ndwi_b64=ndwi_b64
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/pipeline/historical")
def pipeline_historical(req: HistoricalRequest):
    """Score a specific historical date from NASA POWER data."""
    try:
        engine, router, voice = get_modules()
        from seir_model import SEIRModel
        from datetime import datetime
        loc = req.location

        hist_dt = datetime.strptime(req.hist_date, "%Y-%m-%d").date()
        phri_result   = engine.score_historical(hist_dt)
        weather       = {}
        yolo          = {}
        disease_route = router.classify(phri_result, weather, yolo)
        seir_result   = SEIRModel(
            disease_route.primary_bucket,
            lat=loc.lat, lon=loc.lon, radius_km=loc.radius_km
        ).project(phri_result.phri_score, days=14)
        bulletin = voice.generate(phri_result, disease_route, seir_result,
                                  location=loc.location_name)

        return _run_core_pipeline(
            phri_result, disease_route, seir_result, bulletin,
            weather, yolo, loc.location_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/pipeline/stress-test")
def pipeline_stress_test(req: StressTestRequest):
    """Sweep PHRI 0→1 and return SEIR response curves."""
    try:
        from seir_model import SEIRModel, DISEASE_PARAMS

        if req.disease_bucket not in DISEASE_PARAMS:
            raise ValueError(f"Unknown bucket: {req.disease_bucket}")

        model = SEIRModel(req.disease_bucket)
        results = model.stress_test((0.0, 1.0), steps=21, days=14)

        phri_vals = [round(i / 20, 2) for i in range(21)]
        return {
            "disease_bucket": req.disease_bucket,
            "disease_label":  DISEASE_PARAMS[req.disease_bucket]["label"],
            "phri_values":    phri_vals,
            "total_cases":    [r.total_projected for r in results],
            "peak_cases":     [r.peak_cases for r in results],
            "available_buckets": list(DISEASE_PARAMS.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/api/imagery/latest")
def imagery_latest():
    """Return the latest satellite images as base64 strings + metadata."""
    try:
        csv_path = ROOT / "data" / "raw_imagery" / "sentinel2_metadata.csv"
        if not csv_path.exists():
            return {"rgb_b64": None, "ndwi_b64": None, "meta": None}

        df = pd.read_csv(csv_path)
        if df.empty:
            return {"rgb_b64": None, "ndwi_b64": None, "meta": None}

        row = df.iloc[-1]
        meta = row.to_dict()

        def img_to_b64(path_str):
            if path_str and Path(path_str).exists():
                with open(path_str, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            return None

        return {
            "rgb_b64":  img_to_b64(meta.get("rgb_path")),
            "ndwi_b64": img_to_b64(meta.get("ndwi_png_path")),
            "meta": {
                "date":       meta.get("date", "—"),
                "cloud_pct":  meta.get("cloud_pct", "—"),
                "ndwi_mean":  meta.get("ndwi_mean", "—"),
                "ndvi_mean":  meta.get("ndvi_mean", "—"),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def history():
    """Return historical PHRI timeline. Loads from backtest_phri_scores.csv if available, else falls back to proxy."""
    try:
        csv = ROOT / "data" / "weather_cache" / "weather_features.csv"
        if not csv.exists():
            return {"data": [], "is_proxy": True}

        df = pd.read_csv(csv, parse_dates=["date"])

        # Try to load real LSTM backtest scores
        scores_csv = ROOT / "validation" / "backtest_phri_scores.csv"
        real_scores = {}
        is_proxy = True
        if scores_csv.exists():
            try:
                df_scores = pd.read_csv(scores_csv, parse_dates=["seq_end"])
                for _, row in df_scores.iterrows():
                    dt = row["seq_end"].date() if hasattr(row["seq_end"], "date") else row["seq_end"]
                    real_scores[str(dt)] = float(row["phri_score"])
                if real_scores:
                    is_proxy = False
            except Exception as e:
                print(f"[API] Error loading backtest scores: {e}")

        proxy = (
            df["relative_humidity_pct"].clip(0, 100) / 100 * 0.4 +
            df["precipitation_imerg_mm"].clip(0, 80) / 80 * 0.4 +
            df["temperature_2m_c"].clip(15, 38).apply(lambda t: max(0, t - 28) / 10) * 0.2
        ).clip(0, 1)

        result = []
        for i, row in df.iterrows():
            dt_str = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])
            phri_val = real_scores.get(dt_str, float(proxy.iloc[i]))
            result.append({
                "date":  dt_str,
                "phri":  round(phri_val, 4),
                "temp":  round(float(row.get("temperature_2m_c", 0)), 1),
                "rain":  round(float(row.get("precipitation_imerg_mm", 0)), 1),
                "humid": round(float(row.get("relative_humidity_pct", 0)), 1),
            })

        return {"data": result, "is_proxy": is_proxy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
