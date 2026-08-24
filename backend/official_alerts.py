# backend/official_alerts.py
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from database import get_connection, log_system_event

def fetch_and_sync_official_alerts():
    """
    Tries to fetch the latest alerts from IMD or NDMA SACHET public feeds.
    Falls back to existing DB entries if network is offline or feeds fail.
    """
    # Try fetching a public RSS feed (using a public mock/mirror warning feed as a fallback)
    feed_url = "https://mausam.imd.gov.in/imd_latest/contents/all_india_forcast_rss.xml"
    
    try:
        req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        conn = get_connection()
        cursor = conn.cursor()
        
        count = 0
        for item in root.findall(".//item"):
            title = item.find("title").text or "Weather Advisory"
            desc = item.find("description").text or "No details available."
            pub_date = item.find("pubDate").text
            
            # Simple deduplication based on title + publish date
            cursor.execute("SELECT id FROM official_alerts WHERE title = ? AND message = ?", (title, desc))
            if not cursor.fetchone():
                severity = "HIGH" if any(w in title.upper() or w in desc.upper() for w in ["HEAVY", "SEVERE", "EXTREME", "ALERT"]) else "MODERATE"
                cursor.execute("""
                    INSERT INTO official_alerts (title, message, severity, location, latitude, longitude, source, source_type, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title, desc, severity, "All India", 20.5937, 78.9629, 
                    "India Meteorological Department (IMD)", "official", 
                    (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
                ))
                count += 1
                
        if count > 0:
            conn.commit()
            log_system_event("INFO", f"Synced {count} official alerts from IMD RSS.", stage="official_alerts")
        conn.close()
    except Exception as e:
        log_system_event(
            "WARNING", 
            f"IMD/SACHET Live sync skipped: {e}. Relying on stored alerts.",
            stage="official_alerts"
        )
        
    return get_active_official_alerts()

def inject_mock_official_alert(title, message, severity, location, lat=None, lon=None, source="NDMA / SACHET"):
    """Manually insert an official warning (used for demos and administrative purposes)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        expires_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO official_alerts (title, message, severity, location, latitude, longitude, source, source_type, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, message, severity, location, lat, lon, source, "official", expires_at))
        conn.commit()
        conn.close()
        log_system_event("INFO", f"Injected mock official alert: {title} for {location}", stage="official_alerts")
        return True
    except Exception as e:
        log_system_event("ERROR", f"Failed to inject mock official alert: {e}", stage="official_alerts")
        return False

def get_active_official_alerts(location_name=None):
    """Retrieve active warnings from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM official_alerts WHERE status = 'active' AND (expires_at IS NULL OR expires_at > datetime('now'))"
    params = []
    
    if location_name:
        # Check matching location names or sub-strings
        query += " AND (location LIKE ? OR location = 'All India')"
        params.append(f"%{location_name}%")
        
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

def expire_old_official_alerts():
    """Marks expired alerts as inactive."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE official_alerts SET status = 'expired' WHERE expires_at < datetime('now') AND status = 'active'")
        conn.commit()
        conn.close()
    except Exception as e:
         log_system_event("ERROR", f"Failed to expire old official alerts: {e}", stage="official_alerts")
