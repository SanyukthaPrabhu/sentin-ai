"""
realtime_pipeline.py
====================
Sentin-AI Live Automated Real-Time Pipeline.

Workflow:
  1. Fetch live OpenWeatherMap weather for the target location
  2. Fetch the latest Sentinel-2 image from Google Earth Engine (5km ROI)
     — Automatic SAR fallback if Sentinel-2 is unavailable (cloud / no scene)
  3. Run YOLOv8 instance segmentation on the latest scene
     — mask-based pixel area when masks are available, bbox area otherwise
  4. Compute NDWI temporal differencing to quantify new/temporary water bodies
     — NDWI delta -> stagnant_water signal (NOT vegetation_anomaly)
     — NDVI change -> vegetation_anomaly_score (separate feature)
  5. Run LSTM PHRI Engine with the saved train-only scaler
  6. Route PHRI + weather + visual signals to disease bucket
  7. Generate 14-day SEIR case projections
  8. Generate Gemini AI Public Health Bulletin

Usage:
  python src/realtime_pipeline.py
"""

import os
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from live_weather import LiveWeatherFetcher
from gee_pipeline import GEEPipeline, SAR_Pipeline
from yolo_inference import YOLOInference
from phri_engine import PHRIEngine
from disease_router import DiseaseRouter
from seir_model import SEIRModel
from gemini_voice import GeminiVoice


def run_live_pipeline(lat: float = None, lon: float = None,
                      radius_km: float = None, location_name: str = None):
    """Execute full automated real-time pipeline for specified location."""
    import importlib
    import live_weather
    import gee_pipeline
    importlib.reload(live_weather)
    importlib.reload(gee_pipeline)
    from live_weather import LiveWeatherFetcher
    from gee_pipeline import GEEPipeline, SAR_Pipeline

    print("\n" + "=" * 65)
    print(" [SENTIN-AI] Automated Real-Time Pipeline Execution")
    print("=" * 65)

    # ── 1. Live Weather ─────────────────────────────────────────────────────
    print("\n[1/5] Fetching live weather from OpenWeatherMap API...")
    weather_fetcher = (LiveWeatherFetcher(lat=lat, lon=lon)
                       if (lat and lon) else LiveWeatherFetcher())
    weather_dict = weather_fetcher.fetch_current_weather()
    if location_name:
        weather_dict["city_name"] = location_name

    print(f"      Location: {weather_dict['city_name']} | Temp: {weather_dict['temperature_2m_c']}°C | "
          f"Humidity: {weather_dict['relative_humidity_pct']}% | Rain: {weather_dict['precipitation_imerg_mm']}mm")

    # ── 2. Latest GEE Satellite Scene (Sentinel-2, SAR fallback) ────────────
    print(f"\n[2/5] Querying Google Earth Engine for latest Sentinel-2 scene "
          f"({weather_dict['city_name']} {radius_km or 5}km ROI)...")

    gee = (GEEPipeline(lat=lat, lon=lon, radius_km=radius_km)
           if (lat and lon and radius_km) else GEEPipeline())

    sar_activated = False
    latest_meta   = None
    try:
        latest_meta = gee.fetch_latest_image(lookback_days=90, max_cloud=60.0)
        if latest_meta is None:
            raise ValueError("fetch_latest_image returned None (no usable Sentinel-2 scene).")
        latest_meta["source"] = "Sentinel-2"
        print(f"      Scene Date  : {latest_meta['date']} | Cloud: {latest_meta['cloud_pct']}% | "
              f"Mean NDWI: {latest_meta['ndwi_mean']} | Mean NDVI: {latest_meta['ndvi_mean']}")
    except Exception as s2_err:
        # ── Sentinel-2 failed -> automatic SAR fallback ─────────────────────
        print(f"\n      [WARN] Sentinel-2 unavailable: {s2_err}")
        print("      [INFO] SAR fallback activated — switching to Sentinel-1 GRD")
        sar_activated = True
        try:
            sar = SAR_Pipeline()
            from datetime import datetime, timedelta
            today_str = date.today().strftime("%Y-%m-%d")
            past_90   = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
            sar_col   = sar.fetch_sar(past_90, today_str)
            latest_meta = {
                "source":       "Sentinel-1 SAR",
                "date":         today_str,
                "cloud_pct":    0.0,        # SAR penetrates cloud
                "ndwi_mean":    None,
                "ndvi_mean":    None,
                "rgb_path":     None,
                "ndwi_npy_path": None,
            }
            print("      [SAR] Sentinel-1 collection fetched successfully.")
        except Exception as sar_err:
            print(f"      [ERROR] SAR fallback also failed: {sar_err}")
            latest_meta = {
                "source": "unavailable", "date": str(date.today()),
                "cloud_pct": 100.0, "ndwi_mean": None, "ndvi_mean": None,
                "rgb_path": None, "ndwi_npy_path": None,
            }

    # ── 3. YOLO Inference (mask-based segmentation area) ───────────────────
    print("\n[3/5] Running YOLOv8 segmentation on latest satellite image...")
    yolo_dict = {
        "stagnant_water_count": 0,
        "stagnant_water_area_px": 0.0,
        "garbage_count": 0,
        "vegetation_anomaly_score": 0.0,
    }

    rgb_path = None
    if latest_meta.get("rgb_path"):
        rgb_path = Path(latest_meta["rgb_path"])

    if rgb_path and rgb_path.exists():
        yolo = YOLOInference()
        npy_path = (Path(latest_meta["ndwi_npy_path"])
                    if latest_meta.get("ndwi_npy_path") else None)
        yolo_dict = yolo.run_single_image(rgb_path, npy_path,
                                          latest_meta.get("ndvi_mean"))
        results = yolo.model.predict(
            str(rgb_path), conf=yolo.conf, verbose=False, save=False
        )
        mask_used = "mask-area" if (len(results) > 0 and results[0].masks is not None) else "bbox-area"
        print(f"      Visual Features -> Water count: {yolo_dict['stagnant_water_count']} | "
              f"Garbage count: {yolo_dict['garbage_count']} | "
              f"Veg Anomaly: {yolo_dict['vegetation_anomaly_score']} "
              f"[area method: {mask_used}]")
    else:
        print(f"      [SKIP] No RGB image available (source: {latest_meta.get('source')}) — "
              f"using zero-filled visual features.")

    # ── 4a. NDWI Temporal Differencing -> stagnant water signal ─────────────
    # NDWI delta identifies NEW or EXPANDING water bodies (monsoon puddles,
    # blocked drains). It feeds stagnant_water_area_px — NOT vegetation_anomaly.
    if not sar_activated and latest_meta.get("date"):
        print("\n      [NDWI] Computing temporal differencing (new water detection)...")
        try:
            ndwi_result = gee.compute_ndwi_delta(
                current_date=latest_meta["date"], lookback_days=90, max_cloud=60.0
            )
            if ndwi_result.get("new_water_flag"):
                # Scale the NDWI delta [0.05 -> 1.0] into a water area estimate
                # injected as a supplement to YOLO water detection
                ndwi_delta = float(ndwi_result.get("ndwi_delta", 0.0))
                # Augment stagnant_water_area_px: convert normalized delta to
                # a rough pixel-count proxy (delta 0.05->1.0 maps to 0->5000 px)
                extra_water_px = max(0.0, (ndwi_delta - 0.05) / 0.95) * 5000.0
                yolo_dict["stagnant_water_area_px"] += extra_water_px
                print(f"      [NDWI] New water detected (delta={ndwi_delta:+.4f}). "
                      f"Augmented water area by +{extra_water_px:.0f}px.")
            else:
                print(f"      [NDWI] No significant new water "
                      f"(delta={ndwi_result.get('ndwi_delta', 0.0):+.4f}).")
        except Exception as ndwi_err:
            print(f"      [NDWI] Temporal differencing skipped: {ndwi_err}")

    # ── 4b. NDVI-based vegetation anomaly ──────────────────────────────────
    # vegetation_anomaly_score comes from YOLO (custom model) or NDVI delta,
    # NOT from NDWI. Only override if YOLO gave zero and NDVI is available.
    ndvi_mean = latest_meta.get("ndvi_mean")
    if ndvi_mean is not None and yolo_dict["vegetation_anomaly_score"] == 0.0:
        baseline_ndvi = 0.30
        ndvi_anomaly  = max(0.0, baseline_ndvi - float(ndvi_mean)) * 3.0
        ndvi_anomaly  = min(1.0, ndvi_anomaly)
        if ndvi_anomaly > 0.0:
            yolo_dict["vegetation_anomaly_score"] = ndvi_anomaly
            print(f"      [NDVI] Anomaly from GEE NDVI: {ndvi_anomaly:.4f} "
                  f"(NDVI mean={ndvi_mean:.4f}, baseline=0.30)")

    # ── 5. PHRI Score & Analytics ───────────────────────────────────────────
    print("\n[4/5] Computing live PHRI score via trained LSTM model...")
    engine = PHRIEngine()
    phri_result = engine.score_realtime(weather_dict, yolo_dict, lat=lat, lon=lon)
    print(f"      {phri_result}")

    # Log SAR flag in the metadata so the dashboard can show a badge
    if sar_activated:
        print("      [NOTE] PHRI computed without satellite visual features (SAR fallback — no optical imagery).")

    router = DiseaseRouter()
    disease_route = router.classify(phri_result, weather_dict, yolo_dict)
    print(f"      Mapped Disease Bucket: {disease_route.primary_bucket} "
          f"(Risk Level: {disease_route.risk_level})")

    seir = SEIRModel(disease_route.primary_bucket, lat=lat, lon=lon, radius_km=radius_km)
    seir_result = seir.project(phri_result.phri_score, days=14)
    print(f"      14-Day Case Projection: Peak at day {seir_result.peak_day} "
          f"({seir_result.peak_cases} cases)")

    # ── 6. Gemini Voice AI Advisory ─────────────────────────────────────────
    print("\n[5/5] Generating AI Public Health Bulletin via Gemini API...")
    voice = GeminiVoice()
    bulletin = voice.generate(
        phri_result, disease_route, seir_result,
        location=weather_dict.get("city_name", "Target Location")
    )

    print("\n" + "=" * 65)
    print(f"  HEADLINE: {bulletin.headline}")
    print("=" * 65)
    print("\n  PUBLIC ADVISORY:")
    print(bulletin.health_bulletin)
    print("\n  ACTION ITEMS:")
    for action in bulletin.action_items:
        print(f"   - {action}")
    print(f"\n  Data source: {latest_meta.get('source', 'unknown')}")
    print("=" * 65)

    return {
        "weather":       weather_dict,
        "latest_meta":   latest_meta,
        "yolo":          yolo_dict,
        "phri_result":   phri_result,
        "disease_route": disease_route,
        "seir_result":   seir_result,
        "bulletin":      bulletin,
        "sar_activated": sar_activated,
    }


if __name__ == "__main__":
    run_live_pipeline()
