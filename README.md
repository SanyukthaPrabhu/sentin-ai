# Sentin-AI — Public Health Early Warning System

> **AI-powered proactive disease outbreak monitor using satellite imagery, ML, and epidemiological modelling.**  
> Built for **AI4India / HopeWorks** | Bengaluru, Karnataka

---

## Architecture Overview

```
[Sentinel-2 GEE] ---> [YOLOv8 Segmentation] ---> [LSTM PHRI Engine] ---> [SEIR Model] ---> [Groq LLM Bulletin]
       |                        |                         |                      |
  10m Satellite             Stagnant Water           PHRI Score 0-1        14-day Case        Health Advisory
  RGB + NDWI              Garbage / Veg             (0=Safe, 1=Critical)    Projection        + Newspaper Headline
```

### Layer 1 — The Eye (Perception)
- **Google Earth Engine** — Sentinel-2 optical imagery at 10m resolution
- **Cloud Masking** — QA60 bitmask (bits 10, 11) eliminates cloud pixels
- **NDWI Temporal Differencing** — Distinguishes permanent lakes from new puddles
- **YOLOv8 Instance Segmentation** (`yolov8m-seg.pt`) — Detects environmental risk proxies

### Layer 2 — The Brain (Analytics)
- **Multi-input LSTM** fusing 4 YOLO visual features + 6 weather features (30-day window)
- **PHRI Score** (0.0 – 1.0) — Public Health Risk Index
- **Disease Router** — Maps PHRI + conditions to disease bucket
- **SEIR Model** — 14-day epidemic projection

### Layer 3 — The Voice (Communication)
- **Groq LLM** (`llama-3.3-70b-versatile`) — Generates hyper-local health bulletins
- **Streamlit Dashboard** — Real-time monitoring interface for health officers

---

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/your-org/sentin-ai
cd sentin-ai
pip install -r requirements.txt
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required keys in `.env`:
| Key | Purpose | Get It |
|-----|---------|--------|
| `GROQ_API_KEY` | LLM bulletin generation | https://console.groq.com (free) |
| `OPENWEATHERMAP_API_KEY` | Live weather | https://openweathermap.org/api (free) |
| `GEE_PROJECT_ID` | Satellite imagery | https://earthengine.google.com |

### 3. Authenticate Google Earth Engine (one-time)
```bash
earthengine authenticate
```

### 4. Run the Dashboard

#### React + FastAPI Dashboard (Recommended & Enhanced)
```bash
# Installs backend deps
pip install fastapi uvicorn python-multipart

# Starts backend & React dev server concurrently
python start_dashboard.py
```
Open **http://localhost:5173**

#### Legacy Streamlit Dashboard
```bash
streamlit run dashboard/app.py
```
Open **http://localhost:8501**

---

## LSTM Feature Vector (10 features per timestep, 30-day window)

| # | Feature | Source | Unit |
|---|---------|--------|------|
| 1 | `temperature_2m_c` | OpenWeatherMap / NASA POWER | °C |
| 2 | `relative_humidity_pct` | OpenWeatherMap / NASA POWER | % |
| 3 | `precipitation_imerg_mm` | OpenWeatherMap / NASA POWER | mm/day |
| 4 | `dew_frost_point_c` | Calculated (Magnus-Tetens) | °C |
| 5 | `wind_speed_10m_ms` | OpenWeatherMap / NASA POWER | m/s |
| 6 | `all_sky_insolation_clearness` | NASA POWER | 0–1 index |
| 7 | `stagnant_water_count` | YOLOv8 | count |
| 8 | `stagnant_water_area_px` | YOLOv8 | pixels |
| 9 | `garbage_count` | YOLOv8 | count |
| 10 | `vegetation_anomaly_score` | YOLOv8 + NDWI | 0–1 score |

---

## Build Order

```
Phase 1 — Data Pipeline
  python src/nasa_power_parser.py          # Parse NASA POWER CSV
  python validation/idsp_parser.py         # Parse IDSP PDFs -> CSV

Phase 2 — Core ML
  python src/lstm_model.py --train         # Train LSTM
  # Trained model saved to models/lstm_phri.h5

Phase 3 — Communication
  python src/gemini_voice.py --phri 0.82   # Test Groq bulletin

Phase 4 — Satellite
  python src/gee_pipeline.py               # Download Sentinel-2 scenes
  python src/yolo_inference.py             # Test YOLO detections

Phase 5 — Dashboard
  streamlit run dashboard/app.py           # Launch UI
```

---

## Dashboard Modes

| Mode | Description |
|------|-------------|
| ⚡ Automated Live Pipeline | Fetches live weather + GEE satellite + YOLOv8 + PHRI + Groq AI bulletin |
| 🔴 Manual Real-time | Manually control weather sliders and YOLO features |
| 📅 Historical Scoring | Score any date in 2023–2024 training data |
| 🧪 Stress Test | Sweep PHRI from 0 to 1 and plot SEIR response curve |

---

## NDWI Temporal Differencing

```python
# Distinguishes permanent vs temporary water
ndwi_delta = ndwi_current - ndwi_baseline_prior_year
# +ve delta = new water appeared = flood/stagnation risk
# ~0 delta  = permanent lake/river = no additional risk

pipeline.compute_ndwi_delta(current_date="2026-07-28")
# [NDWI Delta] Current: -0.1556 | Baseline: -0.2100 | Delta: +0.0544 | New water: True
```

---

## SEIR Epidemiological Model

```python
# beta is amplified by PHRI score
beta_eff = base_beta * (1 + phri_score)

# Population from WorldPop city density lookup
# Bengaluru: 4,378/km2 x pi x 5^2 = 344,000
# Mumbai:   22,000/km2 x pi x 5^2 = 1,728,000

model = SEIRModel("dengue_malaria", lat=12.98, lon=77.58, radius_km=5)
result = model.project(phri_score=0.82, days=14)
```

---

## Validation Strategy

- **Back-testing:** 2023–2024 monsoon weather (wk 22–43) vs IDSP reported outbreak weeks
- **Metric:** Precision / Recall at PHRI threshold = 0.70
- **Ground Truth:** IDSP Weekly Reports, Karnataka / Bengaluru Urban rows
- **Stress Test:** PHRI 0–1 sweep, SEIR curve response verification

```bash
python validation/backtest.py
```

---

## Project Structure

```
sentin-ai/
├── src/
│   ├── gee_pipeline.py        # Sentinel-2 + NDWI temporal differencing
│   ├── yolo_inference.py      # YOLOv8 -> feature vector
│   ├── nasa_power_parser.py   # Weather CSV processing
│   ├── lstm_model.py          # LSTM architecture + training
│   ├── phri_engine.py         # Real-time PHRI scoring
│   ├── disease_router.py      # PHRI -> disease classification
│   ├── seir_model.py          # 14-day SEIR projection (WorldPop N)
│   ├── gemini_voice.py        # Groq LLM health bulletin
│   ├── live_weather.py        # OpenWeatherMap real-time fetch
│   └── realtime_pipeline.py   # End-to-end pipeline orchestrator
├── dashboard/app.py           # Streamlit UI
├── models/lstm_phri.h5        # Trained LSTM model (1.5 MB)
├── data/
│   ├── raw_imagery/           # Sentinel-2 scenes (RGB + NDWI)
│   ├── weather_cache/         # NASA POWER CSVs + LSTM sequences
│   └── idsp_bulletins/        # IDSP PDFs (44) + parsed CSVs
├── validation/
│   ├── idsp_parser.py         # PDF -> structured CSV
│   └── backtest.py            # PHRI vs IDSP comparison
├── notebooks/
│   ├── 01_eda_weather.ipynb   # NASA POWER EDA
│   ├── 02_yolo_training.ipynb # YOLO inference demo
│   └── 03_lstm_training.ipynb # LSTM training review + PHRI validation
└── .env                       # API keys (never commit)
```

---

## References

- SmartHealth-Track: AI-Powered Real-Time Infectious Disease Monitoring — MDPI Mathematics (2025)
- LSI-YOLOv8 for Remote Sensing Images — IEEE Access (2024)
- [Google Earth Engine](https://earthengine.google.com) | [NASA POWER API](https://power.larc.nasa.gov)
- [IDSP Weekly Outbreaks](https://idsp.mohfw.gov.in) | [WorldPop](https://worldpop.org)
- [YOLOv8](https://github.com/ultralytics/ultralytics) | [Groq API](https://console.groq.com)

---

*Last updated: July 2026 | Built for AI4India / HopeWorks Program*
