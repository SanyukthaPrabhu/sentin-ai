import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { MapMarker } from '../api';

interface Props {
  markers: MapMarker[];
  onSelectLocation: (location: { name: string; lat: number; lon: number }) => void;
}

export default function InteractiveMap({ markers, onSelectLocation }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersGroupRef = useRef<any>(null);
  const [leafletLoaded, setLeafletLoaded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // ── 1. Dynamic CDN Loading ──────────────────────────────────────────────────
  useEffect(() => {
    // Check if Leaflet is already loaded
    if ((window as any).L) {
      setLeafletLoaded(true);
      return;
    }

    // Append CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    link.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
    link.crossOrigin = '';
    document.head.appendChild(link);

    // Append JS
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
    script.crossOrigin = '';
    script.onload = () => setLeafletLoaded(true);
    document.body.appendChild(script);

    return () => {
      // We don't remove scripts to avoid reloading if they switch tabs
    };
  }, []);

  // ── 2. Initialize Map Instance ──────────────────────────────────────────────
  useEffect(() => {
    if (!leafletLoaded || !mapContainerRef.current) return;

    const L = (window as any).L;
    if (!L) return;

    // Destroy existing instance if any
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    // Create Map (Centered over India by default)
    const map = L.map(mapContainerRef.current).setView([20.5937, 78.9629], 5);
    mapInstanceRef.current = map;

    // Load Sleek Dark Mode Tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    // Layer group for markers
    markersGroupRef.current = L.layerGroup().addTo(map);

    // Resize map when element changes size
    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
    });
    resizeObserver.observe(mapContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [leafletLoaded]);

  // ── 3. Populate Map Markers ─────────────────────────────────────────────────
  useEffect(() => {
    if (!leafletLoaded || !mapInstanceRef.current || !markersGroupRef.current) return;

    const L = (window as any).L;
    if (!L) return;

    // Clear old markers
    markersGroupRef.current.clearLayers();

    markers.forEach(marker => {
      const isOfficial = marker.type === 'official_alert';
      
      let color = 'var(--cyan)';
      let radius = 10;
      let fillOpacity = 0.5;

      if (isOfficial) {
        // Official warnings are red and double sized
        color = 'var(--red)';
        radius = 16;
        fillOpacity = 0.7;
      } else {
        // AI Risk Levels
        const sev = marker.severity?.toUpperCase();
        if (sev === 'LOW') color = 'var(--green)';
        else if (sev === 'MEDIUM' || sev === 'MODERATE') color = 'var(--amber)';
        else if (sev === 'HIGH') color = '#f97316';
        else if (sev === 'CRITICAL') color = 'var(--red)';
        
        radius = 12;
      }

      // Draw vector circle
      const mapCircle = L.circleMarker([marker.lat, marker.lon], {
        radius: radius,
        fillColor: color,
        color: color,
        weight: 2,
        opacity: 0.9,
        fillOpacity: fillOpacity
      });

      // Build Interactive Popup Content
      let popupContent = `
        <div style="font-family: 'DM Sans', sans-serif; color: #1e293b; min-width: 220px; padding: 4px;">
          <h4 style="margin: 0 0 6px 0; font-size: 14px; font-weight: 700; color: ${isOfficial ? 'var(--red)' : '#0f172a'};">
            ${isOfficial ? '🚨 OFFICIAL ALERT' : '🛰️ AI MONITORING ZONE'}
          </h4>
          <h5 style="margin: 0 0 6px 0; font-size: 13px; font-weight: 600;">${marker.name}</h5>
      `;

      if (isOfficial) {
        popupContent += `
          <p style="margin: 0 0 8px 0; font-size: 11px; line-height: 1.4; color: #475569;">${marker.message || ''}</p>
          <div style="font-size: 10px; color: #94a3b8; font-family: monospace;">SOURCE: ${marker.source || 'Authorized Authority'}</div>
        `;
      } else {
        popupContent += `
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px;">
            <span>PHRI Score:</span>
            <span style="font-weight: 700; color: ${color};">${(marker.phri || 0).toFixed(2)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px;">
            <span>Risk Level:</span>
            <span style="font-weight: 700; color: ${color};">${marker.severity}</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 11px;">
            <span>Classification:</span>
            <span style="font-weight: 600;">${marker.disease || 'General'}</span>
          </div>
          <button id="inspect-btn-${marker.lat}-${marker.lon}" style="
            width: 100%; border: none; background: #0284c7; color: white; 
            padding: 6px; border-radius: 4px; font-size: 11px; font-weight: 600; cursor: pointer;
            transition: background 0.2s;
          " onclick="window.onInspectLocation('${marker.name}', ${marker.lat}, ${marker.lon})">
            Analyze Region
          </button>
        `;
      }

      popupContent += `
          <div style="margin-top: 8px; font-size: 9px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 4px;">
            Updated: ${new Date(marker.updated_at).toLocaleDateString()}
          </div>
        </div>
      `;

      mapCircle.bindPopup(popupContent);
      mapCircle.addTo(markersGroupRef.current);
    });

    // Attach global click listener for the inspect button inside popup
    (window as any).onInspectLocation = (name: string, lat: number, lon: number) => {
      onSelectLocation({ name, lat, lon });
    };

  }, [leafletLoaded, markers]);

  // ── 4. Geocode Search Functionality ─────────────────────────────────────────
  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || !mapInstanceRef.current) return;

    try {
      // Nominatim search API
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}`);
      const data = await res.json();
      
      if (data && data.length > 0) {
        const first = data[0];
        const lat = parseFloat(first.lat);
        const lon = parseFloat(first.lon);
        
        // Zoom and fly to coordinate
        mapInstanceRef.current.setView([lat, lon], 12);
        
        // Callback
        onSelectLocation({
          name: first.display_name.split(',')[0],
          lat,
          lon
        });
      } else {
        alert("Location not found.");
      }
    } catch (err) {
      console.error("Geocoding failed: ", err);
    }
  };

  const handleGetCurrentLocation = () => {
    if (!navigator.geolocation || !mapInstanceRef.current) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        mapInstanceRef.current.setView([latitude, longitude], 12);
        onSelectLocation({
          name: "My Location",
          lat: latitude,
          lon: longitude
        });
      },
      (error) => {
        alert(`Error fetching location: ${error.message}`);
      }
    );
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 12, overflow: 'hidden' }}>
      {/* Search overlay panel */}
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 1000,
        display: 'flex', gap: '0.4rem', width: 'calc(100% - 24px)', maxWidth: 420
      }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flex: 1 }}>
          <input
            type="text"
            placeholder="Search address, city, or coordinates..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              flex: 1, padding: '0.55rem 1rem', border: '1px solid var(--border)',
              borderRadius: '8px 0 0 8px', background: 'rgba(17,24,39,0.9)',
              color: 'var(--text-primary)', fontSize: '0.85rem', outline: 'none',
              backdropFilter: 'blur(8px)'
            }}
          />
          <button type="submit" className="btn btn-primary" style={{
            borderRadius: '0 8px 8px 0', padding: '0.55rem 1.1rem',
            fontSize: '0.85rem', border: 'none', fontWeight: 600
          }}>
            🔍 Search
          </button>
        </form>
        
        <button
          onClick={handleGetCurrentLocation}
          className="btn btn-secondary"
          title="Detect My Location"
          style={{
            padding: '0.55rem', border: '1px solid var(--border)', borderRadius: 8,
            background: 'rgba(17,24,39,0.9)', backdropFilter: 'blur(8px)', cursor: 'pointer'
          }}
        >
          📍
        </button>
      </div>

      {/* Map display */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', background: '#0a0e17' }} />

      {!leafletLoaded && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(10,14,23,0.85)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-muted)', fontFamily: 'DM Mono', fontSize: '0.8rem',
          zIndex: 1001
        }}>
          Loading Leaflet Mapping Layer...
        </div>
      )}
    </div>
  );
}
