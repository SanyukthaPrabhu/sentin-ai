# backend/database.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date

DB_PATH = Path(__file__).resolve().parent / "sentin_ai.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Pre-seed a default admin: admin@sentin.ai / admin123
    cursor.execute("SELECT id FROM users WHERE email = 'admin@sentin.ai'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
            ("admin@sentin.ai", "pbkdf2:sha256:admin_placeholder_hash", 1)
        )
    
    # 2. locations (configured for background monitoring)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        radius_km REAL DEFAULT 5.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Pre-seed default cities
    default_locations = [
        ("Bengaluru, Karnataka", 12.98, 77.58, 5.0),
        ("Mumbai, Maharashtra", 19.07, 72.87, 5.0),
        ("Chennai, Tamil Nadu", 13.08, 80.27, 5.0),
        ("Kolkata, West Bengal", 22.57, 88.36, 5.0),
        ("New Delhi, Delhi", 28.61, 77.20, 5.0),
        ("Hyderabad, Telangana", 17.38, 78.48, 5.0),
        ("Pune, Maharashtra", 18.52, 73.85, 5.0),
        ("Ahmedabad, Gujarat", 23.02, 72.57, 5.0),
        ("Jaipur, Rajasthan", 26.91, 75.78, 5.0),
        ("Lucknow, Uttar Pradesh", 26.84, 80.94, 5.0),
        ("Guwahati, Assam", 26.14, 91.73, 5.0),
        ("Kochi, Kerala", 9.93, 76.27, 5.0),
        ("Srinagar, Jammu & Kashmir", 34.08, 74.79, 5.0),
        ("Bhopal, Madhya Pradesh", 23.25, 77.41, 5.0),
        ("Bhubaneswar, Odisha", 20.29, 85.82, 5.0),
        ("Patna, Bihar", 25.59, 85.13, 5.0)
    ]
    for name, lat, lon, rad in default_locations:
        cursor.execute("SELECT id FROM locations WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO locations (name, latitude, longitude, radius_km) VALUES (?, ?, ?, ?)",
                (name, lat, lon, rad)
            )

    # 3. risk_assessments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS risk_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        phri_score REAL NOT NULL,
        risk_level TEXT NOT NULL,
        disease_bucket TEXT NOT NULL,
        disease_label TEXT NOT NULL,
        confidence REAL NOT NULL,
        visual_complete INTEGER NOT NULL,
        weather_complete INTEGER NOT NULL,
        peak_cases REAL,
        peak_day INTEGER,
        total_projected REAL,
        attack_rate_pct REAL,
        beta_effective REAL,
        bulletin_headline TEXT,
        bulletin_text TEXT,
        action_items TEXT, -- JSON array
        officer_note TEXT,
        rgb_path TEXT,
        ndwi_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 4. environmental_observations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS environmental_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        temperature_2m_c REAL,
        relative_humidity_pct REAL,
        precipitation_imerg_mm REAL,
        dew_frost_point_c REAL,
        wind_speed_10m_ms REAL,
        all_sky_insolation_clearness REAL,
        stagnant_water_count INTEGER,
        stagnant_water_area_px REAL,
        garbage_count INTEGER,
        vegetation_anomaly_score REAL,
        source TEXT NOT NULL, -- e.g. "live_pipeline", "manual", "historical"
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 5. official_alerts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS official_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT NOT NULL, -- e.g. "MODERATE", "HIGH", "CRITICAL"
        location TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        source TEXT NOT NULL, -- e.g. "NDMA / SACHET", "IMD"
        source_type TEXT NOT NULL, -- e.g. "official"
        status TEXT DEFAULT 'active', -- active, expired
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP
    )
    """)
    
    # 6. ai_alerts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT NOT NULL,
        phri_score REAL NOT NULL,
        status TEXT DEFAULT 'active', -- active, expired, resolved
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP
    )
    """)
    
    # 7. subscriptions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        phone TEXT,
        location_name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        all_alerts INTEGER DEFAULT 1,
        environmental_alerts INTEGER DEFAULT 0,
        disease_risk_alerts INTEGER DEFAULT 0,
        weather_alerts INTEGER DEFAULT 0,
        official_disaster_alerts INTEGER DEFAULT 0,
        severity_preference TEXT DEFAULT 'HIGH', -- MODERATE, HIGH, CRITICAL
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 8. notifications queue
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL, -- e.g. "AI_ALERT", "OFFICIAL_ALERT"
        subscription_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'pending', -- pending, sent, failed
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
    )
    """)
    
    # 9. notification_logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notification_id INTEGER,
        channel TEXT NOT NULL, -- "email", "sms", "whatsapp", "telegram"
        status TEXT NOT NULL, -- "success", "failed"
        error_message TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (notification_id) REFERENCES notifications(id)
    )
    """)
    
    # 10. awareness_content
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS awareness_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Seed default awareness categories if empty
    cursor.execute("SELECT COUNT(*) FROM awareness_content")
    if cursor.fetchone()[0] == 0:
        seed_awareness_content(cursor)
        
    # 11. system_logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        request_id TEXT,
        location TEXT,
        stage TEXT,
        model_inference_time_ms REAL,
        api_latency_ms REAL,
        level TEXT NOT NULL, -- INFO, WARNING, ERROR
        message TEXT NOT NULL,
        error_details TEXT
    )
    """)
    
    # 12. telegram_users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telegram_users (
        chat_id TEXT PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    print("[DB] SQLite database initialized and pre-seeded.")

def seed_awareness_content(cursor):
    content = [
        ("flood", "Flood Safety & Survival Guide", 
         "Heavy monsoon rains can lead to flash flooding. Avoid walking or driving through flood waters. Stagnant water left behind causes severe disease risk."),
        ("urban_flood", "Urban Flooding & Clogged Drains", 
         "Concrete structures reduce water absorption. Keep neighborhood storm drains clear of plastic waste and garbage to prevent rapid local flooding."),
        ("heavy_rainfall", "Heavy Rainfall Warnings", 
         "Intense precipitation is an early warning indicator. Accumulation causes water logging, creating prime breeding grounds for vector mosquitoes."),
        ("heat_wave", "Heat Wave & Dehydration Protection", 
         "Extreme heat waves can lead to heat stroke. Stay indoors between 12 PM and 3 PM, drink plenty of water, and wear light clothing."),
        ("lightning", "Lightning & Severe Storm Safety", 
         "During thunderstorms, stay indoors. If outdoors, avoid tall trees, metal poles, and open fields. Unplug sensitive home electronics."),
        ("landslide", "Landslide Warning Signs & Evacuation", 
         "Hillside soil saturation from continuous rainfall triggers landslides. Watch for tilted trees, new soil cracks, or sudden mud flows."),
        ("mosquito_borne", "Vector-Borne Disease Control", 
         "Dengue, Malaria, and Chikungunya spread via vector mosquitoes. Prevent standing water in tires, coolers, pots, and cover water storage."),
        ("stagnant_water", "Stagnant Water Remediation", 
         "Even a small puddle can breed thousands of mosquitoes. Use larvicides or drain standing water weekly. Report municipal blocked drains."),
        ("water_contamination", "Water Contamination & Cholera Prevention", 
         "Flooded pipelines mix sewage with drinking water. Always boil or chlorinate municipal water. Avoid street food after flooding.")
    ]
    for cat, title, desc in content:
        cursor.execute(
            "INSERT OR IGNORE INTO awareness_content (category, title, description) VALUES (?, ?, ?)",
            (cat, title, desc)
        )

# ── LOGGING UTILITIES ────────────────────────────────────────────────────────
def log_system_event(level, message, request_id=None, location=None, stage=None, inference_time=None, latency=None, error_details=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_logs (level, message, request_id, location, stage, model_inference_time_ms, api_latency_ms, error_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (level, message, request_id, location, stage, inference_time, latency, error_details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB LOG ERROR] Failed to log system event: {e}")

# Call init_db at module import time to ensure the database structure is ready
try:
    init_db()
except Exception as e:
    print(f"[DB ERROR] Error during database initialization: {e}")
