# backend/alert_engine.py
import os
from datetime import datetime, timedelta
from database import get_connection, log_system_event
from notification_service import NotificationService

# Minimum hours between repeated Telegram alerts for the same location (avoids spam)
TELEGRAM_COOLDOWN_HOURS = int(os.getenv("TELEGRAM_COOLDOWN_HOURS", 4))

class AlertEngine:
    def __init__(self):
        self.notification_service = NotificationService()

    def evaluate_location_risk(self, location_name: str, lat: float, lon: float, phri_score: float, disease_bucket: str, disease_label: str, weather_dict: dict, yolo_dict: dict):
        """
        Main entry point for Alert Engine.
        Executes hysteresis checks, creates/resolves alerts, deduplicates alerts, 
        and dispatches subscriber notifications.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # ── 1. Hysteresis / Persistence Checking ──────────────────────────────
        # Fetch the last 3 risk assessments for this location to verify persistence
        cursor.execute("""
            SELECT phri_score FROM risk_assessments 
            WHERE location_name = ? 
            ORDER BY created_at DESC LIMIT 3
        """, (location_name,))
        rows = cursor.fetchall()
        recent_scores = [r[0] for r in rows]
        
        # Add the current score if it's not yet in the DB
        recent_scores = [phri_score] + recent_scores
        recent_scores = recent_scores[:3] # keep last 3
        
        # Hysteresis rules:
        # - Temporary rise: PHRI is high now, but wasn't before, and no supporting evidence -> dashboard update only.
        # - Persistence: PHRI remains elevated (>0.40) over at least 2 of the last 3 checks.
        elevated_count = sum(1 for s in recent_scores if s >= 0.40)
        
        target_severity = "NONE"
        if phri_score >= 0.75:
            target_severity = "CRITICAL"
        elif phri_score >= 0.60:
            target_severity = "HIGH"
        elif phri_score >= 0.40:
            target_severity = "MODERATE"
            
        # Apply hysteresis filter: if target is elevated but has no persistent elevation, downgrade severity
        if target_severity in ["MODERATE", "HIGH", "CRITICAL"] and elevated_count < 2:
            # Upgrade is too fast/unstable. Update dashboard but keep alert state at a lower level
            log_system_event(
                "INFO",
                f"Hysteresis active for {location_name}: PHRI is {phri_score:.2f} but persistence count is {elevated_count}/3. Alert propagation delayed.",
                location=location_name, stage="alert_evaluation"
            )
            # Downgrade alert for safety (dashboard will still show high PHRI)
            if target_severity == "CRITICAL":
                target_severity = "HIGH"
            elif target_severity == "HIGH":
                target_severity = "MODERATE"
            else:
                target_severity = "NONE"

        # ── 2. Deduplication & Alert Management ───────────────────────────────
        # Fetch current active AI Alert for this location
        cursor.execute("""
            SELECT * FROM ai_alerts 
            WHERE location_name = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        """, (location_name,))
        active_alert_row = cursor.fetchone()
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expires_at = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        
        if target_severity == "NONE":
            # If there's an active alert, resolve it
            if active_alert_row:
                cursor.execute("""
                    UPDATE ai_alerts 
                    SET status = 'resolved', expires_at = ?
                    WHERE id = ?
                """, (now_str, active_alert_row["id"]))
                conn.commit()
                log_system_event(
                    "INFO", 
                    f"Resolved active alert #{active_alert_row['id']} for {location_name} (PHRI fell to safe level).",
                    location=location_name, stage="alert_evaluation"
                )
            conn.close()
            return
            
        # Compile alert details
        title = f"{target_severity} Outbreak Risk Advisory: {disease_label}"
        message = (
            f"Sentin-AI has detected elevated risk indicators for vector/pathogen propagation in {location_name}.\n\n"
            f"PHRI Score: {phri_score:.2f}\n"
            f"Environmental Triggers:\n"
        )
        if yolo_dict.get("stagnant_water_count", 0) > 0:
            message += f"- Stagnant water detected: {yolo_dict.get('stagnant_water_count')} site(s).\n"
        if yolo_dict.get("garbage_count", 0) > 0:
            message += f"- Garbage accumulation detected: {yolo_dict.get('garbage_count')} site(s).\n"
        if yolo_dict.get("vegetation_anomaly_score", 0) > 0.3:
            message += f"- Vegetation stress/anomaly: {yolo_dict.get('vegetation_anomaly_score'):.2f}.\n"
        message += (
            f"- Temperature: {weather_dict.get('temperature_2m_c', 0)}°C, Humidity: {weather_dict.get('relative_humidity_pct', 0)}%.\n\n"
            f"Recommended Actions:\n"
            f"1. Eliminate any standing water in flower pots, tires, and containers.\n"
            f"2. Ensure trash is covered and disposed of safely.\n"
            f"3. Refer to local health advisories for protective measures."
        )

        should_notify = False
        alert_id = None
        
        if not active_alert_row:
            # Create a brand new alert
            cursor.execute("""
                INSERT INTO ai_alerts (location_name, latitude, longitude, title, message, severity, phri_score, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (location_name, lat, lon, title, message, target_severity, phri_score, expires_at))
            alert_id = cursor.lastrowid
            conn.commit()
            should_notify = True
            log_system_event("INFO", f"Created new {target_severity} alert #{alert_id} for {location_name}", location=location_name, stage="alert_generation")
        else:
            # Active alert exists. Check if we need to escalate or modify
            old_severity = active_alert_row["severity"]
            old_title = active_alert_row["title"]
            
            # Helper to map severity to index for easy comparison
            sev_rank = {"MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
            
            if sev_rank.get(target_severity, 0) > sev_rank.get(old_severity, 0):
                # Severity increased -> Escalate! Expire old and create new
                cursor.execute("UPDATE ai_alerts SET status = 'expired' WHERE id = ?", (active_alert_row["id"],))
                cursor.execute("""
                    INSERT INTO ai_alerts (location_name, latitude, longitude, title, message, severity, phri_score, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (location_name, lat, lon, title, message, target_severity, phri_score, expires_at))
                alert_id = cursor.lastrowid
                conn.commit()
                should_notify = True
                log_system_event(
                    "INFO", 
                    f"Escalated alert #{active_alert_row['id']} ({old_severity}) to #{alert_id} ({target_severity}) in {location_name}.",
                    location=location_name, stage="alert_generation"
                )
            elif old_title != title:
                # Severity matches but disease bucket or details changed significantly -> create new alert
                cursor.execute("UPDATE ai_alerts SET status = 'expired' WHERE id = ?", (active_alert_row["id"],))
                cursor.execute("""
                    INSERT INTO ai_alerts (location_name, latitude, longitude, title, message, severity, phri_score, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (location_name, lat, lon, title, message, target_severity, phri_score, expires_at))
                alert_id = cursor.lastrowid
                conn.commit()
                should_notify = True
                log_system_event(
                    "INFO", 
                    f"Re-issued alert due to core changes: #{alert_id} in {location_name}", 
                    location=location_name, stage="alert_generation"
                )
            else:
                # Deduplicated. Just extend expiry timestamp of the current alert, no duplicate notifications
                cursor.execute("UPDATE ai_alerts SET expires_at = ? WHERE id = ?", (expires_at, active_alert_row["id"]))
                conn.commit()
                alert_id = active_alert_row["id"]
                log_system_event(
                    "INFO", 
                    f"Deduplicated alert for {location_name}: extended expiry for alert #{alert_id}.",
                    location=location_name, stage="alert_generation"
                )

        # ── 3. Telegram Broadcast (fires on new AND ongoing alerts, with cooldown) ────
        # Check cooldown: read last Telegram notification time for this location from system_logs
        try:
            cooldown_conn = get_connection()
            cooldown_cursor = cooldown_conn.cursor()
            cooldown_cursor.execute("""
                SELECT timestamp FROM system_logs
                WHERE stage = 'telegram_sent' AND location = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (location_name,))
            last_tg_row = cooldown_cursor.fetchone()
            cooldown_conn.close()

            tg_ok_to_send = True
            if last_tg_row:
                last_tg_dt = datetime.strptime(last_tg_row[0], "%Y-%m-%d %H:%M:%S")
                hours_since = (datetime.now() - last_tg_dt).total_seconds() / 3600
                if hours_since < TELEGRAM_COOLDOWN_HOURS:
                    tg_ok_to_send = False
                    log_system_event(
                        "INFO",
                        f"Telegram cooldown active for {location_name}: last sent {hours_since:.1f}h ago (cooldown={TELEGRAM_COOLDOWN_HOURS}h).",
                        location=location_name, stage="notification_dispatch"
                    )

            if tg_ok_to_send and alert_id:
                from notification_service import TelegramProvider
                tg = TelegramProvider()
                tg_success, tg_msg = tg.send(recipient="", title=title, message=message)
                if tg_success:
                    # Record the send time so cooldown works on next run
                    log_system_event(
                        "INFO",
                        f"Telegram broadcast sent: {tg_msg}",
                        location=location_name, stage="telegram_sent"
                    )
                else:
                    log_system_event(
                        "ERROR",
                        f"Telegram broadcast failed: {tg_msg}",
                        location=location_name, stage="notification_dispatch"
                    )
        except Exception as tg_err:
            log_system_event(
                "ERROR",
                f"Telegram broadcast exception: {tg_err}",
                location=location_name, stage="notification_dispatch"
            )

        # ── 4. Notify email/SMS/WhatsApp subscribers (new alerts only) ───────
        if should_notify and alert_id:
            cursor.execute("""
                SELECT id, email, phone, all_alerts, environmental_alerts, disease_risk_alerts, weather_alerts, official_disaster_alerts, severity_preference 
                FROM subscriptions 
                WHERE location_name = ? OR location_name = 'All India'
            """, (location_name,))
            subs_rows = cursor.fetchall()
            subs = [dict(r) for r in subs_rows]
            conn.close()

            sev_rank = {"MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
            alert_rank = sev_rank.get(target_severity, 0)

            for sub in subs:
                sub_pref_rank = sev_rank.get(sub["severity_preference"], 2) # default to HIGH

                # Check if alert matches user severity preference
                if alert_rank >= sub_pref_rank:
                    pref_dict = {
                        "all_alerts": sub["all_alerts"],
                        "environmental_alerts": sub["environmental_alerts"],
                        "disease_risk_alerts": sub["disease_risk_alerts"],
                        "weather_alerts": sub["weather_alerts"],
                        "official_disaster_alerts": sub["official_disaster_alerts"]
                    }
                    self.notification_service.dispatch_alert(
                        subscription_id=sub["id"],
                        recipient_email=sub["email"],
                        recipient_phone=sub["phone"],
                        alert_title=title,
                        alert_message=message,
                        pref=pref_dict
                    )
        else:
            conn.close()
