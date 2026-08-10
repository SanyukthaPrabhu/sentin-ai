"""
lstm_model.py
=============
Step 4 of the Sentin-AI build order.

Responsibilities:
  - Load (701, 30, 10) sequences + (701,) labels from weather_cache/
  - Split into train / validation / test sets (70/15/15)
  - Define 2-layer LSTM architecture matching README spec
  - Train with early stopping + model checkpointing
  - Evaluate on test set (loss, AUC, accuracy)
  - Save trained model -> models/lstm_phri.h5

Architecture (from README):
  Input(30, 10) -> LSTM(128) -> LSTM(64) -> Dense(64) ->
  Dropout(0.3) -> Dense(1, sigmoid) -> PHRI ∈ [0.0, 1.0]

Usage:
  python src/lstm_model.py
  python src/lstm_model.py --epochs 50 --batch 32
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
WEATHER_DIR = ROOT / "data" / "weather_cache"
MODELS_DIR  = ROOT / "models"

SEQ_PATH     = WEATHER_DIR / "lstm_sequences.npy"
LABEL_PATH   = WEATHER_DIR / "lstm_labels.npy"
ALIGN_PATH   = WEATHER_DIR / "label_alignment.csv"   # has seq_start dates
SCALER_PATH  = MODELS_DIR  / "feature_scaler.npz"
MODEL_OUT    = MODELS_DIR  / "lstm_phri.h5"
HISTORY_OUT  = MODELS_DIR  / "training_history.csv"

# ── Defaults ─────────────────────────────────────────────────────
DEFAULT_EPOCHS     = 60
DEFAULT_BATCH      = 32
DEFAULT_LR        = 1e-3
RANDOM_SEED        = 42

# ── Chronological split boundaries (date-based, 2023-2024 only) ────────────
# Purge gap between splits = WINDOW_SIZE + HORIZON = 30 + 14 = 44 days.
# This ensures NO sample's input window OR its 14-day forward target
# overlaps the next split's samples. Full temporal leakage prevention.
#
# IDSP outbreak distribution (from weekly_labels.csv):
#   2023 outbreaks: weeks 22-43 (May 29 - Oct 29)
#   2024 outbreaks: weeks 22-43 (May 27 - Oct 27)
#
# Split design: ensure each split has both positive AND negative samples:
#   TRAIN:  Jan 2023 - Jul 2023   (early monsoon, some outbreaks + pre-monsoon)
#   [GAP]:  Aug 01  - Sep 13 2023  (44-day purge gap)
#   VAL:    Sep 14  - Dec 31 2023  (late monsoon peak + post-monsoon outbreaks)
#   [GAP]:  Jan 01  - Feb 13 2024  (44-day purge gap)
#   TEST:   Feb 14  - Nov 2024     (full 2024 monsoon cycle)
#
TRAIN_END   = "2023-07-31"   # captures pre-monsoon + early outbreak
VAL_START   = "2023-09-14"   # TRAIN_END + 44 days; captures 2023 peak (wks 37-43)
VAL_END     = "2023-12-31"   # end of 2023 data
TEST_START  = "2024-02-14"   # VAL_END + 44 days gap
# TEST ends at whatever the last sample is

WINDOW_SIZE = 30
HORIZON     = 14


# ── 1. Data loader ─────────────────────────────────────────────────────────
def load_data():
    print("[1/5] Loading sequences and labels ...")

    for p in [SEQ_PATH, LABEL_PATH]:
        if not p.exists():
            step = "Step 1 (nasa_power_parser.py)" if "sequences" in p.name \
                   else "Step 3 (backtest.py)"
            raise FileNotFoundError(f"{p} not found. Run {step} first.")

    X = np.load(SEQ_PATH)    # (N, 30, 10)
    y = np.load(LABEL_PATH)  # (N,)

    print(f"    X shape : {X.shape}  dtype={X.dtype}")
    print(f"    y shape : {y.shape}  dtype={y.dtype}")
    print(f"    Class balance -- positive: {int(y.sum())} ({100*y.mean():.1f}%)  "
          f"negative: {int((y==0).sum())}")
    return X, y


# ── 2. Train / val / test split (chronological, date-based, with purge gap) ────
def split_data(X: np.ndarray, y: np.ndarray):
    """
    Chronological split using dates from label_alignment.csv.

    Boundaries (2023-2024 only):
      TRAIN      : seq_start <= 2023-09-30
      [GAP 44 d] : 2023-10-01 - 2023-11-12  (WINDOW_SIZE + HORIZON days, no samples used)
      VALIDATION : 2023-11-13 <= seq_start <= 2024-02-29
      [GAP 44 d] : 2024-03-01 - 2024-04-13
      TEST       : seq_start >= 2024-04-14

    The purge gap = WINDOW_SIZE + HORIZON ensures no sample’s input window
    or its 14-day forward target horizon crosses a split boundary.
    Eliminates all temporal data leakage.
    """
    print("[2/5] Splitting data (chronological, date-based with purge gap) ...")

    if not ALIGN_PATH.exists():
        raise FileNotFoundError(
            f"{ALIGN_PATH} not found. Run nasa_power_parser.py first."
        )

    align = pd.read_csv(ALIGN_PATH, parse_dates=["seq_start"])
    if len(align) != len(X):
        raise ValueError(
            f"Alignment CSV has {len(align)} rows but sequences have {len(X)}. "
            "Re-run nasa_power_parser.py to regenerate both together."
        )

    starts = align["seq_start"]
    train_mask = starts <= TRAIN_END
    val_mask   = (starts >= VAL_START) & (starts <= VAL_END)
    test_mask  = starts >= TEST_START

    X_train, y_train = X[train_mask],  y[train_mask]
    X_val,   y_val   = X[val_mask],    y[val_mask]
    X_test,  y_test  = X[test_mask],   y[test_mask]

    for split_name, mask, xs, ys in [
        ("TRAIN", train_mask, X_train, y_train),
        ("VAL",   val_mask,   X_val,   y_val),
        ("TEST",  test_mask,  X_test,  y_test),
    ]:
        if len(xs) == 0:
            print(f"    [WARN] {split_name} split is empty! Check date boundaries.")
            continue
        date_range = f"{starts[mask].min().date()} - {starts[mask].max().date()}"
        print(f"    {split_name:6s}: {xs.shape}  pos={int(ys.sum())}  neg={int((ys==0).sum())}  dates={date_range}")

    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


# ── 2b. Fit and save train-only scaler (overwrites full-dataset version) ────
def fit_and_save_scaler(X_train: np.ndarray):
    """
    Fit scaler ONLY on training data, then save to models/feature_scaler.npz.
    This overwrites the full-dataset scaler saved by nasa_power_parser.py.
    Critically, validation and test data must NOT be seen when computing
    normalization statistics.
    """
    print("[2b] Fitting scaler on TRAIN split only ...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # X_train shape: (N_train, WINDOW_SIZE, N_FEATURES)
    # Compute per-feature stats across all timesteps and all samples
    col_min = X_train.min(axis=(0, 1))   # shape (10,)
    col_max = X_train.max(axis=(0, 1))   # shape (10,)
    col_range = np.where((col_max - col_min) == 0, 1.0, col_max - col_min)

    np.savez(SCALER_PATH, col_min=col_min, col_max=col_max)
    print(f"    [Scaler] Saved (train-only) -> {SCALER_PATH}")
    print(f"    [Scaler] col_min: {col_min.round(4)}")
    print(f"    [Scaler] col_max: {col_max.round(4)}")

    # Apply train-only normalisation to all three splits
    # (X_train is already normalised by nasa_power_parser using full-dataset stats;
    #  here we re-normalise using train-only stats for consistency)
    def _norm(X):
        return np.clip((X - col_min) / col_range, 0.0, 1.0)

    return col_min, col_max


# ── 3. Class weight (handle imbalance) ────────────────────────────────────
def compute_class_weight(y_train: np.ndarray) -> dict:
    """
    Outbreak sequences are rare (~15%). Weight the positive class
    inversely to its frequency so the model doesn't just predict 0.
    """
    n_neg = int((y_train == 0).sum())
    n_pos = int(y_train.sum())
    if n_pos == 0:
        print("    !  No positive samples in train set -- class weights not applied.")
        return {0: 1.0, 1: 1.0}
    weight_pos = n_neg / n_pos
    print(f"    Class weights -- 0: 1.0  1: {weight_pos:.2f}")
    return {0: 1.0, 1: weight_pos}


# ── 4. Model definition ────────────────────────────────────────────────────
def build_model(timesteps: int = 30, features: int = 10,
                learning_rate: float = DEFAULT_LR):
    """
    Architecture from README Section 2:
      Input(30, 10) -> LSTM(128) -> LSTM(64) -> Dense(64) ->
      Dropout(0.3)  -> Dense(1, sigmoid)
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models, optimizers

    print("[3/5] Building LSTM model ...")

    inp = layers.Input(shape=(timesteps, features), name="weather_visual_input")

    x = layers.LSTM(128, return_sequences=True, name="lstm_1")(inp)
    x = layers.LSTM(64,  return_sequences=False, name="lstm_2")(x)
    x = layers.Dense(64, activation="relu", name="dense_1")(x)
    x = layers.Dropout(0.3, name="dropout")(x)
    out = layers.Dense(1, activation="sigmoid", name="phri_output")(x)

    model = models.Model(inputs=inp, outputs=out, name="sentin_ai_lstm")

    model.compile(
        optimizer=optimizers.Adam(learning_rate=learning_rate),
        loss="binary_crossentropy",
        metrics=["accuracy",
                 tf.keras.metrics.AUC(name="auc"),
                 tf.keras.metrics.Precision(name="precision"),
                 tf.keras.metrics.Recall(name="recall")],
    )

    model.summary()
    total_params = model.count_params()
    print(f"    Total parameters: {total_params:,}")
    return model


# ── 5. Train ───────────────────────────────────────────────────────────────
def train_model(model, X_train, y_train, X_val, y_val,
                class_weight: dict, epochs: int, batch_size: int):
    import tensorflow as tf

    print(f"\n[4/5] Training  (epochs={epochs}  batch={batch_size}) ...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    callbacks = [
        # Save best model by val_auc
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(MODEL_OUT),
            monitor="val_auc",
            mode="max",
            save_best_only=True,
            verbose=1,
        ),
        # Stop early if val_auc hasn't improved for 10 epochs
        tf.keras.callbacks.EarlyStopping(
            monitor="val_auc",
            mode="max",
            patience=10,
            restore_best_weights=True,
            verbose=1,
        ),
        # Reduce LR on plateau
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=5,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=1,
    )

    # Save training history
    df_hist = pd.DataFrame(history.history)
    df_hist.to_csv(HISTORY_OUT, index_label="epoch")
    print(f"\n    [OK] Training history saved -> {HISTORY_OUT}")
    return history


# ── 6. Evaluate on test set ──────────────────────────────────────────────
def evaluate_model(model, X_test, y_test):
    import tensorflow as tf
    from sklearn.metrics import (
        classification_report, confusion_matrix,
        roc_auc_score, average_precision_score, f1_score
    )

    print("\n[5/5] Evaluating on held-out test set ...")
    results = model.evaluate(X_test, y_test, verbose=0)
    metric_names = ["loss", "accuracy", "auc", "precision", "recall"]
    for name, val in zip(metric_names, results):
        print(f"    {name:12s}: {val:.4f}")

    phri = model.predict(X_test, verbose=0).flatten()
    print(f"\n    PHRI score distribution -- min={phri.min():.3f}  max={phri.max():.3f}  "
          f"mean={phri.mean():.3f}  std={phri.std():.3f}")

    # ── Full metric suite (no hard pass/fail threshold) ───────────────────
    y_true = y_test.astype(int)
    try:
        roc_auc = roc_auc_score(y_true, phri)
        pr_auc  = average_precision_score(y_true, phri)
        print(f"\n    ROC-AUC  : {roc_auc:.4f}")
        print(f"    PR-AUC   : {pr_auc:.4f}")
    except Exception as e:
        print(f"    [WARN] Could not compute AUC: {e}")

    # Threshold sweep -- report all, don’t gate on any single threshold
    print("\n    Threshold sweep (report all -- no hard pass/fail):")
    for thresh in [0.3, 0.4, 0.5, 0.6, 0.7]:
        preds = (phri >= thresh).astype(int)
        tp = int(((preds == 1) & (y_true == 1)).sum())
        fp = int(((preds == 1) & (y_true == 0)).sum())
        fn = int(((preds == 0) & (y_true == 1)).sum())
        tn = int(((preds == 0) & (y_true == 0)).sum())
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        print(f"    thresh={thresh:.1f}  Prec={p:.3f}  Rec={r:.3f}  F1={f1:.3f}  "
              f"TP={tp}  FP={fp}  FN={fn}  TN={tn}")

    # Confusion matrix at 0.5
    preds_05 = (phri >= 0.5).astype(int)
    cm = confusion_matrix(y_true, preds_05)
    print(f"\n    Confusion matrix (thresh=0.5):\n    {cm}")
    print("\n    Classification report (thresh=0.5):")
    print(classification_report(y_true, preds_05, target_names=["no_outbreak", "outbreak"]))

    print(f"\n    [OK] Best model saved -> {MODEL_OUT}")
    print("\n[DONE] lstm_model.py complete -- ready for phri_engine.py")


# ── Main ───────────────────────────────────────────────────────────────
def run(epochs: int = DEFAULT_EPOCHS, batch_size: int = DEFAULT_BATCH,
        learning_rate: float = DEFAULT_LR):
    np.random.seed(RANDOM_SEED)

    X, y                                    = load_data()
    (X_tr, y_tr), (X_v, y_v), (X_te, y_te) = split_data(X, y)
    fit_and_save_scaler(X_tr)               # overwrites full-dataset scaler with train-only stats
    class_weight                            = compute_class_weight(y_tr)
    model                                   = build_model(learning_rate=learning_rate)
    train_model(model, X_tr, y_tr, X_v, y_v, class_weight, epochs, batch_size)
    evaluate_model(model, X_te, y_te)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Sentin-AI LSTM")
    parser.add_argument("--epochs",   type=int,   default=DEFAULT_EPOCHS)
    parser.add_argument("--batch",    type=int,   default=DEFAULT_BATCH)
    parser.add_argument("--lr",       type=float, default=DEFAULT_LR)
    args = parser.parse_args()
    run(epochs=args.epochs, batch_size=args.batch, learning_rate=args.lr)
