"""
backtest.py
===========
Step 3 of the Sentin-AI build order.

Phase A — Skeleton (this file):
  - Align IDSP weekly labels → LSTM sequence timestamps
  - Overwrite lstm_labels.npy with real 0/1 outbreak labels
  - Save aligned dataset ready for lstm_model.py (Step 4)

Phase B — Full validation (Step 12, after model is trained):
  - Load trained LSTM, run inference on historical sequences
  - Compare PHRI scores against IDSP ground truth
  - Compute Precision / Recall at multiple PHRI thresholds
  - Plot and save results

Outputs (Phase A):
  data/weather_cache/lstm_labels.npy        ← overwritten with real labels
  data/weather_cache/label_alignment.csv    ← human-readable alignment log

Usage:
  python validation/backtest.py              # Phase A (align labels)
  python validation/backtest.py --evaluate   # Phase B (full eval, needs trained model)
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).resolve().parent.parent
WEATHER_DIR  = ROOT / "data" / "weather_cache"
PARSED_DIR   = ROOT / "data" / "idsp_bulletins" / "parsed"

SEQ_PATH     = WEATHER_DIR / "lstm_sequences.npy"
LABEL_PATH   = WEATHER_DIR / "lstm_labels.npy"
FEATURES_CSV = WEATHER_DIR / "weather_features.csv"
WEEKLY_CSV   = PARSED_DIR  / "weekly_labels.csv"
ALIGN_CSV    = WEATHER_DIR / "label_alignment.csv"

WINDOW_SIZE  = 30   # days — must match nasa_power_parser.py
PHRI_THRESHOLD = 0.7

# ── Phase A: Label alignment ───────────────────────────────────────────────

def load_inputs():
    """Load sequences, feature dates, and IDSP weekly labels."""
    print("[1/4] Loading inputs ...")

    # Sequences
    if not SEQ_PATH.exists():
        raise FileNotFoundError(
            f"{SEQ_PATH} not found.\n"
            "Run Step 1 first:  python src/nasa_power_parser.py"
        )
    X = np.load(SEQ_PATH)
    print(f"    Sequences loaded: {X.shape}")

    # Feature date index
    if not FEATURES_CSV.exists():
        raise FileNotFoundError(f"{FEATURES_CSV} not found.")
    df_feat = pd.read_csv(FEATURES_CSV, index_col=0, parse_dates=True)
    dates   = df_feat.index  # daily dates, length = N + WINDOW_SIZE - 1
    print(f"    Feature dates: {dates[0].date()} → {dates[-1].date()}  ({len(dates)} days)")

    # IDSP weekly labels
    if not WEEKLY_CSV.exists():
        raise FileNotFoundError(
            f"{WEEKLY_CSV} not found.\n"
            "Run Step 2 first:  python validation/idsp_parser.py"
        )
    df_weekly = pd.read_csv(WEEKLY_CSV, parse_dates=["week_start", "week_end"])
    print(f"    Weekly labels loaded: {len(df_weekly)} rows  "
          f"| Outbreak weeks: {df_weekly['label'].sum()}")

    return X, dates, df_weekly


def align_labels(X: np.ndarray, dates: pd.DatetimeIndex,
                 df_weekly: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """
    Each sequence i covers days[i] → days[i + WINDOW_SIZE - 1].
    Its label = 1 if ANY of those days fall inside an outbreak week.

    Strategy: build a daily label series from weekly IDSP data,
    then assign label = max(daily_label[i : i+WINDOW_SIZE]).
    """
    print("[2/4] Aligning IDSP weekly labels to LSTM sequences ...")

    # Build daily label series
    daily_label = pd.Series(0, index=dates, dtype=np.float32)

    for _, row in df_weekly.iterrows():
        if row["label"] == 1:
            mask = (dates >= row["week_start"]) & (dates <= row["week_end"])
            daily_label[mask] = 1.0

    outbreak_days = daily_label.sum()
    print(f"    Outbreak days in feature window: {int(outbreak_days)} / {len(dates)}")

    # Assign sequence labels
    n_seq  = len(X)
    labels = np.zeros(n_seq, dtype=np.float32)

    alignment_rows = []
    for i in range(n_seq):
        seq_start = dates[i]
        seq_end   = dates[i + WINDOW_SIZE - 1]
        window_labels = daily_label.iloc[i : i + WINDOW_SIZE].values
        labels[i] = float(window_labels.max())   # 1 if any day is outbreak

        alignment_rows.append({
            "seq_index" : i,
            "seq_start" : seq_start.date(),
            "seq_end"   : seq_end.date(),
            "label"     : int(labels[i]),
        })

    df_align = pd.DataFrame(alignment_rows)
    pos = int(labels.sum())
    neg = n_seq - pos
    print(f"    Sequences labelled: {n_seq} total  |  "
          f"Positive (outbreak=1): {pos}  |  Negative: {neg}")

    if pos == 0:
        print("\n    ⚠  Zero positive sequences — possible causes:")
        print("       • IDSP PDFs not yet parsed (run Step 2 first)")
        print("       • PDF filenames don't contain year/week — check idsp_parser --debug")
        print("       • Monsoon weeks (22-43) don't overlap feature date range")

    return labels, df_align


def save_labels(labels: np.ndarray, df_align: pd.DataFrame):
    print("[3/4] Saving aligned labels ...")
    np.save(LABEL_PATH, labels)
    df_align.to_csv(ALIGN_CSV, index=False)
    print(f"    ✅ {LABEL_PATH}  (overwritten with real labels)")
    print(f"    ✅ {ALIGN_CSV}")


def summarise(df_align: pd.DataFrame):
    print("[4/4] Alignment summary ...")
    pos_seqs = df_align[df_align["label"] == 1]
    if len(pos_seqs):
        print(f"    First outbreak sequence: {pos_seqs.iloc[0]['seq_start']}")
        print(f"    Last  outbreak sequence: {pos_seqs.iloc[-1]['seq_end']}")
    else:
        print("    No outbreak sequences found — labels are all zeros.")
    print(f"\n🎉 backtest.py (Phase A) complete — labels ready for lstm_model.py (Step 4)")


def run_phase_a():
    X, dates, df_weekly = load_inputs()
    labels, df_align    = align_labels(X, dates, df_weekly)
    save_labels(labels, df_align)
    summarise(df_align)
    return X, labels, df_align


# ── Phase B: Full evaluation (Step 12) ────────────────────────────────────

def run_phase_b():
    """
    Full back-test: load trained LSTM → infer PHRI on historical data →
    compare against IDSP ground truth → Precision/Recall sweep.
    Called after Step 4 (lstm_model.py) has saved models/lstm_phri.h5
    """
    import tensorflow as tf
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_score, recall_score, f1_score

    MODEL_PATH = ROOT / "models" / "lstm_phri.h5"
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"{MODEL_PATH} not found.\n"
            "Train the LSTM first:  python src/lstm_model.py"
        )

    print("=== Phase B: Full Backtest ===\n")

    X      = np.load(SEQ_PATH)
    labels = np.load(LABEL_PATH)

    print(f"[1/3] Loading model from {MODEL_PATH} ...")
    model = tf.keras.models.load_model(MODEL_PATH)

    print("[2/3] Running PHRI inference on historical sequences ...")
    phri_scores = model.predict(X, batch_size=64, verbose=0).flatten()
    print(f"    PHRI range: [{phri_scores.min():.3f}, {phri_scores.max():.3f}]  "
          f"mean={phri_scores.mean():.3f}")

    print("[3/3] Threshold sweep (Precision / Recall / F1) ...")
    results = []
    for thresh in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        preds = (phri_scores >= thresh).astype(int)
        true  = labels.astype(int)
        if preds.sum() == 0:
            p, r, f = 0.0, 0.0, 0.0
        else:
            p = precision_score(true, preds, zero_division=0)
            r = recall_score(true, preds, zero_division=0)
            f = f1_score(true, preds, zero_division=0)
        results.append({"threshold": thresh, "precision": round(p,3),
                         "recall": round(r,3), "f1": round(f,3),
                         "alerts_fired": int(preds.sum())})
        marker = " ◀ target" if thresh == PHRI_THRESHOLD else ""
        print(f"    thresh={thresh:.1f}  P={p:.3f}  R={r:.3f}  F1={f:.3f}  "
              f"alerts={int(preds.sum())}{marker}")

    df_results = pd.DataFrame(results)
    results_csv = ROOT / "validation" / "backtest_results.csv"
    df_results.to_csv(results_csv, index=False)
    print(f"\n    ✅ Saved: {results_csv}")

    # Plot PHRI timeline
    df_align = pd.read_csv(ALIGN_CSV, parse_dates=["seq_start"])
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(df_align["seq_start"], phri_scores, color="#2196F3",
            linewidth=0.8, label="PHRI score")
    outbreak_mask = labels == 1
    ax.scatter(df_align["seq_start"][outbreak_mask],
               phri_scores[outbreak_mask],
               color="red", s=12, zorder=5, label="IDSP outbreak")
    ax.axhline(PHRI_THRESHOLD, color="orange", linestyle="--",
               linewidth=1.2, label=f"Threshold {PHRI_THRESHOLD}")
    ax.set_ylim(0, 1)
    ax.set_ylabel("PHRI Score")
    ax.set_title("Sentin-AI Back-test: PHRI vs IDSP Ground Truth (2023–2024)")
    ax.legend()
    fig.tight_layout()
    plot_path = ROOT / "validation" / "backtest_phri_timeline.png"
    fig.savefig(plot_path, dpi=150)
    print(f"    ✅ Plot saved: {plot_path}")

    print("\n🎉 Phase B complete.")
    return df_results


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentin-AI backtest utility")
    parser.add_argument(
        "--evaluate", action="store_true",
        help="Phase B: run full model evaluation (requires trained lstm_phri.h5)"
    )
    args = parser.parse_args()

    if args.evaluate:
        run_phase_b()
    else:
        run_phase_a()