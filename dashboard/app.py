"""
dashboard/app.py
================
Step 11 — Phase 5 Integration. Sentin-AI Streamlit Dashboard.

Wires together all 8 src/ modules into a live UI:
  PHRIEngine → DiseaseRouter → SEIRModel → GeminiVoice

Run:
  streamlit run dashboard/app.py
"""

import sys
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Sentin-AI | Public Health Early Warning",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap');

  /* ── Root palette ── */
  :root {
    --bg-deep:      #0a0e17;
    --bg-card:      #111827;
    --bg-card2:     #1a2235;
    --accent-cyan:  #00e5ff;
    --accent-amber: #ffb300;
    --accent-red:   #ff4c4c;
    --accent-green: #00e676;
    --text-primary: #e8edf5;
    --text-muted:   #6b7a99;
    --border:       rgba(255,255,255,0.07);
  }

  /* ── Global ── */
  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-deep) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text-primary);
  }
  [data-testid="stSidebar"] {
    background: #0d1220 !important;
    border-right: 1px solid var(--border);
  }
  h1,h2,h3 { font-family: 'Syne', sans-serif; }
  code, .mono { font-family: 'DM Mono', monospace; }

  /* ── Hero header ── */
  .hero {
    background: linear-gradient(135deg, #0d1f3c 0%, #0a0e17 60%);
    border: 1px solid rgba(0,229,255,0.15);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(0,229,255,0.08) 0%, transparent 70%);
    border-radius: 50%;
  }
  .hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent-cyan);
    letter-spacing: -0.5px;
    margin: 0 0 0.25rem 0;
  }
  .hero-sub {
    color: var(--text-muted);
    font-size: 0.9rem;
    font-family: 'DM Mono', monospace;
    margin: 0;
  }

  /* ── PHRI gauge card ── */
  .phri-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.5rem;
    text-align: center;
  }
  .phri-score {
    font-family: 'Syne', sans-serif;
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1;
  }
  .phri-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 0.25rem;
  }

  /* ── Metric cards ── */
  .metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
  }
  .metric-title {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
  }
  .metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
  }
  .metric-sub {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
  }

  /* ── Risk badge ── */
  .badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .badge-low      { background: rgba(0,230,118,0.15);  color: #00e676; border: 1px solid rgba(0,230,118,0.3); }
  .badge-medium   { background: rgba(255,179,0,0.15);  color: #ffb300; border: 1px solid rgba(255,179,0,0.3); }
  .badge-high     { background: rgba(255,100,0,0.15);  color: #ff6400; border: 1px solid rgba(255,100,0,0.3); }
  .badge-critical { background: rgba(255,76,76,0.2);   color: #ff4c4c; border: 1px solid rgba(255,76,76,0.4); }

  /* ── Bulletin card ── */
  .bulletin-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent-cyan);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    line-height: 1.75;
  }
  .bulletin-headline {
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--accent-amber);
    margin-bottom: 1rem;
  }
  .action-item {
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
  }
  .action-dot {
    color: var(--accent-cyan);
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 0.05rem;
  }

  /* ── Officer note ── */
  .officer-note {
    background: rgba(0,229,255,0.04);
    border: 1px solid rgba(0,229,255,0.12);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 1rem;
  }

  /* ── Section headers ── */
  .section-head {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
  }

  /* ── Stress test ── */
  .stress-bar {
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, #00e676, #ffb300, #ff4c4c);
    margin-bottom: 0.5rem;
  }

  /* ── Hide Streamlit chrome ── */
  #MainMenu, footer, header { visibility: hidden; }
  [data-testid="stToolbar"] { display: none; }
  .block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────
RISK_COLORS = {
    "LOW": "#00e676", "MEDIUM": "#ffb300",
    "HIGH": "#ff6400", "CRITICAL": "#ff4c4c"
}
RISK_BADGE = {
    "LOW": "badge-low", "MEDIUM": "badge-medium",
    "HIGH": "badge-high", "CRITICAL": "badge-critical"
}

def risk_color(level): return RISK_COLORS.get(level, "#6b7a99")
def risk_badge(level): return RISK_BADGE.get(level,  "badge-low")


def phri_color(score):
    if score < 0.40: return "#00e676"
    if score < 0.60: return "#ffb300"
    if score < 0.75: return "#ff6400"
    return "#ff4c4c"


# ── Module loader (cached) ─────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading Sentin-AI modules...")
def load_modules():
    try:
        from phri_engine    import PHRIEngine
        from disease_router import DiseaseRouter
        from seir_model     import SEIRModel
        from gemini_voice   import GeminiVoice
        return PHRIEngine(), DiseaseRouter(), GeminiVoice()
    except Exception as e:
        st.error(f"Module load error: {e}")
        return None, None, None


@st.cache_data(show_spinner=False)
def load_history_df():
    csv = ROOT / "data" / "weather_cache" / "weather_features.csv"
    if csv.exists():
        return pd.read_csv(csv, index_col=0, parse_dates=True)
    return None


# ── Plotly theme ───────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#6b7a99", size=11),
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
)


# ── PHRI gauge chart ───────────────────────────────────────────────────────
def phri_gauge(score: float, risk_level: str):
    color = phri_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=36, family="Syne", color=color),
                    valueformat=".2f"),
        gauge=dict(
            axis=dict(range=[0, 1], tickfont=dict(color="#6b7a99", size=10),
                      tickvals=[0, 0.4, 0.6, 0.75, 1.0],
                      ticktext=["0", "0.4", "0.6", "0.75", "1"]),
            bar=dict(color=color, thickness=0.25),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[0.00, 0.40], color="rgba(0,230,118,0.08)"),
                dict(range=[0.40, 0.60], color="rgba(255,179,0,0.08)"),
                dict(range=[0.60, 0.75], color="rgba(255,100,0,0.08)"),
                dict(range=[0.75, 1.00], color="rgba(255,76,76,0.08)"),
            ],
            threshold=dict(line=dict(color=color, width=2), value=score),
        ),
    ))
    fig.update_layout(**PLOT_LAYOUT, height=220)
    return fig


# ── SEIR projection chart ──────────────────────────────────────────────────
def seir_chart(seir_result, disease_label: str):
    days   = list(range(1, seir_result.projection_days + 1))
    cases  = seir_result.new_cases_curve[1:]
    color  = phri_color(seir_result.phri_score)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days, y=cases,
        mode="lines+markers",
        line=dict(color=color, width=2.5),
        marker=dict(size=5, color=color),
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.1)",
        name="New Cases / Day",
        hovertemplate="Day %{x}: %{y:.0f} cases<extra></extra>",
    ))

    # Peak annotation
    peak_day = seir_result.peak_day
    peak_val = seir_result.peak_cases
    fig.add_annotation(
        x=peak_day, y=peak_val,
        text=f"Peak: {peak_val}",
        showarrow=True,
        arrowhead=2,
        arrowcolor=color,
        font=dict(color=color, size=11, family="DM Mono"),
        bgcolor="rgba(17,24,39,0.8)",
        bordercolor=color,
        borderwidth=1,
    )

    fig.update_layout(
        **PLOT_LAYOUT,
        title=dict(text=f"14-Day Case Projection — {disease_label}",
                   font=dict(family="Syne", size=13, color="#e8edf5"), x=0),
        xaxis_title="Day",
        yaxis_title="New Cases",
        height=280,
        showlegend=False,
    )
    return fig


# ── Historical PHRI timeline ───────────────────────────────────────────────
def phri_timeline(df_hist: pd.DataFrame, n_days: int = 90):
    df = df_hist.tail(n_days)

    # Approximate PHRI from weather features as a proxy (before model trained)
    # Real PHRI comes from model.predict after training
    proxy = (
        df["relative_humidity_pct"].clip(0, 100) / 100 * 0.4 +
        df["precipitation_imerg_mm"].clip(0, 80)  / 80  * 0.4 +
        df["temperature_2m_c"].clip(15, 38).apply(lambda t: max(0, t-28)/10) * 0.2
    ).clip(0, 1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=proxy,
        mode="lines",
        line=dict(color="#00e5ff", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(0,229,255,0.06)",
        name="PHRI Proxy",
        hovertemplate="%{x|%d %b %Y}: %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=0.70, line_dash="dash", line_color="#ff4c4c",
                  annotation_text="Alert (0.70)",
                  annotation_font=dict(color="#ff4c4c", size=10))
    fig.update_layout(
        **PLOT_LAYOUT,
        title=dict(text="Historical PHRI Proxy (Weather-based)",
                   font=dict(family="Syne", size=13, color="#e8edf5"), x=0),
        height=220, showlegend=False,
    )
    return fig


# ── Weather radar chart ────────────────────────────────────────────────────
def weather_radar(weather: dict):
    cats = ["Temp", "Humidity", "Rain", "Dew Point", "Wind", "Insolation"]
    bounds = [(15,38), (20,100), (0,80), (5,28), (0,12), (0,1)]
    keys   = ["temperature_2m_c", "relative_humidity_pct",
              "precipitation_imerg_mm", "dew_frost_point_c",
              "wind_speed_10m_ms", "all_sky_insolation_clearness"]
    vals = []
    for k, (lo, hi) in zip(keys, bounds):
        raw = weather.get(k, 0)
        vals.append(round((raw - lo) / (hi - lo) * 100, 1))
    vals_closed = vals + [vals[0]]
    cats_closed = cats + [cats[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vals_closed, theta=cats_closed,
        fill="toself",
        fillcolor="rgba(0,229,255,0.1)",
        line=dict(color="#00e5ff", width=1.5),
        marker=dict(size=4),
    ))
    fig.update_layout(
        **PLOT_LAYOUT,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0,100],
                           gridcolor="rgba(255,255,255,0.06)",
                           tickfont=dict(size=8, color="#6b7a99")),
            angularaxis=dict(gridcolor="rgba(255,255,255,0.06)",
                            tickfont=dict(size=10, color="#e8edf5")),
        ),
        height=260, showlegend=False,
        title=dict(text="Weather Conditions",
                   font=dict(family="Syne", size=13, color="#e8edf5"), x=0),
    )
    return fig


# ── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar():
    st.sidebar.markdown("""
    <div style='padding:1rem 0 0.5rem 0'>
      <div style='font-family:Syne;font-size:1.1rem;font-weight:800;color:#00e5ff'>
        🛰️ SENTIN-AI
      </div>
      <div style='font-family:DM Mono;font-size:0.65rem;color:#6b7a99;letter-spacing:1px'>
        PUBLIC HEALTH EARLY WARNING
      </div>
    </div>
    <hr style='border-color:rgba(255,255,255,0.07);margin:0.5rem 0 1rem 0'>
    """, unsafe_allow_html=True)

    mode = st.sidebar.radio(
        "Mode",
        ["🔴 Real-time Scoring", "📅 Historical Scoring", "🧪 Stress Test"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("""
    <div class='section-head' style='margin-top:1.5rem'>Location</div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("📍 **Bengaluru, Karnataka**")
    st.sidebar.markdown(
        "<span style='font-family:DM Mono;font-size:0.72rem;color:#6b7a99'>"
        "12.98°N 77.58°E  |  5km radius</span>",
        unsafe_allow_html=True
    )

    st.sidebar.markdown("""
    <div class='section-head' style='margin-top:1.5rem'>Manual Weather Input</div>
    """, unsafe_allow_html=True)

    weather = {
        "temperature_2m_c"            : st.sidebar.slider("Temperature (°C)", 15.0, 42.0, 31.0, 0.5),
        "relative_humidity_pct"       : st.sidebar.slider("Humidity (%)",      20.0, 100.0, 80.0, 1.0),
        "precipitation_imerg_mm"      : st.sidebar.slider("Rainfall (mm/day)", 0.0,  80.0,  18.0, 0.5),
        "dew_frost_point_c"           : st.sidebar.slider("Dew Point (°C)",    5.0,  30.0,  24.0, 0.5),
        "wind_speed_10m_ms"           : st.sidebar.slider("Wind Speed (m/s)",  0.0,  15.0,   2.5, 0.1),
        "all_sky_insolation_clearness": st.sidebar.slider("Insolation (0–1)",  0.0,   1.0,   0.4, 0.05),
    }

    st.sidebar.markdown("""
    <div class='section-head' style='margin-top:1rem'>YOLO Visual Features</div>
    """, unsafe_allow_html=True)
    use_yolo = st.sidebar.toggle("Simulate YOLO Detections", value=True)
    yolo = None
    if use_yolo:
        yolo = {
            "stagnant_water_count"    : st.sidebar.slider("Stagnant Water Sites",  0, 20, 5),
            "stagnant_water_area_px"  : st.sidebar.slider("Water Area (px)",       0, 50000, 12000, 500),
            "garbage_count"           : st.sidebar.slider("Garbage Sites",         0, 15, 3),
            "vegetation_anomaly_score": st.sidebar.slider("Veg Anomaly Score",     0.0, 1.0, 0.25, 0.05),
        }

    return mode, weather, yolo


# ── Main run function ──────────────────────────────────────────────────────
def run_inference(engine, router, voice, weather, yolo, mode,
                  hist_date=None):
    """Run the full pipeline and return all results."""
    from seir_model import SEIRModel

    with st.spinner("Running PHRI inference..."):
        if mode == "📅 Historical Scoring" and hist_date:
            phri_result = engine.score_historical(hist_date)
        else:
            phri_result = engine.score_realtime(weather, yolo)

    disease_route = router.classify(phri_result, weather, yolo)
    seir_result   = SEIRModel(disease_route.primary_bucket).project(
                        phri_result.phri_score, days=14)

    with st.spinner("Generating health bulletin..."):
        bulletin = voice.generate(phri_result, disease_route, seir_result)

    return phri_result, disease_route, seir_result, bulletin


# ── Page render ────────────────────────────────────────────────────────────
def main():
    engine, router, voice = load_modules()
    df_hist = load_history_df()

    mode, weather, yolo = render_sidebar()

    # ── Hero ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class='hero'>
      <div class='hero-title'>🛰️ Sentin-AI</div>
      <p class='hero-sub'>
        AI-Powered Proactive Disease Outbreak Monitor &nbsp;·&nbsp;
        Bengaluru, Karnataka &nbsp;·&nbsp;
        {date.today().strftime("%d %B %Y")}
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Module check ───────────────────────────────────────────────────────
    if engine is None:
        st.error("Could not load Sentin-AI modules. Check that src/ files are in place.")
        return

    model_ready = (ROOT / "models" / "lstm_phri.h5").exists()
    data_ready  = (ROOT / "data" / "weather_cache" / "weather_features.csv").exists()

    if not data_ready:
        st.warning("⚠️  `weather_features.csv` not found — run `python src/nasa_power_parser.py` first.")
    if not model_ready:
        st.info("ℹ️  Trained model not found — using sidebar weather directly for demo scoring.")

    # ── Mode: Historical ──────────────────────────────────────────────────
    hist_date = None
    if mode == "📅 Historical Scoring":
        st.markdown("<div class='section-head'>Select Historical Date</div>",
                    unsafe_allow_html=True)
        if data_ready:
            min_d = date(2023, 1, 31)
            max_d = date(2024, 12, 31)
        else:
            min_d = date(2023, 1, 31)
            max_d = date.today() - timedelta(days=1)
        hist_date = st.date_input("Date", value=date(2024, 8, 15),
                                  min_value=min_d, max_value=max_d)

    # ── Mode: Stress Test ─────────────────────────────────────────────────
    if mode == "🧪 Stress Test":
        st.markdown("<div class='section-head'>Stress Test — PHRI Response Sweep</div>",
                    unsafe_allow_html=True)
        from seir_model import SEIRModel, DISEASE_PARAMS
        stress_disease = st.selectbox(
            "Disease bucket", list(DISEASE_PARAMS.keys()), index=0
        )
        phri_vals  = np.linspace(0, 1, 21)
        seir_model = SEIRModel(stress_disease)
        stress_res = seir_model.stress_test((0.0, 1.0), steps=21, days=14)
        totals     = [r.total_projected for r in stress_res]
        peaks      = [r.peak_cases      for r in stress_res]

        fig_stress = go.Figure()
        fig_stress.add_trace(go.Scatter(
            x=phri_vals, y=totals, mode="lines+markers",
            name="Total Cases (14d)",
            line=dict(color="#00e5ff", width=2),
            marker=dict(size=5),
        ))
        fig_stress.add_trace(go.Scatter(
            x=phri_vals, y=peaks, mode="lines+markers",
            name="Peak Daily Cases",
            line=dict(color="#ffb300", width=2, dash="dot"),
            marker=dict(size=5),
        ))
        fig_stress.add_vline(x=0.70, line_dash="dash", line_color="#ff4c4c",
                             annotation_text="Alert threshold",
                             annotation_font=dict(color="#ff4c4c", size=10))
        fig_stress.update_layout(
            **PLOT_LAYOUT,
            title=dict(text=f"SEIR Response to PHRI — {stress_disease}",
                       font=dict(family="Syne", size=13, color="#e8edf5"), x=0),
            xaxis_title="PHRI Score",
            yaxis_title="Cases",
            height=320,
            legend=dict(font=dict(color="#e8edf5")),
        )
        st.plotly_chart(fig_stress, width='stretch')
        st.info("💡 This is the Streamlit Stress Test from README Section 12 — "
                "adjust PHRI to see real-time SEIR curve response.")
        return

    # ── Run inference ──────────────────────────────────────────────────────
    run_btn = st.button("▶ Run Analysis", type="primary", width='content')

    if run_btn:
        try:
            phri_r, disease_r, seir_r, bulletin = run_inference(
                engine, router, voice, weather, yolo, mode, hist_date
            )
            st.session_state["last_result"] = (phri_r, disease_r, seir_r, bulletin)
        except Exception as e:
            st.error(f"Inference error: {e}")
            st.info("Tip: Make sure Step 1 (nasa_power_parser.py) has been run.")
            return

    if "last_result" not in st.session_state:
        st.markdown("""
        <div style='background:#111827;border:1px solid rgba(0,229,255,0.12);
                    border-radius:12px;padding:2.5rem;text-align:center;margin-top:1rem'>
          <div style='font-size:2.5rem;margin-bottom:0.75rem'>🛰️</div>
          <div style='font-family:Syne;font-size:1.1rem;font-weight:700;
                      color:#00e5ff;margin-bottom:0.5rem'>
            Sentin-AI Ready
          </div>
          <div style='font-family:DM Mono;font-size:0.8rem;color:#6b7a99'>
            Adjust the weather sliders in the sidebar, then click
            <strong style='color:#e8edf5'>▶ Run Analysis</strong> to generate a health bulletin.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    phri_r, disease_r, seir_r, bulletin = st.session_state["last_result"]

    score      = phri_r.phri_score
    risk_level = phri_r.risk_level
    color      = phri_color(score)
    badge_cls  = risk_badge(risk_level)

    # ── Row 1: PHRI gauge + key metrics ────────────────────────────────────
    st.markdown("<div class='section-head'>Risk Assessment</div>",
                unsafe_allow_html=True)

    col_gauge, col_m1, col_m2, col_m3, col_m4 = st.columns([1.4, 1, 1, 1, 1])

    with col_gauge:
        st.plotly_chart(phri_gauge(score, risk_level), width='stretch')
        st.markdown(f"""
        <div style='text-align:center;margin-top:-1rem'>
          <span class='badge {badge_cls}'>{risk_level}</span>
        </div>""", unsafe_allow_html=True)

    metrics = [
        ("Disease Risk",  disease_r.meta.get("label","—"), disease_r.primary_bucket.replace("_"," ").title()),
        ("Peak Cases",    f"{seir_r.peak_cases}", f"Day {seir_r.peak_day} of 14"),
        ("14d Total",     f"{seir_r.total_projected}", f"Attack rate {seir_r.attack_rate_pct:.3f}%"),
        ("Confidence",    f"{phri_r.confidence:.0%}", "Visual ✅" if phri_r.visual_complete else "Weather only"),
    ]
    for col, (title, val, sub) in zip([col_m1, col_m2, col_m3, col_m4], metrics):
        with col:
            st.markdown(f"""
            <div class='metric-card'>
              <div class='metric-title'>{title}</div>
              <div class='metric-value' style='color:{color}'>{val}</div>
              <div class='metric-sub'>{sub}</div>
            </div>""", unsafe_allow_html=True)

    # ── Row 2: SEIR chart + weather radar ──────────────────────────────────
    st.markdown("<div class='section-head' style='margin-top:1.5rem'>Projection & Environment</div>",
                unsafe_allow_html=True)
    col_seir, col_radar = st.columns([2, 1])

    with col_seir:
        st.plotly_chart(
            seir_chart(seir_r, disease_r.meta.get("label","—")),
            width='stretch'
        )

    with col_radar:
        st.plotly_chart(weather_radar(weather), width='stretch')

    # ── Row 3: Historical timeline ─────────────────────────────────────────
    if df_hist is not None:
        st.markdown("<div class='section-head'>Historical Risk Timeline</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(phri_timeline(df_hist), width='stretch')

    # ── Row 4: Health bulletin ─────────────────────────────────────────────
    st.markdown("<div class='section-head' style='margin-top:0.5rem'>Health Bulletin</div>",
                unsafe_allow_html=True)

    col_bull, col_act = st.columns([3, 2])

    with col_bull:
        fallback_note = (
            " <span style='font-size:0.7rem;color:#6b7a99'>(template)</span>"
            if bulletin.fallback_used else ""
        )
        st.markdown(f"""
        <div class='bulletin-card'>
          <div class='bulletin-headline'>📰 {bulletin.headline}{fallback_note}</div>
          <div style='font-size:0.88rem;color:#c8d0e0;line-height:1.8'>
            {bulletin.health_bulletin.replace(chr(10), '<br><br>')}
          </div>
          <div class='officer-note'>
            🔬 <strong>Officer Note:</strong> {bulletin.officer_note}
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_act:
        st.markdown("<div style='font-family:DM Mono;font-size:0.7rem;color:#6b7a99;"
                    "letter-spacing:1.5px;text-transform:uppercase;margin-bottom:0.75rem'>"
                    "Action Items</div>", unsafe_allow_html=True)
        for item in bulletin.action_items:
            st.markdown(f"""
            <div class='action-item'>
              <span class='action-dot'>▸</span>
              <span>{item}</span>
            </div>""", unsafe_allow_html=True)

        # Disease meta box
        meta = disease_r.meta
        st.markdown(f"""
        <div class='officer-note' style='margin-top:1rem'>
          <strong>Vector:</strong> {meta.get('vector','—')}<br>
          <strong>Incubation:</strong> {meta.get('incubation_days','—')}<br>
          <strong>Warning Signs:</strong> {meta.get('warning_signs','—')}
        </div>""", unsafe_allow_html=True)

    # ── Row 5: Co-risks + rules triggered ─────────────────────────────────
    if disease_r.secondary_buckets or disease_r.rules_triggered:
        st.markdown("<div class='section-head' style='margin-top:1rem'>Rule Engine Output</div>",
                    unsafe_allow_html=True)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("**Rules triggered:**")
            for rule in disease_r.rules_triggered:
                st.markdown(f"- `{rule}`")
        with col_r2:
            if disease_r.secondary_buckets:
                st.markdown("**Co-risk buckets:**")
                for b in disease_r.secondary_buckets:
                    st.markdown(f"- `{b}`")
            st.markdown(f"**Reasoning:**  \n{disease_r.reasoning[:200]}...")

    # ── Footer ─────────────────────────────────────────────────────────────
    st.markdown("""
    <hr style='border-color:rgba(255,255,255,0.06);margin:2rem 0 1rem 0'>
    <div style='text-align:center;font-family:DM Mono;font-size:0.68rem;color:#3d4d6a'>
      Sentin-AI · AI4India / HopeWorks · Bengaluru ·
      Built with Sentinel-2 · NASA POWER · YOLOv8 · LSTM · SEIR · Gemini
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()