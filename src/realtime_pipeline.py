"""
realtime_pipeline.py
====================
Sentin-AI Live Automated Real-Time Pipeline.

Workflow:
  1. Fetch live OpenWeatherMap weather for Bengaluru
  2. Fetch the latest Sentinel-2 image from Google Earth Engine (5km ROI)
  3. Run YOLOv8 inference & NDWI feature extraction on the latest scene
  4. Run LSTM PHRI Engine to produce current PHRI score
  5. Route PHRI + weather + visual signals to disease bucket
  6. Generate 14-day SEIR case projections
  7. Generate Gemini AI Public Health Bulletin

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
from gee_pipeline import GEEPipeline
from yolo_inference import YOLOInference
from phri_engine import PHRIEngine
from disease_router import DiseaseRouter
from seir_model import SEIRModel
from gemini_voice import GeminiVoice


def run_live_pipeline(lat: float = None, lon: float = None, radius_km: float = None, location_name: str = None):
    """Execute full automated real-time pipeline for specified location."""
    import importlib
    import live_weather
    import gee_pipeline
    importlib.reload(live_weather)
    importlib.reload(gee_pipeline)
    from live_weather import LiveWeatherFetcher
    from gee_pipeline import GEEPipeline

    print("\n" + "=" * 65)
    print(" [SENTIN-AI] Automated Real-Time Pipeline Execution")
    print("=" * 65)

    # 1. Live Weather
    print("\n[1/5] Fetching live weather from OpenWeatherMap API...")
    weather_fetcher = LiveWeatherFetcher(lat=lat, lon=lon) if (lat and lon) else LiveWeatherFetcher()
    weather_dict = weather_fetcher.fetch_current_weather()
    if location_name:
        weather_dict["city_name"] = location_name

    print(f"      Location: {weather_dict['city_name']} | Temp: {weather_dict['temperature_2m_c']}°C | "
          f"Humidity: {weather_dict['relative_humidity_pct']}% | Rain: {weather_dict['precipitation_imerg_mm']}mm")

    # 2. Latest GEE Satellite Scene
    print(f"\n[2/5] Querying Google Earth Engine for latest Sentinel-2 scene ({weather_dict['city_name']} {radius_km or 5}km ROI)...")
    gee = GEEPipeline(lat=lat, lon=lon, radius_km=radius_km) if (lat and lon and radius_km) else GEEPipeline()
    latest_meta = gee.fetch_latest_image(lookback_days=90, max_cloud=60.0)
    print(f"      Scene Date: {latest_meta['date']} | Cloud: {latest_meta['cloud_pct']}% | "
          f"Mean NDWI: {latest_meta['ndwi_mean']} | Mean NDVI: {latest_meta['ndvi_mean']}")

    # 3. Live YOLO Inference
    print("\n[3/5] Running YOLOv8 object detection on latest satellite image...")
    yolo = YOLOInference()
    rgb_path = Path(latest_meta["rgb_path"])
    npy_path = Path(latest_meta["ndwi_npy_path"]) if latest_meta.get("ndwi_npy_path") else None
    yolo_dict = yolo.run_single_image(rgb_path, npy_path, latest_meta.get("ndvi_mean"))
    print(f"      Visual Features -> Water count: {yolo_dict['stagnant_water_count']} | "
          f"Garbage count: {yolo_dict['garbage_count']} | Veg Anomaly: {yolo_dict['vegetation_anomaly_score']}")

    # 4. PHRI Score & Analytics
    print("\n[4/5] Computing live PHRI score via trained LSTM model...")
    engine = PHRIEngine()
    phri_result = engine.score_realtime(weather_dict, yolo_dict)
    print(f"      {phri_result}")

    router = DiseaseRouter()
    disease_route = router.classify(phri_result, weather_dict, yolo_dict)
    print(f"      Mapped Disease Bucket: {disease_route.primary_bucket} (Risk Level: {disease_route.risk_level})")

    seir = SEIRModel(disease_route.primary_bucket, lat=lat, lon=lon, radius_km=radius_km)
    seir_result = seir.project(phri_result.phri_score, days=14)
    print(f"      14-Day Case Projection: Peak at day {seir_result.peak_day} ({seir_result.peak_cases} cases)")

    # 5. Gemini Voice AI Advisory
    print("\n[5/5] Generating AI Public Health Bulletin via Gemini API...")
    voice = GeminiVoice()
    bulletin = voice.generate(phri_result, disease_route, seir_result, location=weather_dict.get('city_name', 'Target Location'))

    print("\n" + "=" * 65)
    print(f"  HEADLINE: {bulletin.headline}")
    print("=" * 65)
    print("\n  PUBLIC ADVISORY:")
    print(bulletin.health_bulletin)
    print("\n  ACTION ITEMS:")
    for action in bulletin.action_items:
        print(f"   - {action}")
    print("\n" + "=" * 65)

    return {
        "weather": weather_dict,
        "latest_meta": latest_meta,
        "yolo": yolo_dict,
        "phri_result": phri_result,
        "disease_route": disease_route,
        "seir_result": seir_result,
        "bulletin": bulletin,
    }


if __name__ == "__main__":
    run_live_pipeline()
