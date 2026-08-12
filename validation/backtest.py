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
    print(f"    Feature dates: {dates[0].date()} -> {dates[-1].date()}  ({len(dates)} days)")

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
    print(f"    [OK] {LABEL_PATH}  (overwritten with real labels)")
    print(f"    [OK] {ALIGN_CSV}")


def summarise(df_align: pd.DataFrame):
    print("[4/4] Alignment summary ...")
    pos_seqs = df_align[df_align["label"] == 1]
    if len(pos_seqs):
        print(f"    First outbreak sequence: {pos_seqs.iloc[0]['seq_start']}")
        print(f"    Last  outbreak sequence: {pos_seqs.iloc[-1]['seq_end']}")
    else:
        print("    No outbreak sequences found - labels are all zeros.")
    print("\n[OK] backtest.py (Phase A) complete - labels ready for lstm_model.py (Step 4)")


def run_phase_a():
    X, dates, df_weekly = load_inputs()
    labels, df_align    = align_labels(X, dates, df_weekly)
    save_labels(labels, df_align)
    summarise(df_align)
    return X, labels, df_align


# ── Phase B: Full evaluation (Step 12) ────────────────────────────────────

def run_phase_b():
    """
    Full back-test: load trained LSTM → infer PHRI on all historical sequences
    → compare against IDSP ground truth → Precision/Recall sweep →
    save results CSV + 3 diagnostic plots.

    Called after Step 4 (lstm_model.py) has saved models/lstm_phri.h5.
    """
    import tensorflow as tf
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend for server environments
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from sklearn.metrics import (precision_score, recall_score, f1_score,
                                 roc_curve, auc, confusion_matrix)

    VAL_DIR    = ROOT / "validation"
    MODEL_PATH = ROOT / "models" / "lstm_phri.h5"

    # ── Guard: model must exist ────────────────────────────────────────────
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"\n{MODEL_PATH} not found.\n"
            "Train the LSTM first:\n"
            "  python src/lstm_model.py\n"
        )
    for p, step in [(SEQ_PATH, "Step 1 — nasa_power_parser.py"),
                    (LABEL_PATH, "Step 3 — backtest.py (Phase A)"),
                    (ALIGN_CSV,  "Step 3 — backtest.py (Phase A)")]:
        if not p.exists():
            raise FileNotFoundError(f"{p} not found. Run {step} first.")

    print("=" * 60)
    print("  Sentin-AI - Phase B: Full Backtest (Step 12)")
    print("=" * 60)

    # ── 1. Load data ───────────────────────────────────────────────────────
    print("\n[1/6] Loading sequences, labels, and alignment ...")
    X        = np.load(SEQ_PATH)
    labels   = np.load(LABEL_PATH)
    df_align = pd.read_csv(ALIGN_CSV, parse_dates=["seq_start", "seq_end"])

    n_total = len(labels)
    n_pos   = int(labels.sum())
    n_neg   = n_total - n_pos
    print(f"    Sequences : {n_total}  |  Positive (outbreak): {n_pos}  |  Negative: {n_neg}")
    print(f"    Date range: {df_align['seq_start'].min().date()} -> "
          f"{df_align['seq_end'].max().date()}")

    # ── 2. Load model + infer ──────────────────────────────────────────────
    print(f"\n[2/6] Loading model: {MODEL_PATH.name} ...")
    model = tf.keras.models.load_model(str(MODEL_PATH))
    model.summary(print_fn=lambda x: None)   # suppress verbose summary

    print("[3/6] Running PHRI inference on all sequences ...")
    # Normalize X using feature_scaler.npz
    SCALER_PATH = ROOT / "models" / "feature_scaler.npz"
    if SCALER_PATH.exists():
        scaler = np.load(SCALER_PATH)
        col_min = scaler["col_min"].astype(np.float32)
        col_max = scaler["col_max"].astype(np.float32)
        col_range = np.where((col_max - col_min) == 0, 1.0, col_max - col_min)
        X_norm = np.clip((X - col_min) / col_range, 0.0, 1.0)
        print("    [Scaler] Sequences normalized successfully.")
    else:
        print("    [Scaler] feature_scaler.npz not found - predicting on raw sequences.")
        X_norm = X

    phri_scores = model.predict(X_norm, batch_size=64, verbose=0).flatten()
    print(f"    PHRI range : [{phri_scores.min():.4f}, {phri_scores.max():.4f}]")
    print(f"    PHRI mean  : {phri_scores.mean():.4f}")
    print(f"    PHRI median: {np.median(phri_scores):.4f}")

    # Attach PHRI scores to alignment df
    df_align["phri_score"] = phri_scores
    df_align["true_label"] = labels.astype(int)

    # ── 3. Threshold sweep ─────────────────────────────────────────────────
    print("\n[4/6] Threshold sweep ...")
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9]
    sweep_rows = []

    print(f"\n  {'Thresh':>7}  {'Prec':>6}  {'Recall':>7}  {'F1':>6}  "
          f"{'TP':>4}  {'FP':>4}  {'FN':>4}  {'TN':>4}  {'Alerts':>6}")
    print("  " + "-" * 60)

    for thresh in thresholds:
        preds = (phri_scores >= thresh).astype(int)
        true  = labels.astype(int)
        tp = int(((preds==1) & (true==1)).sum())
        fp = int(((preds==1) & (true==0)).sum())
        fn = int(((preds==0) & (true==1)).sum())
        tn = int(((preds==0) & (true==0)).sum())

        p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2*p*r / (p+r)  if (p + r)  > 0 else 0.0

        marker = "  <- target" if thresh == PHRI_THRESHOLD else ""
        print(f"  {thresh:>7.2f}  {p:>6.3f}  {r:>7.3f}  {f1:>6.3f}  "
              f"{tp:>4}  {fp:>4}  {fn:>4}  {tn:>4}  {int(preds.sum()):>6}{marker}")

        sweep_rows.append({
            "threshold": thresh, "precision": round(p,4),
            "recall": round(r,4), "f1": round(f1,4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "alerts_fired": int(preds.sum()),
        })

    df_sweep = pd.DataFrame(sweep_rows)

    # Best threshold by F1
    best_row   = df_sweep.loc[df_sweep["f1"].idxmax()]
    best_thresh = float(best_row["threshold"])
    print(f"\n  Best threshold by F1: {best_thresh:.2f}  "
          f"(P={best_row['precision']:.3f}  R={best_row['recall']:.3f}  "
          f"F1={best_row['f1']:.3f})")

    # ROC-AUC
    fpr_arr, tpr_arr, _ = roc_curve(labels.astype(int), phri_scores)
    roc_auc = auc(fpr_arr, tpr_arr)
    print(f"  ROC-AUC: {roc_auc:.4f}")

    # ── 4. Save CSVs ───────────────────────────────────────────────────────
    print("\n[5/6] Saving results ...")
    VAL_DIR.mkdir(parents=True, exist_ok=True)

    sweep_csv   = VAL_DIR / "backtest_results.csv"
    scores_csv  = VAL_DIR / "backtest_phri_scores.csv"
    df_sweep.to_csv(sweep_csv,  index=False)
    df_align.to_csv(scores_csv, index=False)
    print(f"    [OK] {sweep_csv}")
    print(f"    [OK] {scores_csv}")

    # ── 5. Generate 3 diagnostic plots ────────────────────────────────────
    print("[6/6] Generating diagnostic plots ...")

    # Colour palette matching dashboard
    C_CYAN   = "#00e5ff"
    C_AMBER  = "#ffb300"
    C_RED    = "#ff4c4c"
    C_GREEN  = "#00e676"
    C_BG     = "#0a0e17"
    C_CARD   = "#111827"
    C_MUTED  = "#6b7a99"

    plt.rcParams.update({
        "figure.facecolor" : C_BG,
        "axes.facecolor"   : C_CARD,
        "axes.edgecolor"   : C_MUTED,
        "axes.labelcolor"  : "#e8edf5",
        "xtick.color"      : C_MUTED,
        "ytick.color"      : C_MUTED,
        "text.color"       : "#e8edf5",
        "grid.color"       : "#1a2235",
        "font.family"      : "monospace",
    })

    fig = plt.figure(figsize=(18, 14), facecolor=C_BG)
    gs  = gridspec.GridSpec(2, 2, figure=fig,
                            hspace=0.38, wspace=0.28,
                            left=0.06, right=0.97,
                            top=0.93, bottom=0.07)

    # ── Plot 1: PHRI Timeline ──────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])   # full-width top row
    dates_plot   = df_align["seq_start"]
    outbreak_idx = df_align["true_label"] == 1

    ax1.fill_between(dates_plot, phri_scores, alpha=0.15, color=C_CYAN)
    ax1.plot(dates_plot, phri_scores, color=C_CYAN, linewidth=0.9,
             label="PHRI Score")
    ax1.scatter(dates_plot[outbreak_idx], phri_scores[outbreak_idx],
                color=C_RED, s=18, zorder=6, label="IDSP Outbreak (label=1)")
    ax1.axhline(PHRI_THRESHOLD, color=C_AMBER, linestyle="--",
                linewidth=1.3, label=f"Alert Threshold ({PHRI_THRESHOLD})")
    ax1.axhline(best_thresh, color=C_GREEN, linestyle=":",
                linewidth=1.1, label=f"Best F1 Threshold ({best_thresh:.2f})")
    ax1.set_ylim(0, 1)
    ax1.set_ylabel("PHRI Score")
    ax1.set_title("PHRI Score vs IDSP Outbreak Ground Truth  (2023–2024 Monsoon)",
                  fontsize=13, pad=10)
    ax1.legend(fontsize=9, loc="upper left",
               facecolor=C_CARD, edgecolor=C_MUTED)
    ax1.grid(True, alpha=0.3)

    # ── Plot 2: Precision-Recall curve ─────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(df_sweep["recall"], df_sweep["precision"],
             "o-", color=C_CYAN, linewidth=2, markersize=6)

    for _, row in df_sweep.iterrows():
        ax2.annotate(f"{row['threshold']:.1f}",
                     (row["recall"], row["precision"]),
                     textcoords="offset points", xytext=(4, 4),
                     fontsize=7.5, color=C_MUTED)

    # Mark target threshold
    tgt = df_sweep[df_sweep["threshold"] == PHRI_THRESHOLD]
    if len(tgt):
        ax2.scatter(tgt["recall"], tgt["precision"],
                    s=80, color=C_AMBER, zorder=7,
                    label=f"Target ({PHRI_THRESHOLD})")
        ax2.legend(fontsize=9, facecolor=C_CARD, edgecolor=C_MUTED)

    ax2.set_xlim(-0.05, 1.05)
    ax2.set_ylim(-0.05, 1.05)
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title("Precision–Recall Curve", fontsize=12, pad=8)
    ax2.grid(True, alpha=0.3)

    # ── Plot 3: ROC curve ──────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(fpr_arr, tpr_arr, color=C_GREEN, linewidth=2,
             label=f"ROC (AUC = {roc_auc:.3f})")
    ax3.plot([0,1], [0,1], color=C_MUTED, linestyle="--",
             linewidth=1, label="Random (AUC=0.5)")

    # Mark target threshold on ROC
    preds_tgt = (phri_scores >= PHRI_THRESHOLD).astype(int)
    tgt_tp    = int(((preds_tgt==1) & (labels.astype(int)==1)).sum())
    tgt_fp    = int(((preds_tgt==1) & (labels.astype(int)==0)).sum())
    tgt_fn    = int(((preds_tgt==0) & (labels.astype(int)==1)).sum())
    tgt_tn    = int(((preds_tgt==0) & (labels.astype(int)==0)).sum())
    tgt_fpr   = tgt_fp / (tgt_fp + tgt_tn) if (tgt_fp + tgt_tn) > 0 else 0
    tgt_tpr   = tgt_tp / (tgt_tp + tgt_fn) if (tgt_tp + tgt_fn) > 0 else 0
    ax3.scatter([tgt_fpr], [tgt_tpr], s=80, color=C_AMBER, zorder=7,
                label=f"Threshold {PHRI_THRESHOLD}")

    ax3.set_xlim(-0.02, 1.02)
    ax3.set_ylim(-0.02, 1.02)
    ax3.set_xlabel("False Positive Rate")
    ax3.set_ylabel("True Positive Rate")
    ax3.set_title(f"ROC Curve  (AUC = {roc_auc:.3f})", fontsize=12, pad=8)
    ax3.legend(fontsize=9, facecolor=C_CARD, edgecolor=C_MUTED)
    ax3.grid(True, alpha=0.3)

    fig.suptitle("Sentin-AI Backtest Report - Bengaluru 2023-2024",
                 fontsize=15, fontweight="bold", color="#e8edf5", y=0.97)

    plot_path = VAL_DIR / "backtest_report.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    [OK] {plot_path}")

    # ── Final summary ──────────────────────────────────────────────────────
    print(f"""
{'='*60}
  BACKTEST COMPLETE
{'='*60}
  Sequences evaluated : {n_total}
  Outbreak sequences  : {n_pos}  ({100*n_pos/n_total:.1f}%)
  ROC-AUC             : {roc_auc:.4f}
  Best F1 threshold   : {best_thresh:.2f}
    Precision         : {best_row['precision']:.3f}
    Recall            : {best_row['recall']:.3f}
    F1                : {best_row['f1']:.3f}

  Outputs:
    {sweep_csv}
    {scores_csv}
    {plot_path}

[OK] Sentin-AI build complete - all 12 steps done.
{'='*60}
""")
    return df_sweep, roc_auc


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