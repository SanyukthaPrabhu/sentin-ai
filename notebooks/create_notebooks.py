"""
create_notebooks.py
===================
Creates all 3 Jupyter notebooks for Sentin-AI.
Run once: python notebooks/create_notebooks.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cell_md(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def cell_code(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


META = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12.0"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Notebook 01 — EDA Weather
# ─────────────────────────────────────────────────────────────────────────────
nb01 = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": META,
    "cells": [
        cell_md([
            "# 01 — EDA: NASA POWER Weather Data\n",
            "**Sentin-AI | Phase 1 — Step 1 Validation**\n\n",
            "Explores 730 days of weather data for Bengaluru Urban (2023–2024).\n",
            "Features: temperature, humidity, precipitation, dew point, wind speed, insolation.",
        ]),
        cell_code([
            "import pandas as pd\n",
            "import numpy as np\n",
            "import matplotlib.pyplot as plt\n",
            "import seaborn as sns\n",
            "from pathlib import Path\n",
            "\n",
            "ROOT = Path('..')\n",
            "df = pd.read_csv(ROOT / 'data/weather_cache/weather_features.csv', parse_dates=['date'])\n",
            "print(f'Shape: {df.shape}')\n",
            "print(df.dtypes)\n",
            "df.head()",
        ]),
        cell_code([
            "# Time-series for the 6 LSTM weather features\n",
            "COLS = [\n",
            "    ('temperature_2m_c',             'Temperature (°C)',          '#ff6b6b'),\n",
            "    ('relative_humidity_pct',         'Relative Humidity (%)',     '#4ecdc4'),\n",
            "    ('precipitation_imerg_mm',        'Precipitation (mm/day)',    '#45b7d1'),\n",
            "    ('dew_frost_point_c',             'Dew Point (°C)',            '#96ceb4'),\n",
            "    ('wind_speed_10m_ms',             'Wind Speed (m/s)',          '#ffeaa7'),\n",
            "    ('all_sky_insolation_clearness',  'Insolation Clearness (0-1)','#dfe6e9'),\n",
            "]\n",
            "\n",
            "fig, axes = plt.subplots(3, 2, figsize=(14, 10))\n",
            "fig.suptitle('Bengaluru Weather 2023-2024 (NASA POWER)', fontsize=14, fontweight='bold')\n",
            "for ax, (col, label, color) in zip(axes.flat, COLS):\n",
            "    if col in df.columns:\n",
            "        ax.plot(df['date'], df[col], color=color, linewidth=0.7, alpha=0.8)\n",
            "        ax.set_title(label, fontsize=10)\n",
            "        ax.grid(True, alpha=0.2)\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'weather_timeseries.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()\n",
            "print('Saved: weather_timeseries.png')",
        ]),
        cell_code([
            "# Correlation matrix of all weather features\n",
            "feature_cols = [c for c in df.columns if c != 'date']\n",
            "corr = df[feature_cols].corr()\n",
            "\n",
            "plt.figure(figsize=(10, 8))\n",
            "sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,\n",
            "            square=True, linewidths=0.5)\n",
            "plt.title('LSTM Feature Correlation Matrix — Bengaluru 2023-2024')\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'correlation_matrix.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
        cell_code([
            "# Monthly aggregation: visualise monsoon peak (Jun–Oct)\n",
            "df['month'] = df['date'].dt.month\n",
            "monthly = df.groupby('month')[['precipitation_imerg_mm',\n",
            "                                 'relative_humidity_pct',\n",
            "                                 'temperature_2m_c']].mean()\n",
            "\n",
            "fig, ax1 = plt.subplots(figsize=(10, 5))\n",
            "ax2 = ax1.twinx()\n",
            "ax1.bar(monthly.index, monthly['precipitation_imerg_mm'],\n",
            "        color='#45b7d1', alpha=0.7, label='Rainfall (mm/day)')\n",
            "ax2.plot(monthly.index, monthly['relative_humidity_pct'],\n",
            "         'r-o', label='Humidity (%)')\n",
            "ax1.set_xlabel('Month')\n",
            "ax1.set_ylabel('Avg Rainfall (mm/day)', color='#45b7d1')\n",
            "ax2.set_ylabel('Avg Humidity (%)', color='red')\n",
            "months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']\n",
            "ax1.set_xticks(range(1, 13))\n",
            "ax1.set_xticklabels(months)\n",
            "plt.title('Monthly Weather Patterns — Bengaluru Monsoon Season')\n",
            "fig.legend(loc='upper left', bbox_to_anchor=(0.1, 0.9))\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'monthly_weather.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Notebook 02 — YOLO Inference
# ─────────────────────────────────────────────────────────────────────────────
nb02 = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": META,
    "cells": [
        cell_md([
            "# 02 — YOLOv8 Satellite Inference\n",
            "**Sentin-AI | Phase 4 — Step 10 Validation**\n\n",
            "Demonstrates YOLOv8 segmentation on Sentinel-2 imagery.\n",
            "Shows the YOLO → feature vector extraction used as LSTM visual input.",
        ]),
        cell_code([
            "import sys\n",
            "sys.path.insert(0, '../src')\n",
            "from pathlib import Path\n",
            "from PIL import Image\n",
            "import matplotlib.pyplot as plt\n",
            "import numpy as np\n",
            "\n",
            "ROOT    = Path('..')\n",
            "IMG_DIR = ROOT / 'data/raw_imagery'\n",
            "\n",
            "rgb_files = sorted(IMG_DIR.glob('S2_*_rgb.png'))\n",
            "print(f'Available Sentinel-2 scenes: {len(rgb_files)}')\n",
            "for f in rgb_files[-5:]:\n",
            "    print(f'  {f.name}')",
        ]),
        cell_code([
            "# Display latest RGB + NDWI scene pair\n",
            "if rgb_files:\n",
            "    stem     = rgb_files[-1].stem.replace('_rgb', '').replace('S2_', '')\n",
            "    rgb_img  = Image.open(rgb_files[-1])\n",
            "    ndwi_p   = IMG_DIR / f'S2_{stem}_ndwi.png'\n",
            "\n",
            "    fig, axes = plt.subplots(1, 2, figsize=(14, 6))\n",
            "    axes[0].imshow(rgb_img)\n",
            "    axes[0].set_title(f'Sentinel-2 RGB ({stem})', fontsize=12, fontweight='bold')\n",
            "    axes[0].axis('off')\n",
            "\n",
            "    if ndwi_p.exists():\n",
            "        axes[1].imshow(Image.open(ndwi_p), cmap='RdYlBu')\n",
            "        axes[1].set_title(f'NDWI Heatmap ({stem})\\nBlue=Water | Red=No Water',\n",
            "                           fontsize=12, fontweight='bold')\n",
            "        axes[1].axis('off')\n",
            "\n",
            "    plt.suptitle('Sentin-AI Satellite Perception Layer — 5km ROI', fontsize=13)\n",
            "    plt.tight_layout()\n",
            "    plt.savefig(HERE / 'satellite_sample.png', dpi=150, bbox_inches='tight')\n",
            "    plt.show()",
        ]),
        cell_code([
            "# Run YOLOv8 on latest satellite image\n",
            "from yolo_inference import YOLOInference\n",
            "\n",
            "yolo   = YOLOInference(model_path=str(ROOT / 'yolov8m-seg.pt'))\n",
            "result = yolo.run_single_image(str(rgb_files[-1]))\n",
            "\n",
            "print('\\nYOLO Visual Feature Vector:')\n",
            "for k, v in result.items():\n",
            "    print(f'  {k:30s}: {v}')",
        ]),
        cell_md([
            "## YOLO → LSTM Interface\n\n",
            "| Feature | COCO Proxy Mapping | Epidemiological Meaning |\n",
            "|---------|-------------------|------------------------|\n",
            "| `stagnant_water_count` | person-class detections | Puddle / water body count |\n",
            "| `stagnant_water_area_px` | sum of person mask areas | Total water exposure surface |\n",
            "| `garbage_count` | suitcase / backpack detections | Waste accumulation proxy |\n",
            "| `vegetation_anomaly_score` | NDWI std-deviation | Deviation from healthy baseline |\n\n",
            "> **Production upgrade:** Fine-tune on [iSAID dataset](https://paperswithcode.com/dataset/isaid) "
            "for actual `stagnant_water`, `garbage_pile`, `vegetation_anomaly` classes.",
        ]),
        cell_code([
            "# NDWI time series across all downloaded scenes\n",
            "npy_files = sorted(IMG_DIR.glob('S2_*_ndwi.npy'))\n",
            "means = [np.mean(np.load(f)) for f in npy_files]\n",
            "dates = [f.stem.split('_')[1] for f in npy_files]\n",
            "\n",
            "plt.figure(figsize=(14, 4))\n",
            "plt.plot(dates, means, '-o', color='#45b7d1', markersize=4)\n",
            "plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)\n",
            "plt.xticks(rotation=45, ha='right', fontsize=7)\n",
            "plt.ylabel('Mean NDWI')\n",
            "plt.title('NDWI Time Series — Bengaluru 5km ROI (2023–2026)\\n'\n",
            "          'Positive=Water present | Negative=Dry / Vegetation')\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'ndwi_timeseries.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Notebook 03 — LSTM Training & PHRI Validation
# ─────────────────────────────────────────────────────────────────────────────
nb03 = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": META,
    "cells": [
        cell_md([
            "# 03 — LSTM Training & PHRI Validation\n",
            "**Sentin-AI | Phase 2 — Step 4 Validation**\n\n",
            "Reviews the trained LSTM model, plots training history,\n",
            "and validates PHRI scores against diverse weather scenarios.",
        ]),
        cell_code([
            "import sys\n",
            "sys.path.insert(0, '../src')\n",
            "import numpy as np\n",
            "import pandas as pd\n",
            "import matplotlib.pyplot as plt\n",
            "from pathlib import Path\n",
            "\n",
            "ROOT = Path('..')\n",
            "\n",
            "# Training history\n",
            "hist = pd.read_csv(ROOT / 'models/training_history.csv')\n",
            "print('Training history:')\n",
            "print(hist.to_string())",
        ]),
        cell_code([
            "# Training + validation loss curves\n",
            "fig, axes = plt.subplots(1, 2, figsize=(12, 4))\n",
            "\n",
            "axes[0].plot(hist['loss'], label='Train Loss', color='#ff6b6b', linewidth=2)\n",
            "if 'val_loss' in hist.columns:\n",
            "    axes[0].plot(hist['val_loss'], label='Val Loss', color='#45b7d1', linewidth=2)\n",
            "axes[0].set_title('Training Loss (Binary Crossentropy)')\n",
            "axes[0].set_xlabel('Epoch')\n",
            "axes[0].legend()\n",
            "axes[0].grid(True, alpha=0.3)\n",
            "\n",
            "if 'accuracy' in hist.columns:\n",
            "    axes[1].plot(hist['accuracy'], label='Train Acc', color='#ff6b6b', linewidth=2)\n",
            "if 'val_accuracy' in hist.columns:\n",
            "    axes[1].plot(hist['val_accuracy'], label='Val Acc', color='#45b7d1', linewidth=2)\n",
            "axes[1].set_title('Training Accuracy')\n",
            "axes[1].set_xlabel('Epoch')\n",
            "axes[1].legend()\n",
            "axes[1].grid(True, alpha=0.3)\n",
            "\n",
            "plt.suptitle('LSTM PHRI Model — Training History', fontsize=13, fontweight='bold')\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'training_history.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
        cell_code([
            "# Load sequences and labels\n",
            "X = np.load(ROOT / 'data/weather_cache/lstm_sequences.npy')\n",
            "y = np.load(ROOT / 'data/weather_cache/lstm_labels.npy')\n",
            "print(f'Sequences shape : {X.shape}  (samples, timesteps=30, features=10)')\n",
            "print(f'Labels shape    : {y.shape}')\n",
            "print(f'Label range     : [{y.min():.3f}, {y.max():.3f}]  mean={y.mean():.3f}')\n",
            "\n",
            "plt.figure(figsize=(10, 4))\n",
            "plt.hist(y, bins=40, color='#00b894', edgecolor='white', alpha=0.8)\n",
            "plt.axvline(x=0.70, color='red', linestyle='--', linewidth=2, label='Alert threshold (0.70)')\n",
            "plt.xlabel('PHRI Score')\n",
            "plt.ylabel('Count')\n",
            "plt.title('Distribution of PHRI Training Labels')\n",
            "plt.legend()\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'phri_distribution.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
        cell_code([
            "# PHRI sensitivity test: diverse real-world weather scenarios\n",
            "from phri_engine import PHRIEngine\n",
            "\n",
            "engine = PHRIEngine()\n",
            "\n",
            "SCENARIOS = [\n",
            "    ('Bengaluru Monsoon (Jul)',  26.0, 88.0, 48.0, 24.0, 2.0, 0.20),\n",
            "    ('Hyderabad Monsoon (Aug)', 28.0, 82.0, 35.0, 23.0, 2.5, 0.25),\n",
            "    ('Mumbai Monsoon (Jul)',    30.0, 85.0, 55.0, 27.0, 3.0, 0.18),\n",
            "    ('Chennai Post-Monsoon',   30.0, 75.0, 20.0, 22.0, 3.0, 0.35),\n",
            "    ('Delhi Winter (Jan)',     15.0, 55.0,  2.0,  8.0, 4.0, 0.60),\n",
            "    ('Leh Dry Summer (Jul)',   22.0, 34.0,  0.0,  4.0, 5.0, 0.85),\n",
            "    ('Las Vegas Desert (Jul)', 34.0,  8.0,  0.0, -3.0, 3.0, 0.95),\n",
            "]\n",
            "\n",
            "FEAT_KEYS = [\n",
            "    'temperature_2m_c', 'relative_humidity_pct', 'precipitation_imerg_mm',\n",
            "    'dew_frost_point_c', 'wind_speed_10m_ms', 'all_sky_insolation_clearness'\n",
            "]\n",
            "\n",
            "results = []\n",
            "for row in SCENARIOS:\n",
            "    name  = row[0]\n",
            "    vals  = row[1:]\n",
            "    w     = dict(zip(FEAT_KEYS, vals))\n",
            "    res   = engine.score_realtime(w)\n",
            "    results.append((name, res.phri_score, res.risk_level))\n",
            "    print(f'{name:30s}  PHRI={res.phri_score:.3f}  [{res.risk_level}]')\n",
            "\n",
            "names  = [r[0] for r in results]\n",
            "scores = [r[1] for r in results]\n",
            "risks  = [r[2] for r in results]\n",
            "CMAP   = {'CRITICAL':'#ff4c4c','HIGH':'#ff6400','MEDIUM':'#ffb300','LOW':'#00e676'}\n",
            "colors = [CMAP.get(r, '#aaa') for r in risks]\n",
            "\n",
            "plt.figure(figsize=(10, 5))\n",
            "plt.barh(names, scores, color=colors, edgecolor='white', height=0.6)\n",
            "plt.axvline(x=0.70, color='red', linestyle='--', linewidth=1.5, label='Alert threshold')\n",
            "plt.xlim(0, 1)\n",
            "plt.xlabel('PHRI Score')\n",
            "plt.title('PHRI Score Across Locations — Model Sensitivity Validation')\n",
            "plt.legend()\n",
            "plt.tight_layout()\n",
            "plt.savefig(HERE / 'phri_sensitivity.png', dpi=150, bbox_inches='tight')\n",
            "plt.show()",
        ]),
        cell_md([
            "## Model Architecture Summary\n\n",
            "```\n",
            "Input:  (batch, 30 timesteps, 10 features)\n",
            "         ↓\n",
            "LSTM(128, return_sequences=True)\n",
            "         ↓\n",
            "LSTM(64)\n",
            "         ↓\n",
            "Dense(64, relu)\n",
            "         ↓\n",
            "Dropout(0.3)\n",
            "         ↓\n",
            "Dense(1, sigmoid)  →  PHRI score ∈ [0.0, 1.0]\n",
            "```\n\n",
            "- **Loss:** Binary Crossentropy\n",
            "- **Optimizer:** Adam (lr=0.001)\n",
            "- **Features:** 4 YOLO visual + 6 NASA POWER weather\n",
            "- **Window:** 30-day rolling\n",
            "- **Alert threshold:** PHRI ≥ 0.70\n",
        ]),
    ],
}

# Patch HERE reference in nb02 cells (HERE is not available in notebooks, use Path)
for nb, name in [(nb01, "01_eda_weather.ipynb"),
                 (nb02, "02_yolo_training.ipynb"),
                 (nb03, "03_lstm_training.ipynb")]:
    out_path = HERE / name
    # Inject HERE definition into first code cell
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            cell["source"].insert(0, "HERE = __import__('pathlib').Path('.')\n")
            break
    out_path.write_text(json.dumps(nb, indent=2, ensure_ascii=True), encoding='utf-8')
    print(f"Created: {out_path.name}")

print("\nAll 3 notebooks created successfully.")
