# backend/scheduler.py
import os
import time
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

from database import get_connection, log_system_event
from alert_engine import AlertEngine
from realtime_pipeline import run_live_pipeline

# ── Interval Configurations (Seconds) ────────────────────────────────────────
# Defaults: check locations every 60s, fetch weather/run model every 1h, sync satellite daily.
ALERT_CHECK_INTERVAL = int(os.getenv("ALERT_CHECK_INTERVAL", 60))
WEATHER_INTERVAL = int(os.getenv("WEATHER_INTERVAL", 3600))
SATELLITE_INTERVAL = int(os.getenv("SATELLITE_INTERVAL", 86400))
MODEL_INTERVAL = int(os.getenv("MODEL_INTERVAL", 3600))

# Thread controller
_scheduler_thread = None
_stop_event = threading.Event()

class BackgroundScheduler:
    def __init__(self):
        self.alert_engine = AlertEngine()

    def run_surveillance_cycle(self):
        """Processes each monitored location in the database."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, latitude, longitude, radius_km FROM locations")
        locations_rows = cursor.fetchall()
        locations = [dict(r) for r in locations_rows]
        conn.close()
        
        now = datetime.now()
        
        for loc in locations:
            loc_id = loc["id"]
            name = loc["name"]
            lat = loc["latitude"]
            lon = loc["longitude"]
            rad = loc["radius_km"]
            
            # Check last execution
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT created_at FROM risk_assessments 
                WHERE location_name = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (name,))
            last_run = cursor.fetchone()
            conn.close()
            
            should_run = False
            if not last_run:
                should_run = True
            else:
                last_dt = datetime.strptime(last_run[0], "%Y-%m-%d %H:%M:%S")
                elapsed = (now - last_dt).total_seconds()
                if elapsed >= MODEL_INTERVAL:
                    should_run = True
            
            if should_run:
                log_system_event("INFO", f"Scheduler: starting surveillance run for {name}.", location=name, stage="scheduler_run")
                try:
                    start_time = time.time()
                    
                    # Run the live pipeline (preserves 100% of existing logic)
                    res = run_live_pipeline(lat=lat, lon=lon, radius_km=rad, location_name=name)
                    
                    inference_time_ms = (time.time() - start_time) * 1000
                    
                    # Extract variables
                    weather = res["weather"]
                    yolo = res["yolo"]
                    phri = res["phri_result"]
                    disease = res["disease_route"]
                    seir = res["seir_result"]
                    bulletin = res["bulletin"]
                    meta = res.get("latest_meta") or {}
                    
                    # 1. Insert into risk_assessments
                    import json
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
                        name, lat, lon, phri.phri_score, phri.risk_level, disease.primary_bucket, disease.meta.get("label", "—"),
                        phri.confidence, 1 if phri.visual_complete else 0, 1 if phri.weather_complete else 0,
                        seir.peak_cases, seir.peak_day, seir.total_projected, seir.attack_rate_pct, seir.beta_effective,
                        bulletin.headline, bulletin.health_bulletin, json.dumps(list(bulletin.action_items)),
                        bulletin.officer_note, meta.get("rgb_path"), meta.get("ndwi_png_path")
                    ))
                    
                    # 2. Insert into environmental_observations
                    cursor.execute("""
                        INSERT INTO environmental_observations (
                            location_name, lat, lon, temperature_2m_c, relative_humidity_pct, precipitation_imerg_mm,
                            dew_frost_point_c, wind_speed_10m_ms, all_sky_insolation_clearness, stagnant_water_count,
                            stagnant_water_area_px, garbage_count, vegetation_anomaly_score, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name, lat, lon, weather.get("temperature_2m_c"), weather.get("relative_humidity_pct"),
                        weather.get("precipitation_imerg_mm"), weather.get("dew_frost_point_c"), weather.get("wind_speed_10m_ms"),
                        weather.get("all_sky_insolation_clearness"), yolo.get("stagnant_water_count"),
                        yolo.get("stagnant_water_area_px"), yolo.get("garbage_count"), yolo.get("vegetation_anomaly_score"),
                        "live_pipeline"
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    # 3. Evaluate Alerts
                    self.alert_engine.evaluate_location_risk(
                        location_name=name,
                        lat=lat,
                        lon=lon,
                        phri_score=phri.phri_score,
                        disease_bucket=disease.primary_bucket,
                        disease_label=disease.meta.get("label", "—"),
                        weather_dict=weather,
                        yolo_dict=yolo
                    )
                    
                    log_system_event(
                        "INFO",
                        f"Scheduler: successfully completed surveillance for {name} (PHRI={phri.phri_score:.2f}).",
                        location=name, stage="scheduler_run", inference_time=inference_time_ms
                    )
                    
                except Exception as e:
                    import traceback
                    log_system_event(
                        "ERROR",
                        f"Scheduler failed for {name}: {e}",
                        location=name, stage="scheduler_run", error_details=traceback.format_exc()
                    )

def _worker_loop():
    scheduler = BackgroundScheduler()
    print(f"[Scheduler] Background surveillance worker thread started. Sync interval: {ALERT_CHECK_INTERVAL}s")
    
    while not _stop_event.is_set():
        try:
            scheduler.run_surveillance_cycle()
        except Exception as e:
            print(f"[Scheduler Loop Error] {e}")
            
        # Sleep in increments of 1s to respond fast to stop signals
        for _ in range(ALERT_CHECK_INTERVAL):
            if _stop_event.is_set():
                break
            time.sleep(1)

def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        print("[Scheduler] Already running.")
        return
        
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_worker_loop, daemon=True)
    _scheduler_thread.start()

def stop_scheduler():
    global _scheduler_thread
    if _scheduler_thread is None:
        return
        
    print("[Scheduler] Stopping background thread...")
    _stop_event.set()
    _scheduler_thread.join(timeout=5)
    _scheduler_thread = None
    print("[Scheduler] Background thread stopped.")
