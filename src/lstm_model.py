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
  - Save trained model → models/lstm_phri.h5

Architecture (from README):
  Input(30, 10) → LSTM(128) → LSTM(64) → Dense(64) →
  Dropout(0.3) → Dense(1, sigmoid) → PHRI ∈ [0.0, 1.0]

Usage:
  python src/lstm_model.py
  python src/lstm_model.py --epochs 50 --batch 32
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
WEATHER_DIR = ROOT / "data" / "weather_cache"
MODELS_DIR  = ROOT / "models"

SEQ_PATH    = WEATHER_DIR / "lstm_sequences.npy"
LABEL_PATH  = WEATHER_DIR / "lstm_labels.npy"
MODEL_OUT   = MODELS_DIR  / "lstm_phri.h5"
HISTORY_OUT = MODELS_DIR  / "training_history.csv"

# ── Defaults ───────────────────────────────────────────────────────────────
DEFAULT_EPOCHS     = 60
DEFAULT_BATCH      = 32
DEFAULT_LR         = 1e-3
TRAIN_FRAC         = 0.70
VAL_FRAC           = 0.15
# TEST_FRAC        = 0.15  (remainder)
RANDOM_SEED        = 42


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
    print(f"    Class balance — positive: {int(y.sum())} ({100*y.mean():.1f}%)  "
          f"negative: {int((y==0).sum())}")
    return X, y


# ── 2. Train / val / test split (time-ordered, no shuffle) ────────────────
def split_data(X: np.ndarray, y: np.ndarray):
    """
    Keep temporal order — do NOT shuffle time-series sequences.
    Split: first 70% → train, next 15% → val, last 15% → test.
    """
    print("[2/5] Splitting data (time-ordered) ...")
    N = len(X)
    train_end = int(N * TRAIN_FRAC)
    val_end   = int(N * (TRAIN_FRAC + VAL_FRAC))

    X_train, y_train = X[:train_end],       y[:train_end]
    X_val,   y_val   = X[train_end:val_end], y[train_end:val_end]
    X_test,  y_test  = X[val_end:],          y[val_end:]

    print(f"    Train : {X_train.shape}  pos={int(y_train.sum())}")
    print(f"    Val   : {X_val.shape}    pos={int(y_val.sum())}")
    print(f"    Test  : {X_test.shape}   pos={int(y_test.sum())}")
    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


# ── 3. Class weight (handle imbalance) ────────────────────────────────────
def compute_class_weight(y_train: np.ndarray) -> dict:
    """
    Outbreak sequences are rare (~15%). Weight the positive class
    inversely to its frequency so the model doesn't just predict 0.
    """
    n_neg = int((y_train == 0).sum())
    n_pos = int(y_train.sum())
    if n_pos == 0:
        print("    ⚠  No positive samples in train set — class weights not applied.")
        return {0: 1.0, 1: 1.0}
    weight_pos = n_neg / n_pos
    print(f"    Class weights — 0: 1.0  1: {weight_pos:.2f}")
    return {0: 1.0, 1: weight_pos}


# ── 4. Model definition ────────────────────────────────────────────────────
def build_model(timesteps: int = 30, features: int = 10,
                learning_rate: float = DEFAULT_LR):
    """
    Architecture from README Section 2:
      Input(30, 10) → LSTM(128) → LSTM(64) → Dense(64) →
      Dropout(0.3)  → Dense(1, sigmoid)
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
    print(f"\n    ✅ Training history saved → {HISTORY_OUT}")
    return history


# ── 6. Evaluate on test set ────────────────────────────────────────────────
def evaluate_model(model, X_test, y_test):
    import tensorflow as tf

    print("\n[5/5] Evaluating on held-out test set ...")
    results = model.evaluate(X_test, y_test, verbose=0)
    metric_names = ["loss", "accuracy", "auc", "precision", "recall"]
    for name, val in zip(metric_names, results):
        print(f"    {name:12s}: {val:.4f}")

    # PHRI threshold sweep on test set
    phri = model.predict(X_test, verbose=0).flatten()
    print(f"\n    PHRI scores — min={phri.min():.3f}  max={phri.max():.3f}  "
          f"mean={phri.mean():.3f}")
    print("\n    Threshold sweep:")
    for thresh in [0.4, 0.5, 0.6, 0.7, 0.8]:
        preds = (phri >= thresh).astype(int)
        true  = y_test.astype(int)
        tp = int(((preds == 1) & (true == 1)).sum())
        fp = int(((preds == 1) & (true == 0)).sum())
        fn = int(((preds == 0) & (true == 1)).sum())
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        marker = " ◀ target" if thresh == 0.7 else ""
        print(f"    thresh={thresh:.1f}  P={p:.3f}  R={r:.3f}  "
              f"TP={tp}  FP={fp}  FN={fn}{marker}")

    print(f"\n    ✅ Best model saved → {MODEL_OUT}")
    print("\n🎉 lstm_model.py complete — ready for Step 5 (phri_engine.py)")


# ── Main ───────────────────────────────────────────────────────────────────
def run(epochs: int = DEFAULT_EPOCHS, batch_size: int = DEFAULT_BATCH,
        learning_rate: float = DEFAULT_LR):
    np.random.seed(RANDOM_SEED)

    X, y                              = load_data()
    (X_tr, y_tr), (X_v, y_v), (X_te, y_te) = split_data(X, y)
    class_weight                      = compute_class_weight(y_tr)
    model                             = build_model(learning_rate=learning_rate)
    train_model(model, X_tr, y_tr, X_v, y_v, class_weight, epochs, batch_size)
    evaluate_model(model, X_te, y_te)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Sentin-AI LSTM")
    parser.add_argument("--epochs",   type=int,   default=DEFAULT_EPOCHS)
    parser.add_argument("--batch",    type=int,   default=DEFAULT_BATCH)
    parser.add_argument("--lr",       type=float, default=DEFAULT_LR)
    args = parser.parse_args()
    run(epochs=args.epochs, batch_size=args.batch, learning_rate=args.lr)