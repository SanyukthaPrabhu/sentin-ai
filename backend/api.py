# backend/api.py
"""
backend/api.py
==============
FastAPI backend for the Sentin-AI Community Early Warning Hub.
Wraps core ML modules into REST endpoints and provides public/admin tools.
"""

import sys
import os
import base64
import traceback
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

# Path setup
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# Import database and background scheduler
import database
import scheduler
from database import get_connection, log_system_event
from official_alerts import fetch_and_sync_official_alerts, inject_mock_official_alert, get_active_official_alerts
from alert_engine import AlertEngine

# ── App Init ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sentin-AI Community Early Warning API",
    description="Early warning and environmental disease risk intelligence platform.",
    version="2.0.0",
)

# Allow CORS for dev environment
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for Demo Mode
DEMO_SCENARIO = None  # None, "scenario_1", "scenario_2", "scenario_3", "scenario_4", "scenario_5"

# ── Startup/Shutdown events ──────────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    # Initialize DB (creates files and pre-seeds data)
    database.init_db()
    # Start the background worker scheduler
    scheduler.start_scheduler()
    log_system_event("INFO", "FastAPI server started, database initialized, scheduler thread active.", stage="startup")

@app.on_event("shutdown")
def shutdown_event():
    # Shutdown the background thread safely
    scheduler.stop_scheduler()
    log_system_event("INFO", "FastAPI server shutting down, scheduler thread stopped.", stage="shutdown")


# ── Module loaders (cached) ──────────────────────────────────────────────────
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


# ── Pydantic models ──────────────────────────────────────────────────────────
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
    hist_date:  str            = "2024-08-15"

class StressTestRequest(BaseModel):
    disease_bucket: str = "dengue_malaria"

class SubscriptionRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location_name: str
    latitude: float
    longitude: float
    all_alerts: bool = True
    environmental_alerts: bool = False
    disease_risk_alerts: bool = False
    weather_alerts: bool = False
    official_disaster_alerts: bool = False
    severity_preference: str = "HIGH"

class DemoScenarioRequest(BaseModel):
    scenario: Optional[str] = None  # "scenario_1", "scenario_2", "scenario_3", "scenario_4", "scenario_5", or "none"

class InjectOfficialAlertRequest(BaseModel):
    title: str
    message: str
    severity: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str = "NDMA / SACHET"

class AddLocationRequest(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_km: float = 5.0


# ── Shared base64 encoder ────────────────────────────────────────────────────
def _encode_image(path_str) -> Optional[str]:
    if isinstance(path_str, str) and path_str.strip() and Path(path_str).exists():
        try:
            with open(path_str, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass
    return None

def _run_core_pipeline(phri_result, disease_route, seir_result, bulletin,
                       weather_dict: dict, yolo_dict: dict,
                       location_name: str, live_meta: Optional[dict] = None,
                       rgb_b64: Optional[str] = None,
                       ndwi_b64: Optional[str] = None) -> dict:
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
        "rgb_b64":       rgb_b64,
        "ndwi_b64":      ndwi_b64,
        "demo_mode":     DEMO_SCENARIO is not None,
    }


# ── Demo Mode Interceptor ────────────────────────────────────────────────────
def _check_demo_interceptor(location_name: str, lat: float, lon: float) -> Optional[dict]:
    """Intercepts requests and returns mock output if Demo Mode is active."""
    global DEMO_SCENARIO
    if not DEMO_SCENARIO:
        return None

    # Load modules to reuse class representations for return type consistency
    from phri_engine import PHRIResult
    from disease_router import DiseaseRoute, DISEASE_META
    from seir_model import SEIRResult
    from gemini_voice import BulletinResult

    print(f"[DEMO INTERCEPTOR] Generating mock responses for scenario: {DEMO_SCENARIO}")
    
    if DEMO_SCENARIO == "scenario_1":
        # Low risk
        phri_res = PHRIResult(phri_score=0.15, confidence=1.0, risk_level="LOW", visual_complete=True, weather_complete=True, window_end_date=date.today())
        dis_route = DiseaseRoute(primary_bucket="none", secondary_buckets=[], phri_score=0.15, risk_level="LOW", rules_triggered=[], reasoning="All environmental factors within safe normal limits.", meta=DISEASE_META["none"])
        seir_res = SEIRResult(disease_bucket="none", phri_score=0.15, population=100000, projection_days=14, beta_effective=0.0, peak_cases=0, peak_day=0, total_projected=0, attack_rate_pct=0.0, new_cases_curve=[0]*15)
        bulletin = BulletinResult(headline="Low Environmental Disease Risk", health_bulletin="Sensors report minimal stagnant water, low garbage accumulation, and standard moderate temperatures. No primary public health concerns detected at this time.", action_items=["Continue routine cleaning.", "Report persistent community drain blocks."], officer_note="Baseline parameters stable.", phri_score=0.15, risk_level="LOW", disease_label="General Outbreak Risk", fallback_used=True, generated_date=date.today())
        weather = {"temperature_2m_c": 24.5, "relative_humidity_pct": 52.0, "precipitation_imerg_mm": 0.0, "dew_frost_point_c": 12.0, "wind_speed_10m_ms": 3.2, "all_sky_insolation_clearness": 0.72}
        yolo = {"stagnant_water_count": 0, "stagnant_water_area_px": 0.0, "garbage_count": 0, "vegetation_anomaly_score": 0.05}
        live_meta = {"source": "Sentinel-2 Composite", "date": str(date.today()), "cloud_pct": 8.5, "ndwi_mean": -0.24, "ndvi_mean": 0.45}
        
    elif DEMO_SCENARIO == "scenario_2":
        # Heavy rain + stagnant water
        phri_res = PHRIResult(phri_score=0.68, confidence=1.0, risk_level="HIGH", visual_complete=True, weather_complete=True, window_end_date=date.today())
        dis_route = DiseaseRoute(primary_bucket="dengue_malaria", secondary_buckets=[], phri_score=0.68, risk_level="HIGH", rules_triggered=["dengue_malaria"], reasoning="Rainfall spike (>40mm) + 14 stagnant water pooling sites detected.", meta=DISEASE_META["dengue_malaria"])
        seir_res = SEIRResult(disease_bucket="dengue_malaria", phri_score=0.68, population=100000, projection_days=14, beta_effective=0.28, peak_cases=45, peak_day=8, total_projected=180, attack_rate_pct=0.18, new_cases_curve=[0, 5, 12, 22, 34, 42, 45, 45, 40, 32, 22, 12, 6, 2, 0])
        bulletin = BulletinResult(headline="Elevated Vector Breeding Risk Post-Rainfall", health_bulletin="Recent intense rainfall coupled with high humidity (>80%) has created multiple stagnant water pooling sites. Risk indicators for vector breeding are elevated.", action_items=["Drain flower pots and tires.", "Ensure water coolers are scrubbed dry.", "Apply mosquito repellent during dawn and dusk."], officer_note="Monitor pooling lakes closely.", phri_score=0.68, risk_level="HIGH", disease_label="Dengue / Malaria", fallback_used=True, generated_date=date.today())
        weather = {"temperature_2m_c": 28.2, "relative_humidity_pct": 84.0, "precipitation_imerg_mm": 42.0, "dew_frost_point_c": 22.0, "wind_speed_10m_ms": 1.8, "all_sky_insolation_clearness": 0.35}
        yolo = {"stagnant_water_count": 14, "stagnant_water_area_px": 15600.0, "garbage_count": 1, "vegetation_anomaly_score": 0.12}
        live_meta = {"source": "Sentinel-2 Composite", "date": str(date.today()), "cloud_pct": 42.0, "ndwi_mean": 0.18, "ndvi_mean": 0.38}
        
    elif DEMO_SCENARIO == "scenario_3":
        # High vector risk
        phri_res = PHRIResult(phri_score=0.88, confidence=1.0, risk_level="CRITICAL", visual_complete=True, weather_complete=True, window_end_date=date.today())
        dis_route = DiseaseRoute(primary_bucket="dengue_malaria", secondary_buckets=["lepto_cholera"], phri_score=0.88, risk_level="CRITICAL", rules_triggered=["dengue_malaria", "lepto_cholera"], reasoning="Critical stagnant water pooling (28 sites) + heavy garbage accumulation in water logged zones.", meta=DISEASE_META["dengue_malaria"])
        seir_res = SEIRResult(disease_bucket="dengue_malaria", phri_score=0.88, population=100000, projection_days=14, beta_effective=0.42, peak_cases=120, peak_day=9, total_projected=540, attack_rate_pct=0.54, new_cases_curve=[0, 8, 24, 52, 88, 110, 120, 118, 102, 82, 58, 32, 14, 4, 0])
        bulletin = BulletinResult(headline="CRITICAL OUTBREAK WARNING: Vector Breeding & Flooding Hazards", health_bulletin="Severe satellite detection of 28 stagnant water sites and widespread waste piles in active flood water zones. Extremely high vector threat index.", action_items=["Immediate neighborhood drain unclogging.", "Avoid wading in standing street water.", "Report municipal blockages immediately."], officer_note="Urgent local body intervention recommended.", phri_score=0.88, risk_level="CRITICAL", disease_label="Dengue / Malaria", fallback_used=True, generated_date=date.today())
        weather = {"temperature_2m_c": 30.5, "relative_humidity_pct": 89.0, "precipitation_imerg_mm": 18.0, "dew_frost_point_c": 25.0, "wind_speed_10m_ms": 1.2, "all_sky_insolation_clearness": 0.28}
        yolo = {"stagnant_water_count": 28, "stagnant_water_area_px": 32400.0, "garbage_count": 8, "vegetation_anomaly_score": 0.24}
        live_meta = {"source": "Sentinel-2 Composite", "date": str(date.today()), "cloud_pct": 58.0, "ndwi_mean": 0.32, "ndvi_mean": 0.30}
        
    elif DEMO_SCENARIO == "scenario_4":
        # Official disaster warning (we make sure the active warnings table has a mock red alert warning, but we still return high AI PHRI separately)
        inject_mock_official_alert(
            title="RED ALERT: Extreme Heavy Rainfall and Urban Flooding Warning",
            message="The Disaster Management Authority has issued an extreme rainfall and severe flood warning for the metropolitan area. Citizens are advised to stay indoors, avoid travel near lakes/low-lying subways, and secure water storage.",
            severity="CRITICAL",
            location=location_name,
            lat=lat, lon=lon,
            source="National Disaster Management Authority (SACHET)"
        )
        # return lepto_cholera warning separately
        phri_res = PHRIResult(phri_score=0.81, confidence=1.0, risk_level="HIGH", visual_complete=True, weather_complete=True, window_end_date=date.today())
        dis_route = DiseaseRoute(primary_bucket="lepto_cholera", secondary_buckets=[], phri_score=0.81, risk_level="HIGH", rules_triggered=["lepto_cholera"], reasoning="Extensive flood water accumulation near garbage piles.", meta=DISEASE_META["lepto_cholera"])
        seir_res = SEIRResult(disease_bucket="lepto_cholera", phri_score=0.81, population=100000, projection_days=14, beta_effective=0.35, peak_cases=62, peak_day=7, total_projected=280, attack_rate_pct=0.28, new_cases_curve=[0, 8, 18, 36, 52, 60, 62, 58, 48, 36, 24, 12, 6, 2, 0])
        bulletin = BulletinResult(headline="Water-borne Contamination Risks (Leptospirosis / Cholera)", health_bulletin="Flooding has merged street waste with standing pool areas. Strong warning to boil drinking water and avoid direct skin contact with flood waters.", action_items=["Boil drinking water for 20 minutes.", "Avoid walking barefoot in standing floodwater.", "Disinfect flooded household surfaces."], officer_note="Coordination with drinking water boards required.", phri_score=0.81, risk_level="HIGH", disease_label="Leptospirosis / Cholera", fallback_used=True, generated_date=date.today())
        weather = {"temperature_2m_c": 26.8, "relative_humidity_pct": 92.0, "precipitation_imerg_mm": 55.0, "dew_frost_point_c": 24.0, "wind_speed_10m_ms": 4.5, "all_sky_insolation_clearness": 0.22}
        yolo = {"stagnant_water_count": 22, "stagnant_water_area_px": 28000.0, "garbage_count": 5, "vegetation_anomaly_score": 0.18}
        live_meta = {"source": "Sentinel-2 Composite", "date": str(date.today()), "cloud_pct": 82.0, "ndwi_mean": 0.28, "ndvi_mean": 0.32}

    elif DEMO_SCENARIO == "scenario_5":
        # Sentinel-2 unavailable -> SAR fallback
        phri_res = PHRIResult(phri_score=0.62, confidence=0.85, risk_level="HIGH", visual_complete=False, weather_complete=True, window_end_date=date.today())
        dis_route = DiseaseRoute(primary_bucket="dengue_malaria", secondary_buckets=[], phri_score=0.62, risk_level="HIGH", rules_triggered=["dengue_malaria"], reasoning="Dengue/Malaria proxy rules triggered: high humidity (88%) + high rain (12mm) + elevated temp (29.5C). Optical satellite data blocked by clouds, using radar fallback.", meta=DISEASE_META["dengue_malaria"])
        seir_res = SEIRResult(disease_bucket="dengue_malaria", phri_score=0.62, population=100000, projection_days=14, beta_effective=0.25, peak_cases=32, peak_day=8, total_projected=130, attack_rate_pct=0.13, new_cases_curve=[0, 3, 8, 16, 24, 30, 32, 32, 28, 22, 16, 8, 4, 1, 0])
        bulletin = BulletinResult(headline="High Risk Advisory (Sentinel-1 SAR Radar Fallback Active)", health_bulletin="Heavy cloud cover has blocked optical satellite imagery. Radar Sentinel-1 analysis confirms soil saturation. Weather models indicate high vector threat.", action_items=["Drain neighborhood flower pots.", "Sleep under insecticide-treated bed nets."], officer_note="No optical visual features available. Active radar backing.", phri_score=0.62, risk_level="HIGH", disease_label="Dengue / Malaria", fallback_used=True, generated_date=date.today())
        weather = {"temperature_2m_c": 29.5, "relative_humidity_pct": 88.0, "precipitation_imerg_mm": 12.0, "dew_frost_point_c": 23.0, "wind_speed_10m_ms": 2.1, "all_sky_insolation_clearness": 0.18}
        yolo = {"stagnant_water_count": 0, "stagnant_water_area_px": 0.0, "garbage_count": 0, "vegetation_anomaly_score": 0.0}
        live_meta = {"source": "Sentinel-1 SAR", "date": str(date.today()), "cloud_pct": 100.0, "ndwi_mean": None, "ndvi_mean": None}

    else:
        return None

    # Build response format (identical to normal pipeline)
    return _run_core_pipeline(
        phri_res, dis_route, seir_res, bulletin,
        weather, yolo, location_name, live_meta,
        rgb_b64=None, ndwi_b64=None
    )


# ── REST API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Detailed health check for administrative monitoring."""
    db_ok = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone():
            db_ok = True
        conn.close()
    except Exception:
        pass
        
    model_ok = False
    try:
        # Check if the file exists and is loadable
        if Path(ROOT / "models" / "lstm_phri.h5").exists():
            model_ok = True
    except Exception:
        pass

    # Simple check on weather API config
    weather_ok = len(os.getenv("OPENWEATHERMAP_API_KEY", "")) > 0
    gee_ok = len(os.getenv("GEE_PROJECT_ID", "")) > 0
    groq_ok = len(os.getenv("GROQ_API_KEY", "")) > 0

    status = "healthy" if db_ok and model_ok else "degraded"

    return {
        "status": status,
        "date": str(date.today()),
        "components": {
            "database": "healthy" if db_ok else "unhealthy",
            "model": "healthy" if model_ok else "unhealthy",
            "weather_api": "configured" if weather_ok else "not_configured",
            "earth_engine": "configured" if gee_ok else "not_configured",
            "groq_llm": "configured" if groq_ok else "not_configured",
            "notification_service": "online"
        }
    }


# ── Pipeline Executions (Preserved & Extended) ───────────────────────────────

@app.post("/api/pipeline/manual")
def pipeline_manual(req: ManualPipelineRequest):
    """Run PHRI + SEIR + LLM with user-supplied weather and YOLO values."""
    try:
        loc = req.location
        
        # Check Demo Interceptor
        demo_resp = _check_demo_interceptor(loc.location_name, loc.lat, loc.lon)
        if demo_resp:
            return demo_resp

        engine, router, voice = get_modules()
        from seir_model import SEIRModel

        weather = req.weather.model_dump()
        yolo    = req.yolo.model_dump()

        phri_result   = engine.score_realtime(weather, yolo, lat=loc.lat, lon=loc.lon, is_manual=True)
        disease_route = router.classify(phri_result, weather, yolo)
        seir_result   = SEIRModel(
            disease_route.primary_bucket,
            lat=loc.lat, lon=loc.lon, radius_km=loc.radius_km
        ).project(phri_result.phri_score, days=14)
        bulletin = voice.generate(phri_result, disease_route, seir_result,
                                  location=loc.location_name)

        # Write results to DB for history tracking (never overwrite)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_assessments (
                location_name, lat, lon, phri_score, risk_level, disease_bucket, disease_label,
                confidence, visual_complete, weather_complete, peak_cases, peak_day, total_projected,
                attack_rate_pct, beta_effective, bulletin_headline, bulletin_text, action_items, officer_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc.location_name, loc.lat, loc.lon, phri_result.phri_score, phri_result.risk_level, 
            disease_route.primary_bucket, disease_route.meta.get("label", "—"), phri_result.confidence,
            1 if phri_result.visual_complete else 0, 1 if phri_result.weather_complete else 0,
            seir_result.peak_cases, seir_result.peak_day, seir_result.total_projected,
            seir_result.attack_rate_pct, seir_result.beta_effective, bulletin.headline,
            bulletin.health_bulletin, json.dumps(list(bulletin.action_items)), bulletin.officer_note
        ))
        
        cursor.execute("""
            INSERT INTO environmental_observations (
                location_name, lat, lon, temperature_2m_c, relative_humidity_pct, precipitation_imerg_mm,
                dew_frost_point_c, wind_speed_10m_ms, all_sky_insolation_clearness, stagnant_water_count,
                stagnant_water_area_px, garbage_count, vegetation_anomaly_score, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc.location_name, loc.lat, loc.lon, weather.get("temperature_2m_c"), weather.get("relative_humidity_pct"),
            weather.get("precipitation_imerg_mm"), weather.get("dew_frost_point_c"), weather.get("wind_speed_10m_ms"),
            weather.get("all_sky_insolation_clearness"), yolo.get("stagnant_water_count"),
            yolo.get("stagnant_water_area_px"), yolo.get("garbage_count"), yolo.get("vegetation_anomaly_score"),
            "manual"
        ))
        conn.commit()
        conn.close()

        # Trigger Alert Engine (same as live pipeline) so manual runs also send Telegram alerts
        alert_engine = AlertEngine()
        alert_engine.evaluate_location_risk(
            location_name=loc.location_name,
            lat=loc.lat, lon=loc.lon,
            phri_score=phri_result.phri_score,
            disease_bucket=disease_route.primary_bucket,
            disease_label=disease_route.meta.get("label", "—"),
            weather_dict=weather,
            yolo_dict=yolo
        )

        return _run_core_pipeline(
            phri_result, disease_route, seir_result, bulletin,
            weather, yolo, loc.location_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/pipeline/live")
def pipeline_live(req: LivePipelineRequest):
    """Full automated pipeline: live weather + GEE satellite + YOLO + PHRI + LLM."""
    try:
        loc = req.location

        # Check Demo Interceptor
        demo_resp = _check_demo_interceptor(loc.location_name, loc.lat, loc.lon)
        if demo_resp:
            return demo_resp

        from realtime_pipeline import run_live_pipeline
        
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

        rgb_b64  = _encode_image(live_meta.get("rgb_path"))
        ndwi_b64 = _encode_image(live_meta.get("ndwi_png_path"))

        # Save to DB for tracking
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_assessments (
                location_name, lat, lon, phri_score, risk_level, disease_bucket, disease_label,
                confidence, visual_complete, weather_complete, peak_cases, peak_day, total_projected,
                attack_rate_pct, beta_effective, bulletin_headline, bulletin_text, action_items, 
                officer_note, rgb_path, ndwi_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc.location_name, loc.lat, loc.lon, phri_result.phri_score, phri_result.risk_level, 
            disease_route.primary_bucket, disease_route.meta.get("label", "—"), phri_result.confidence,
            1 if phri_result.visual_complete else 0, 1 if phri_result.weather_complete else 0,
            seir_result.peak_cases, seir_result.peak_day, seir_result.total_projected,
            seir_result.attack_rate_pct, seir_result.beta_effective, bulletin.headline,
            bulletin.health_bulletin, json.dumps(list(bulletin.action_items)), bulletin.officer_note,
            live_meta.get("rgb_path"), live_meta.get("ndwi_png_path")
        ))
        
        cursor.execute("""
            INSERT INTO environmental_observations (
                location_name, lat, lon, temperature_2m_c, relative_humidity_pct, precipitation_imerg_mm,
                dew_frost_point_c, wind_speed_10m_ms, all_sky_insolation_clearness, stagnant_water_count,
                stagnant_water_area_px, garbage_count, vegetation_anomaly_score, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc.location_name, loc.lat, loc.lon, weather.get("temperature_2m_c"), weather.get("relative_humidity_pct"),
            weather.get("precipitation_imerg_mm"), weather.get("dew_frost_point_c"), weather.get("wind_speed_10m_ms"),
            weather.get("all_sky_insolation_clearness"), yolo.get("stagnant_water_count"),
            yolo.get("stagnant_water_area_px"), yolo.get("garbage_count"), yolo.get("vegetation_anomaly_score"),
            "live_pipeline"
        ))
        conn.commit()
        
        # Trigger Alert Engine rules to sync alarms
        alert_engine = AlertEngine()
        alert_engine.evaluate_location_risk(
            location_name=loc.location_name,
            lat=loc.lat, lon=loc.lon,
            phri_score=phri_result.phri_score,
            disease_bucket=disease_route.primary_bucket,
            disease_label=disease_route.meta.get("label", "—"),
            weather_dict=weather,
            yolo_dict=yolo
        )
        
        conn.close()

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
        loc = req.location
        
        # Check Demo Interceptor
        demo_resp = _check_demo_interceptor(loc.location_name, loc.lat, loc.lon)
        if demo_resp:
            return demo_resp

        engine, router, voice = get_modules()
        from seir_model import SEIRModel
        from datetime import datetime
        
        hist_dt = datetime.strptime(req.hist_date, "%Y-%m-%d").date()
        phri_result   = engine.score_historical(hist_dt, lat=loc.lat, lon=loc.lon)

        raw_vals = phri_result.raw_features[-1]
        weather = {
            "temperature_2m_c":            float(raw_vals[0]),
            "relative_humidity_pct":       float(raw_vals[1]),
            "precipitation_imerg_mm":      float(raw_vals[2]),
            "dew_frost_point_c":           float(raw_vals[3]),
            "wind_speed_10m_ms":            float(raw_vals[4]),
            "all_sky_insolation_clearness": float(raw_vals[5]),
        }
        yolo = {
            "stagnant_water_count":     int(raw_vals[6]),
            "stagnant_water_area_px":   float(raw_vals[7]),
            "garbage_count":            int(raw_vals[8]),
            "vegetation_anomaly_score": float(raw_vals[9]),
        }

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
    """Return the latest global satellite imagery composite."""
    try:
        csv_path = ROOT / "data" / "raw_imagery" / "sentinel2_metadata.csv"
        if not csv_path.exists():
            return {"rgb_b64": None, "ndwi_b64": None, "meta": None}

        df = pd.read_csv(csv_path)
        if df.empty:
            return {"rgb_b64": None, "ndwi_b64": None, "meta": None}

        row = df.iloc[-1]
        meta = row.to_dict()

        return {
            "rgb_b64":  _encode_image(meta.get("rgb_path")),
            "ndwi_b64": _encode_image(meta.get("ndwi_png_path")),
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
def history(lat: Optional[float] = None, lon: Optional[float] = None):
    """Historical timeline loading."""
    try:
        if lat is not None and lon is not None:
            from phri_engine import prepare_location_weather
            csv = prepare_location_weather(lat, lon)
        else:
            csv = ROOT / "data" / "weather_cache" / "weather_features.csv"

        if not csv.exists():
            return {"data": [], "is_proxy": True}

        df = pd.read_csv(csv, parse_dates=["date"])
        is_proxy = True
        real_scores = {}
        
        try:
            engine, _, _ = get_modules()
            from phri_engine import LSTM_FEATURES, WINDOW_SIZE, _normalize_window
            engine._load_model()
            if engine._model is not None:
                if len(df) >= WINDOW_SIZE:
                    feature_matrix = df[LSTM_FEATURES].values.astype(np.float32)
                    windows = []
                    dates_list = []
                    for i in range(len(df) - WINDOW_SIZE + 1):
                        window = feature_matrix[i : i + WINDOW_SIZE]
                        window_norm = _normalize_window(window)
                        windows.append(window_norm)
                        dt_str = str(df.iloc[i + WINDOW_SIZE - 1]["date"].date())
                        dates_list.append(dt_str)
                        
                    X = np.array(windows, dtype=np.float32)
                    scores = engine._model.predict(X, batch_size=128, verbose=0).flatten()
                    
                    for dt_str, score in zip(dates_list, scores):
                        real_scores[dt_str] = float(score)
                    is_proxy = False
        except Exception as e:
            print(f"[API] LSTM backtest error: {e}")

        if not real_scores:
            scores_csv = ROOT / "validation" / "backtest_phri_scores.csv"
            if scores_csv.exists() and (lat is None or (abs(lat - 12.98) < 0.05 and abs(lon - 77.58) < 0.05)):
                try:
                    df_scores = pd.read_csv(scores_csv, parse_dates=["seq_end"])
                    for _, row in df_scores.iterrows():
                        dt = row["seq_end"].date() if hasattr(row["seq_end"], "date") else row["seq_end"]
                        real_scores[str(dt)] = float(row["phri_score"])
                    if real_scores:
                        is_proxy = False
                except Exception:
                    pass

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


# ── New Community Early Warning Platform REST APIs ───────────────────────────

@app.get("/api/risk/{location}")
def get_risk_location(location: str):
    """Retrieve the latest risk assessment stored for a specific location."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM risk_assessments 
        WHERE location_name LIKE ? 
        ORDER BY created_at DESC LIMIT 1
    """, (f"%{location}%",))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        # Fallback to returning Bengaluru default placeholder if not evaluated
        return {"error": "Location not actively monitored. Run live pipeline to create records."}
        
    res = dict(row)
    # Decode list of action items
    try:
        res["action_items"] = json.loads(res["action_items"])
    except Exception:
        res["action_items"] = []
        
    conn.close()
    return res

@app.get("/api/risk/latest")
def get_risk_latest():
    """Fetch the latest assessment across all monitored locations."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.* FROM risk_assessments r
        INNER JOIN (
            SELECT location_name, MAX(created_at) as max_time
            FROM risk_assessments
            GROUP BY location_name
        ) tm ON r.location_name = tm.location_name AND r.created_at = tm.max_time
        ORDER BY r.phri_score DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/map/risk")
def get_map_risk():
    """Retrieve map markers for both AI alerts and official warnings."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch latest monitored locations with their PHRI scores
    cursor.execute("""
        SELECT r.location_name, r.lat, r.lon, r.phri_score, r.risk_level, r.disease_label, r.created_at
        FROM risk_assessments r
        INNER JOIN (
            SELECT location_name, MAX(created_at) as max_time
            FROM risk_assessments
            GROUP BY location_name
        ) tm ON r.location_name = tm.location_name AND r.created_at = tm.max_time
    """)
    ai_rows = cursor.fetchall()
    
    # 2. Fetch active official alerts
    cursor.execute("""
        SELECT title, message, severity, location, latitude, longitude, source, created_at
        FROM official_alerts
        WHERE status = 'active' AND (expires_at IS NULL OR expires_at > datetime('now'))
    """)
    off_rows = cursor.fetchall()
    conn.close()
    
    markers = []
    # Plot AI monitored points
    for r in ai_rows:
        markers.append({
            "type": "ai_risk",
            "name": r["location_name"],
            "lat": r["lat"],
            "lon": r["lon"],
            "phri": r["phri_score"],
            "severity": r["risk_level"],
            "disease": r["disease_label"],
            "updated_at": r["created_at"]
        })
        
    # Plot Official points
    for r in off_rows:
        markers.append({
            "type": "official_alert",
            "name": r["title"],
            "lat": r["latitude"] if r["latitude"] else 20.5937,
            "lon": r["longitude"] if r["longitude"] else 78.9629,
            "message": r["message"],
            "severity": r["severity"],
            "location": r["location"],
            "source": r["source"],
            "updated_at": r["created_at"]
        })
        
    return markers

@app.get("/api/alerts")
def get_all_alerts():
    """Get active AI risk alerts + official disaster warnings, deduplicated."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Active AI alerts
    cursor.execute("""
        SELECT id, location_name as location, latitude, longitude, title, message, severity, phri_score, 'AI Risk Assessment' as source, 'ai' as source_type, created_at
        FROM ai_alerts WHERE status = 'active'
    """)
    ai_alerts = [dict(r) for r in cursor.fetchall()]
    
    # Active Official alerts
    cursor.execute("""
        SELECT id, location, latitude, longitude, title, message, severity, 1.0 as phri_score, source, 'official' as source_type, created_at
        FROM official_alerts WHERE status = 'active'
    """)
    off_alerts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    # Deduplicate AI alerts
    seen_ai = set()
    deduped_ai = []
    for alert in ai_alerts:
        key = (alert['title'], alert['message'], alert['location'])
        if key not in seen_ai:
            seen_ai.add(key)
            deduped_ai.append(alert)
            
    # Deduplicate Official alerts
    seen_off = set()
    deduped_off = []
    for alert in off_alerts:
        key = (alert['title'], alert['message'], alert['location'])
        if key not in seen_off:
            seen_off.add(key)
            deduped_off.append(alert)
            
    return {
        "ai_alerts": deduped_ai,
        "official_alerts": deduped_off,
        "total_active": len(deduped_ai) + len(deduped_off)
    }

@app.get("/api/alerts/official")
def get_official_alerts_only(location: Optional[str] = None):
    return get_active_official_alerts(location)

@app.get("/api/alerts/ai")
def get_ai_alerts_only():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_alerts WHERE status = 'active' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/alerts/{id}")
def get_specific_alert(id: int, type: str = "ai"):
    conn = get_connection()
    cursor = conn.cursor()
    if type == "ai":
        cursor.execute("SELECT * FROM ai_alerts WHERE id = ?", (id,))
    else:
        cursor.execute("SELECT * FROM official_alerts WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return dict(row)

@app.post("/api/subscriptions")
def create_subscription(req: SubscriptionRequest):
    """Subscribe a user's contact information to local alerts."""
    if not req.email and not req.phone:
        raise HTTPException(status_code=400, detail="Either Email or Phone must be provided for alerts subscription.")
        
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscriptions (
                email, phone, location_name, latitude, longitude, all_alerts,
                environmental_alerts, disease_risk_alerts, weather_alerts,
                official_disaster_alerts, severity_preference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.email, req.phone, req.location_name, req.latitude, req.longitude,
            1 if req.all_alerts else 0, 1 if req.environmental_alerts else 0,
            1 if req.disease_risk_alerts else 0, 1 if req.weather_alerts else 0,
            1 if req.official_disaster_alerts else 0, req.severity_preference
        ))
        sub_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_system_event("INFO", f"New user subscription created: ID #{sub_id} for {req.location_name}")
        
        # Check if there is an active alert for this location and dispatch a welcome alert immediately
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ai_alerts 
                WHERE location_name = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """, (req.location_name,))
            active_alert = cursor.fetchone()
            conn.close()
            
            if active_alert:
                sev_rank = {"MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
                alert_rank = sev_rank.get(active_alert["severity"], 0)
                sub_pref_rank = sev_rank.get(req.severity_preference, 2)
                
                if alert_rank >= sub_pref_rank:
                    from notification_service import NotificationService
                    notifier = NotificationService()
                    pref_dict = {
                        "all_alerts": 1 if req.all_alerts else 0,
                        "environmental_alerts": 1 if req.environmental_alerts else 0,
                        "disease_risk_alerts": 1 if req.disease_risk_alerts else 0,
                        "weather_alerts": 1 if req.weather_alerts else 0,
                        "official_disaster_alerts": 1 if req.official_disaster_alerts else 0
                    }
                    notifier.dispatch_alert(
                        subscription_id=sub_id,
                        recipient_email=req.email,
                        recipient_phone=req.phone,
                        alert_title=f"Welcome to Sentin-AI! Active Warning: {active_alert['title']}",
                        alert_message=active_alert["message"],
                        pref=pref_dict
                    )
        except Exception as welcome_err:
            print(f"[API] Welcome notification error: {welcome_err}")
            
        return {"status": "subscribed", "subscription_id": sub_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/subscriptions/{id}")
def delete_subscription(id: int):
    """Unsubscribe a user from alerts."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM subscriptions WHERE id = ?", (id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Subscription ID not found.")
            
        cursor.execute("DELETE FROM subscriptions WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        log_system_event("INFO", f"Removed subscription ID #{id}")
        return {"status": "unsubscribed", "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/awareness")
def get_awareness():
    """Retrieve all safety guides and emergency checklists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM awareness_content")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/awareness/{category}")
def get_awareness_category(category: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM awareness_content WHERE category = ?", (category,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Safety category not found.")
    return dict(row)

@app.get("/api/projection/{location}")
def get_projection_location(location: str):
    """Get the latest SEIR cases projection curve for a location."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT disease_label, peak_cases, peak_day, total_projected, attack_rate_pct, beta_effective, created_at
        FROM risk_assessments 
        WHERE location_name LIKE ? 
        ORDER BY created_at DESC LIMIT 1
    """, (f"%{location}%",))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No historical projection found for this location.")
    return dict(row)

@app.get("/api/environment/{location}")
def get_environment_location(location: str):
    """Retrieve historical observations for environmental factors (YOLO, Weather) to plot graphs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM environmental_observations 
        WHERE location_name LIKE ? 
        ORDER BY created_at DESC LIMIT 15
    """, (f"%{location}%",))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/analyze")
def api_analyze(req: LivePipelineRequest):
    """Ad-hoc analytics runner. Alias of pipeline/live."""
    return pipeline_live(req)


# ── Demo Scenarios Control ───────────────────────────────────────────────────

@app.post("/api/pipeline/demo")
def set_demo_scenario(req: DemoScenarioRequest):
    """Activates a simulated scenario override."""
    global DEMO_SCENARIO
    scen = req.scenario
    if scen == "none" or scen is None:
        DEMO_SCENARIO = None
        log_system_event("INFO", "Disabled Demo Mode. Reverting to normal sensor inputs.")
        return {"status": "disabled", "message": "Demo mode deactivated. Normal pipeline restored."}
        
    valid = ["scenario_1", "scenario_2", "scenario_3", "scenario_4", "scenario_5"]
    if scen not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Select from: {valid}")
        
    DEMO_SCENARIO = scen
    
    # Sync alerts in the database if Scenario 4 is active to ensure the UI updates
    if scen == "scenario_4":
        _check_demo_interceptor("Bengaluru, Karnataka", 12.98, 77.58)
        
    log_system_event("INFO", f"Demo Mode set to active: {scen}")
    return {"status": "enabled", "scenario": scen, "message": f"Demo scenario {scen} loaded."}


# ── Administrative Controls ──────────────────────────────────────────────────

@app.get("/api/admin/system")
def get_admin_system():
    """Retrieve system health diagnostic data and active queue logs."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Counts
    cursor.execute("SELECT COUNT(*) FROM locations")
    loc_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    sub_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM ai_alerts WHERE status = 'active'")
    ai_alert_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM official_alerts WHERE status = 'active'")
    off_alert_count = cursor.fetchone()[0]
    
    # Failed fetches
    cursor.execute("SELECT COUNT(*) FROM system_logs WHERE level = 'ERROR'")
    error_count = cursor.fetchone()[0]
    
    # Active locations list
    cursor.execute("SELECT name, latitude, longitude, radius_km, created_at FROM locations")
    loc_list = [dict(r) for r in cursor.fetchall()]
    
    # Health checks
    health_data = health()
    
    conn.close()
    
    return {
        "monitored_locations_count": loc_count,
        "monitored_locations": loc_list,
        "subscriptions_count": sub_count,
        "active_ai_alerts": ai_alert_count,
        "active_official_alerts": off_alert_count,
        "failed_fetches_count": error_count,
        "system_health": health_data["components"],
        "demo_mode": DEMO_SCENARIO,
    }

@app.get("/api/admin/logs")
def get_admin_logs(limit: int = Query(50, le=200)):
    """Fetch structured system logs from SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/locations")
def add_monitored_location(req: AddLocationRequest):
    """Enables monitoring on a new geographic coordinate coordinate."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM locations WHERE name = ?", (req.name,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Location name already exists.")
            
        cursor.execute("""
            INSERT INTO locations (name, latitude, longitude, radius_km)
            VALUES (?, ?, ?, ?)
        """, (req.name, req.latitude, req.longitude, req.radius_km))
        conn.commit()
        conn.close()
        log_system_event("INFO", f"Admin added new monitored location: {req.name}")
        return {"status": "success", "message": f"Added monitored location: {req.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/locations")
def list_monitored_locations():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/alerts/official")
def inject_official_alert(req: InjectOfficialAlertRequest):
    """Manually insert an official warning alert."""
    success = inject_mock_official_alert(
        title=req.title,
        message=req.message,
        severity=req.severity,
        location=req.location,
        lat=req.latitude,
        lon=req.longitude,
        source=req.source
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to inject warning.")
    return {"status": "success", "message": "Official warning alert injected successfully."}
