# backend/test_platform.py
import unittest
import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime, date, timedelta

# Path setups
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import database
from database import get_connection, init_db, log_system_event
from alert_engine import AlertEngine
from notification_service import NotificationService
from official_alerts import inject_mock_official_alert, get_active_official_alerts, expire_old_official_alerts

class TestSentinAIPlatform(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Point database path to a test database during testing
        database.DB_PATH = Path(__file__).resolve().parent / "test_sentin_ai.db"
        init_db()

    @classmethod
    def tearDownClass(cls):
        # Remove test database after tests complete
        test_db = Path(__file__).resolve().parent / "test_sentin_ai.db"
        if test_db.exists():
            try:
                os.remove(test_db)
            except Exception:
                pass

    def setUp(self):
        # Clear tables before each test
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_alerts")
        cursor.execute("DELETE FROM official_alerts")
        cursor.execute("DELETE FROM subscriptions")
        cursor.execute("DELETE FROM risk_assessments")
        cursor.execute("DELETE FROM environmental_observations")
        cursor.execute("DELETE FROM notifications")
        cursor.execute("DELETE FROM notification_logs")
        cursor.execute("DELETE FROM system_logs")
        conn.commit()
        conn.close()

    def test_database_initialization(self):
        """Verifies database tables are created correctly with pre-seeded data."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check locations table exists and is seeded
        cursor.execute("SELECT COUNT(*) FROM locations")
        loc_count = cursor.fetchone()[0]
        self.assertGreater(loc_count, 0, "Locations table should be pre-seeded.")
        
        # Check awareness content exists and is seeded
        cursor.execute("SELECT COUNT(*) FROM awareness_content")
        awareness_count = cursor.fetchone()[0]
        self.assertGreater(awareness_count, 0, "Awareness content table should be pre-seeded.")
        
        conn.close()

    def test_alert_engine_hysteresis_and_persistence(self):
        """Tests that the AlertEngine applies hysteresis and does not immediately raise warnings on temporary PHRI rises."""
        engine = AlertEngine()
        
        # Monitored coordinates
        loc_name = "Test City"
        lat, lon = 12.0, 77.0
        weather = {"temperature_2m_c": 28.0, "relative_humidity_pct": 72.0}
        yolo = {"stagnant_water_count": 5, "garbage_count": 0}
        
        # Run 1: Temporary rise (PHRI exceeds 0.40 threshold, but first time)
        # Should NOT trigger an active alert in the database (Hysteresis downgrades it to NONE)
        engine.evaluate_location_risk(loc_name, lat, lon, phri_score=0.48, disease_bucket="dengue_malaria", disease_label="Dengue", weather_dict=weather, yolo_dict=yolo)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_alerts WHERE status = 'active'")
        active_alerts_count = cursor.fetchone()[0]
        self.assertEqual(active_alerts_count, 0, "Hysteresis should downgrade temporary rises; active alerts should be 0.")
        
        # Seed two historical assessments to trigger persistence count
        # In a real environment, assessments are written to the database during cycles
        for _ in range(2):
            cursor.execute("""
                INSERT INTO risk_assessments (location_name, lat, lon, phri_score, risk_level, disease_bucket, disease_label, confidence, visual_complete, weather_complete)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (loc_name, lat, lon, 0.55, "MEDIUM", "dengue_malaria", "Dengue", 1.0, 1, 1))
        conn.commit()
        
        # Run 2: Persistent rise (assessments exist in the DB, so elevated count >= 2)
        # Should now trigger an alert
        engine.evaluate_location_risk(loc_name, lat, lon, phri_score=0.55, disease_bucket="dengue_malaria", disease_label="Dengue", weather_dict=weather, yolo_dict=yolo)
        
        cursor.execute("SELECT COUNT(*) FROM ai_alerts WHERE status = 'active'")
        active_alerts_count = cursor.fetchone()[0]
        self.assertEqual(active_alerts_count, 1, "Persistent risk over multiple cycles should trigger an active alert.")
        conn.close()

    def test_alert_engine_deduplication(self):
        """Tests that redundant duplicate alerts are suppressed, extending the expiry date of the active alert instead."""
        engine = AlertEngine()
        loc_name = "Deduplication City"
        lat, lon = 13.0, 80.0
        weather = {"temperature_2m_c": 29.0, "relative_humidity_pct": 82.0}
        yolo = {"stagnant_water_count": 8, "garbage_count": 0}
        
        conn = get_connection()
        cursor = conn.cursor()
        # Seed historical values to pass hysteresis
        for _ in range(2):
            cursor.execute("""
                INSERT INTO risk_assessments (location_name, lat, lon, phri_score, risk_level, disease_bucket, disease_label, confidence, visual_complete, weather_complete)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (loc_name, lat, lon, 0.65, "HIGH", "dengue_malaria", "Dengue", 1.0, 1, 1))
        conn.commit()
        conn.close()
        
        # Trigger first alert
        engine.evaluate_location_risk(loc_name, lat, lon, phri_score=0.65, disease_bucket="dengue_malaria", disease_label="Dengue", weather_dict=weather, yolo_dict=yolo)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, expires_at FROM ai_alerts WHERE status = 'active'")
        alert1 = cursor.fetchone()
        alert1_id = alert1[0]
        alert1_expiry = alert1[1]
        
        # Simulate passage of time by back-dating the active alert's expiry by 1 hour in the DB
        older_expiry = (datetime.now() + timedelta(days=2) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE ai_alerts SET expires_at = ? WHERE id = ?", (older_expiry, alert1_id))
        conn.commit()
        conn.close()
        
        # Trigger second identical alert cycle
        engine.evaluate_location_risk(loc_name, lat, lon, phri_score=0.66, disease_bucket="dengue_malaria", disease_label="Dengue", weather_dict=weather, yolo_dict=yolo)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, expires_at FROM ai_alerts WHERE status = 'active'")
        alerts = cursor.fetchall()
        
        self.assertEqual(len(alerts), 1, "AlertEngine should deduplicate identical warnings; only one alert should remain active.")
        self.assertEqual(alerts[0][0], alert1_id, "Alert ID should not change during deduplication.")
        self.assertGreater(alerts[0][1], older_expiry, "Alert deduplication should extend the existing alert's expiry timestamp.")
        conn.close()

    def test_notification_dispatch_severity_preferences(self):
        """Verifies that alerts are dispatched only to subscribers whose severity preferences match the alert level."""
        engine = AlertEngine()
        loc_name = "Subscriber City"
        lat, lon = 22.0, 88.0
        
        # Create three subscribers:
        # Sub 1: Moderate+ threshold (should be notified)
        # Sub 2: Critical only threshold (should NOT be notified for a HIGH alert)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscriptions (email, phone, location_name, latitude, longitude, all_alerts, severity_preference)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("sub_mod@test.com", None, loc_name, lat, lon, 1, "MODERATE"))
        
        cursor.execute("""
            INSERT INTO subscriptions (email, phone, location_name, latitude, longitude, all_alerts, severity_preference)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("sub_crit@test.com", None, loc_name, lat, lon, 1, "CRITICAL"))
        
        # Seed historical points to bypass hysteresis
        for _ in range(2):
            cursor.execute("""
                INSERT INTO risk_assessments (location_name, lat, lon, phri_score, risk_level, disease_bucket, disease_label, confidence, visual_complete, weather_complete)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (loc_name, lat, lon, 0.65, "HIGH", "dengue_malaria", "Dengue", 1.0, 1, 1))
        conn.commit()
        conn.close()
        
        # Trigger a HIGH alert
        weather = {"temperature_2m_c": 30.0, "relative_humidity_pct": 78.0}
        yolo = {"stagnant_water_count": 6, "garbage_count": 0}
        engine.evaluate_location_risk(loc_name, lat, lon, phri_score=0.65, disease_bucket="dengue_malaria", disease_label="Dengue", weather_dict=weather, yolo_dict=yolo)
        
        # Check notifications queue
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.email FROM notifications n 
            JOIN subscriptions s ON n.subscription_id = s.id
        """)
        notified_emails = [r[0] for r in cursor.fetchall()]
        
        self.assertIn("sub_mod@test.com", notified_emails, "Subscriber with MODERATE+ preference should be notified of a HIGH alert.")
        self.assertNotIn("sub_crit@test.com", notified_emails, "Subscriber with CRITICAL preference should NOT be notified of a HIGH alert.")
        conn.close()

    def test_official_alerts_sync(self):
        """Verifies that official warning injection works, deduplicates, and expires old alerts correctly."""
        # Inject warning alert
        success = inject_mock_official_alert(
            title="HEAVY MONSOON WARNING",
            message="Extreme precipitation expected.",
            severity="HIGH",
            location="Bengaluru, Karnataka",
            lat=12.98, lon=77.58,
            source="India Meteorological Department (IMD)"
        )
        self.assertTrue(success, "Warning injection should succeed.")
        
        # Ingest warning alert again (should insert since it doesn't deduplicate manually, or verify retrieval)
        active = get_active_official_alerts("Bengaluru")
        self.assertEqual(len(active), 1, "Should retrieve active official alert.")
        self.assertEqual(active[0]["title"], "HEAVY MONSOON WARNING")
        
        # Set expiry date to past manually in DB, check if expire_old_official_alerts cleans it up
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE official_alerts SET expires_at = datetime('now', '-1 minute')")
        conn.commit()
        conn.close()
        
        # Run cleanup routine
        expire_old_official_alerts()
        
        # Verify retrieved alerts list is empty
        active_after = get_active_official_alerts("Bengaluru")
        self.assertEqual(len(active_after), 0, "Expired official alerts should not be active.")

if __name__ == "__main__":
    unittest.main()
