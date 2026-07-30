"""
yolo_inference.py
=================
Step 10 of the Sentin-AI build order.  Phase 4 — Satellite.

Responsibilities:
  - Load each Sentinel-2 RGB PNG from data/raw_imagery/
  - Run YOLOv8m-seg.pt inference on each image
  - Map COCO classes to Sentin-AI proxy classes:
      stagnant_water  <- boat, surfboard, frisbee (water-adjacent COCO proxies)
      garbage_pile    <- suitcase, backpack, handbag, bottle, cup, fork, knife
      vegetation      <- potted plant (vegetated area proxy)
  - Compute NDWI-based water extent from the saved .npy arrays
  - Aggregate into the 4-feature vector the LSTM expects per timestep:
      stagnant_water_count    (int)
      stagnant_water_area_px  (float)
      garbage_count           (int)
      vegetation_anomaly_score (float, NDVI delta from baseline)
  - Save yolo_features.csv → data/raw_imagery/yolo_features.csv

NOTE on model:
  Using yolov8m-seg.pt (COCO pretrained) as a stand-in.
  When yolo_custom.pt (fine-tuned on Indian imagery) is available,
  set YOLO_WEIGHTS in .env and it will be picked up automatically.

Usage (CLI):
  python src/yolo_inference.py
  python src/yolo_inference.py --conf 0.25 --verbose

Usage (as module):
  from yolo_inference import YOLOInference
  yolo = YOLOInference()
  features = yolo.run_all()   # returns DataFrame
"""

import argparse
import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
IMAGERY_DIR = ROOT / "data" / "raw_imagery"
METADATA_CSV  = IMAGERY_DIR / "sentinel2_metadata.csv"
FEATURES_CSV  = IMAGERY_DIR / "yolo_features.csv"

# ── Config ─────────────────────────────────────────────────────────────────────
YOLO_WEIGHTS  = os.getenv("YOLO_WEIGHTS", "yolov8m-seg.pt")   # auto-downloads if not present
CONF_THRESH   = float(os.getenv("YOLO_CONF", 0.25))

# ── COCO class → Sentin-AI proxy mapping ───────────────────────────────────────
# COCO class names (80 classes, 0-indexed)
# We use proxies since custom fine-tuned weights don't exist yet.
COCO_CLASSES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack",
    "umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball",
    "kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket",
    "bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair",
    "couch","potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator",
    "book","clock","vase","scissors","teddy bear","hair drier","toothbrush"
]

# Proxy class IDs
WATER_PROXY_IDS = {
    8,   # boat
    29,  # frisbee (circular water reflections)
    37,  # surfboard
}

GARBAGE_PROXY_IDS = {
    24,  # backpack
    26,  # handbag
    28,  # suitcase
    39,  # bottle
    41,  # cup
    43,  # fork
    44,  # knife
    45,  # spoon
    46,  # bowl
}

VEGETATION_PROXY_IDS = {
    58,  # potted plant
}


class YOLOInference:
    """
    Runs YOLOv8 on Sentinel-2 RGB PNGs and extracts the
    4-feature vector required by the PHRI LSTM.

    Feature vector (per image / timestep):
      stagnant_water_count     int   — number of detected water-proxy boxes
      stagnant_water_area_px   float — total pixel area of water detections
      garbage_count            int   — number of garbage-proxy detections
      vegetation_anomaly_score float — NDWI-based water extent score
                                       (higher = more water than baseline)
    """

    def __init__(self, weights: str = YOLO_WEIGHTS, conf: float = CONF_THRESH):
        self.weights  = weights
        self.conf     = conf
        self.model    = self._load_model()
        self.baseline_ndwi = None   # set from first dry-season image

    # ── Model loading ──────────────────────────────────────────────────────────

    def _load_model(self):
        """Load YOLOv8 model. Downloads yolov8m-seg.pt on first run (~50 MB)."""
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics not installed. Run: pip install ultralytics"
            )
        print(f"[YOLO] Loading model: {self.weights}")
        model = YOLO(self.weights)
        print(f"[YOLO] Model loaded. Task: {model.task}")
        return model

    # ── Single image inference ─────────────────────────────────────────────────

    def run_inference(self, image_path: Path, verbose: bool = False):
        """
        Run YOLOv8 on one RGB PNG.

        Returns
        -------
        list of dicts: [{class_id, class_name, confidence, area_px}, ...]
        """
        results = self.model.predict(
            source=str(image_path),
            conf=self.conf,
            verbose=verbose,
            save=False,
        )

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf   = float(box.conf[0].item())
                # Bounding box area in pixels
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                detections.append({
                    "class_id":   cls_id,
                    "class_name": COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else str(cls_id),
                    "confidence": round(conf, 3),
                    "area_px":    round(area, 1),
                })

        return detections

    # ── Feature aggregation ────────────────────────────────────────────────────

    def aggregate_features(
        self,
        detections: list,
        ndwi_array: np.ndarray | None = None,
        ndvi_mean:  float | None = None,
    ) -> dict:
        """
        Aggregate raw YOLO detections into the 4-feature LSTM vector.

        Parameters
        ----------
        detections : list of detection dicts from run_inference()
        ndwi_array : np.ndarray | None — NDWI pixel values from .npy file
        ndvi_mean  : float | None      — mean NDVI from GEE metadata

        Returns
        -------
        dict with keys:
          stagnant_water_count, stagnant_water_area_px,
          garbage_count, vegetation_anomaly_score
        """
        water_count  = 0
        water_area   = 0.0
        garbage_count = 0

        for det in detections:
            cid = det["class_id"]
            if cid in WATER_PROXY_IDS:
                water_count += 1
                water_area  += det["area_px"]
            elif cid in GARBAGE_PROXY_IDS:
                garbage_count += 1

        # ── NDWI-based vegetation anomaly score ───────────────────────────────
        # We use NDWI positivity fraction as a proxy for water extent.
        # Higher fraction = more standing water than baseline = higher risk.
        veg_anomaly = 0.0
        if ndwi_array is not None and len(ndwi_array) > 0:
            valid = ndwi_array[~np.isnan(ndwi_array)]
            if len(valid) > 0:
                # Fraction of pixels with NDWI > 0 (water-positive)
                water_positive_frac = float(np.mean(valid > 0.0))

                # Set baseline from first observation
                if self.baseline_ndwi is None:
                    self.baseline_ndwi = water_positive_frac
                    veg_anomaly = 0.0
                else:
                    # Anomaly = deviation above baseline (capped at 1.0)
                    veg_anomaly = max(0.0, water_positive_frac - self.baseline_ndwi)
                    veg_anomaly = min(1.0, veg_anomaly * 10.0)   # scale to [0,1]
        elif ndvi_mean is not None:
            # Fallback: use NDVI depression as anomaly indicator
            # Low NDVI relative to typical Bengaluru (~0.30) = stress
            baseline_ndvi = 0.30
            veg_anomaly = max(0.0, baseline_ndvi - ndvi_mean) * 3.0
            veg_anomaly = min(1.0, veg_anomaly)

        return {
            "stagnant_water_count":    water_count,
            "stagnant_water_area_px":  round(water_area, 1),
            "garbage_count":           garbage_count,
            "vegetation_anomaly_score": round(veg_anomaly, 4),
        }

    def run_single_image(self, rgb_path: Path, npy_path: Path | None = None, ndvi_mean: float | None = None) -> dict:
        """Process a single image and return its 4-feature vector."""
        ndwi_arr = None
        if npy_path and npy_path.exists():
            ndwi_arr = np.load(npy_path)
        detections = self.run_inference(rgb_path)
        features = self.aggregate_features(detections, ndwi_arr, ndvi_mean)
        return features


    # ── Batch run over all downloaded images ───────────────────────────────────

    def run_all(self, verbose: bool = False) -> pd.DataFrame:
        """
        Process all Sentinel-2 images in data/raw_imagery/.
        Reads sentinel2_metadata.csv to get the list of dates.

        Returns
        -------
        pd.DataFrame saved to data/raw_imagery/yolo_features.csv
        """
        print("\n" + "="*60)
        print("  Sentin-AI | YOLO Inference Pipeline")
        print("="*60)

        if not METADATA_CSV.exists():
            raise FileNotFoundError(
                f"Metadata not found: {METADATA_CSV}\n"
                "Run gee_pipeline.py first."
            )

        meta_df = pd.read_csv(METADATA_CSV)
        print(f"[YOLO] Processing {len(meta_df)} images...")

        records = []

        for _, row in meta_df.iterrows():
            date_str  = row["date"]
            ndvi_mean = row.get("ndvi_mean", None)
            if pd.isna(ndvi_mean):
                ndvi_mean = None

            rgb_path = IMAGERY_DIR / f"S2_{date_str}_rgb.png"
            npy_path = IMAGERY_DIR / f"S2_{date_str}_ndwi.npy"

            if not rgb_path.exists():
                print(f"  [{date_str}] RGB not found — skipping")
                records.append({"date": date_str,
                                "stagnant_water_count": 0,
                                "stagnant_water_area_px": 0.0,
                                "garbage_count": 0,
                                "vegetation_anomaly_score": 0.0})
                continue

            # Load NDWI array if available
            ndwi_array = None
            if npy_path.exists():
                ndwi_array = np.load(npy_path)

            # Run YOLO inference
            detections = self.run_inference(rgb_path, verbose=verbose)

            # Aggregate to 4-feature vector
            features = self.aggregate_features(detections, ndwi_array, ndvi_mean)

            print(f"  [{date_str}] "
                  f"water={features['stagnant_water_count']} "
                  f"area={features['stagnant_water_area_px']:.0f}px "
                  f"garbage={features['garbage_count']} "
                  f"veg_anomaly={features['vegetation_anomaly_score']:.4f} "
                  f"| {len(detections)} total detections")

            records.append({"date": date_str, **features})

        df = pd.DataFrame(records)
        df.to_csv(FEATURES_CSV, index=False)
        print(f"\n[YOLO] Features saved -> {FEATURES_CSV}")
        print(f"[YOLO] Shape: {df.shape}")
        print("="*60)
        print(df.to_string(index=False))
        return df


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sentin-AI: YOLO inference on Sentinel-2 imagery"
    )
    parser.add_argument(
        "--conf", type=float, default=CONF_THRESH,
        help=f"YOLO confidence threshold (default: {CONF_THRESH})"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print YOLO per-image detection details"
    )
    args = parser.parse_args()

    yolo = YOLOInference(conf=args.conf)
    yolo.run_all(verbose=args.verbose)


if __name__ == "__main__":
    main()
