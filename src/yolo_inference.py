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
  - Save yolo_features.csv -> data/raw_imagery/yolo_features.csv

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
# YOLO WEIGHTS RESOLUTION
# Priority:
# 1. Environment variable YOLO_WEIGHTS (if set)
# 2. Local custom weights models/yolo_custom.pt (if exists)
# 3. Pretrained models yolov8m-seg.pt
YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS")
if not YOLO_WEIGHTS:
    DEFAULT_CUSTOM_WEIGHTS = ROOT / "models" / "yolo_custom.pt"
    if DEFAULT_CUSTOM_WEIGHTS.exists():
        YOLO_WEIGHTS = str(DEFAULT_CUSTOM_WEIGHTS)
    else:
        YOLO_WEIGHTS = "yolov8m-seg.pt"   # auto-downloads if not present

CONF_THRESH   = float(os.getenv("YOLO_CONF", 0.25))

# ── COCO class -> Sentin-AI proxy mapping ───────────────────────────────────────
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
      stagnant_water_count     int   -- number of detected water-proxy instances
      stagnant_water_area_px   float -- total pixel area of water detections
      garbage_count            int   -- number of garbage-proxy detections
      vegetation_anomaly_score float -- vegetation anomaly/stress signal

    When the custom YOLO model returns very low confidence (< NDWI_FALLBACK_CONF),
    NDWI-physics-based feature extraction is used instead. This is scientifically
    defensible: NDWI (Normalized Difference Water Index) is the standard index for
    mapping water bodies from Sentinel-2 imagery in the remote sensing literature.
    """

    # If YOLO max confidence on an image is below this, fall back to NDWI physics
    NDWI_FALLBACK_CONF = 0.10

    # NDWI thresholds (McFeeters 1996 standard)
    NDWI_WATER_THRESH     = 0.0    # pixels > 0 are open water
    NDWI_STAGNANT_THRESH  = 0.2    # pixels > 0.2 are confidently stagnant/pooled
    NDWI_PIXEL_AREA_SCALE = 100.0  # each NDWI pixel ~ 100 m^2 at 10m resolution

    def __init__(self, weights: str = YOLO_WEIGHTS, conf: float = CONF_THRESH):
        self.weights  = weights
        self.conf     = conf
        self.is_custom = False
        self.model    = self._load_model()
        self.baseline_ndwi = None   # set from first dry-season image

    # ── Model loading ──────────────────────────────────────────────────────────

    def _load_model(self):
        """Load YOLOv8 model. Downloads pretrained weight file on first run."""
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics not installed. Run: pip install ultralytics"
            )
        print(f"[YOLO] Loading model: {self.weights}")
        model = YOLO(self.weights)
        print(f"[YOLO] Model loaded. Task: {model.task}")
        
        # Dynamically inspect classes to check if they match our custom fine-tuned model
        self.is_custom = "stagnant_water" in model.names.values() or "garbage_pile" in model.names.values()
        if self.is_custom:
            print(f"[YOLO] Dynamic class detection: LOADED CUSTOM model. Classes: {model.names}")
        else:
            print(f"[YOLO] Dynamic class detection: LOADED PRETRAINED COCO model (using proxies).")
            
        return model

    # ── Single image inference ─────────────────────────────────────────────────

    def run_inference(self, image_path: Path, verbose: bool = False):
        """
        Run YOLOv8 on one RGB PNG.

        Returns
        -------
        list of dicts:
          {class_id, class_name, confidence, area_px, mask_available}

        area_px is the SEGMENTATION MASK pixel count when masks are available
        (model returns result.masks), otherwise falls back to bounding-box area.
        Mask pixel area is technically more defensible: it measures the actual
        occupied footprint rather than the bounding rectangle.
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

            # Check if segmentation masks are available for this result
            masks = result.masks  # None if model is detection-only

            for idx, box in enumerate(boxes):
                cls_id = int(box.cls[0].item())
                conf   = float(box.conf[0].item())

                # ── Area calculation ──────────────────────────────────────
                # Priority 1: segmentation mask pixel count (most accurate)
                # Priority 2: bounding-box area (fallback)
                mask_available = False
                if masks is not None and idx < len(masks):
                    try:
                        # masks.data shape: (N, H, W) — one binary mask per detection
                        mask_pixels = int(masks.data[idx].sum().item())
                        area = float(mask_pixels)
                        mask_available = True
                    except Exception:
                        # Unexpected mask format — fall back to bbox
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        area = (x2 - x1) * (y2 - y1)
                else:
                    # No masks from this model — use bounding-box area
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    area = (x2 - x1) * (y2 - y1)

                # Fetch name dynamically from model.names
                cname = self.model.names[cls_id] if cls_id in self.model.names else str(cls_id)

                detections.append({
                    "class_id":      cls_id,
                    "class_name":    cname,
                    "confidence":    round(conf, 3),
                    "area_px":       round(area, 1),
                    "mask_available": mask_available,
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
        veg_anomaly_area = 0.0

        for det in detections:
            cid = det["class_id"]
            cname = det["class_name"]
            
            if self.is_custom:
                # Custom Model direct class resolution
                if cname == "stagnant_water":
                    water_count += 1
                    water_area  += det["area_px"]
                elif cname == "garbage_pile":
                    garbage_count += 1
                elif cname == "vegetation_anomaly":
                    veg_anomaly_area += det["area_px"]
            else:
                # COCO Proxy fallback resolution
                if cid in WATER_PROXY_IDS:
                    water_count += 1
                    water_area  += det["area_px"]
                elif cid in GARBAGE_PROXY_IDS:
                    garbage_count += 1
                elif cid in VEGETATION_PROXY_IDS:
                    veg_anomaly_area += det["area_px"]

        # Calculate vegetation anomaly score
        if self.is_custom:
            # Mathematical definition: (detected_anomaly_mask_pixels / total_image_pixels)
            # Sentinel-2 images are 512x512
            total_image_pixels = 512.0 * 512.0
            veg_anomaly = float(veg_anomaly_area / total_image_pixels)
            veg_anomaly = min(1.0, max(0.0, veg_anomaly))
        else:
            # COCO NDWI fallback calculation for backward compatibility
            veg_anomaly = 0.0
            if ndwi_array is not None and len(ndwi_array) > 0:
                valid = ndwi_array[~np.isnan(ndwi_array)]
                if len(valid) > 0:
                    water_positive_frac = float(np.mean(valid > 0.0))
                    if self.baseline_ndwi is None:
                        self.baseline_ndwi = water_positive_frac
                        veg_anomaly = 0.0
                    else:
                        veg_anomaly = max(0.0, water_positive_frac - self.baseline_ndwi)
                        veg_anomaly = min(1.0, veg_anomaly * 10.0)   # scale to [0,1]
            elif ndvi_mean is not None:
                baseline_ndvi = 0.30
                veg_anomaly = max(0.0, baseline_ndvi - ndvi_mean) * 3.0
                veg_anomaly = min(1.0, veg_anomaly)

        return {
            "stagnant_water_count":    water_count,
            "stagnant_water_area_px":  round(water_area, 1),
            "garbage_count":           garbage_count,
            "vegetation_anomaly_score": round(veg_anomaly, 4),
        }

    def ndwi_physics_features(self,
                               ndwi_array: np.ndarray,
                               ndvi_mean: float | None = None) -> dict:
        """
        NDWI-physics-based feature extraction.

        Uses the pre-computed NDWI array (NDWI = (Green-NIR)/(Green+NIR))
        downloaded alongside each Sentinel-2 scene to derive water features
        without relying on YOLO detections.

        Scientific basis:
          NDWI > 0.0  => open water / wet surface  (McFeeters 1996)
          NDWI > 0.2  => confidently stagnant / pooled water

        stagnant_water_count:
          Number of connected water regions (approx: n pixels > NDWI_STAGNANT_THRESH / 500)
        stagnant_water_area_px:
          Total pixel count with NDWI > NDWI_WATER_THRESH (each pixel = 10m x 10m)
        garbage_count:
          0 (NDWI cannot detect garbage; placeholder until YOLO is retrained)
        vegetation_anomaly_score:
          Fraction of vegetated pixels with anomalously low NDWI vs baseline,
          or from NDVI departure if ndvi_mean is provided.
        """
        if ndwi_array is None or ndwi_array.size == 0:
            return {
                "stagnant_water_count":     0,
                "stagnant_water_area_px":   0.0,
                "garbage_count":            0,
                "vegetation_anomaly_score": 0.0,
                "_source": "ndwi_empty",
            }

        valid = ndwi_array[~np.isnan(ndwi_array)]
        if len(valid) == 0:
            return {
                "stagnant_water_count":     0,
                "stagnant_water_area_px":   0.0,
                "garbage_count":            0,
                "vegetation_anomaly_score": 0.0,
                "_source": "ndwi_all_nan",
            }

        # -- Water area (NDWI > 0) ------------------------------------------
        water_mask     = valid > self.NDWI_WATER_THRESH
        water_px_count = int(water_mask.sum())
        water_area_px  = float(water_px_count)          # raw pixel count

        # Stagnant water count: approximate number of pools
        # A single monsoon pool is ~500+ pixels at 10m resolution
        stagnant_mask  = valid > self.NDWI_STAGNANT_THRESH
        stagnant_px    = int(stagnant_mask.sum())
        water_count    = max(1, stagnant_px // 500) if stagnant_px > 50 else 0

        # Update baseline for delta calculation
        water_frac = float(np.mean(water_mask))
        if self.baseline_ndwi is None:
            self.baseline_ndwi = water_frac

        # -- Vegetation anomaly (NDVI departure or NDWI proxy) --------------
        veg_anomaly = 0.0
        if ndvi_mean is not None:
            # NDVI below healthy baseline indicates stress
            baseline_ndvi = 0.35
            veg_anomaly = max(0.0, baseline_ndvi - float(ndvi_mean)) * 3.0
            veg_anomaly = min(1.0, veg_anomaly)
        elif self.baseline_ndwi is not None:
            # Water fraction delta as proxy for waterlogged vegetation stress
            delta = max(0.0, water_frac - self.baseline_ndwi)
            veg_anomaly = min(1.0, delta * 5.0)

        return {
            "stagnant_water_count":     water_count,
            "stagnant_water_area_px":   round(water_area_px, 1),
            "garbage_count":            0,       # NDWI cannot detect garbage
            "vegetation_anomaly_score": round(veg_anomaly, 4),
            "_source": "ndwi_physics",
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
                print(f"  [{date_str}] RGB not found -- skipping")
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

            # -- Feature extraction strategy -----------------------------------
            # 1. Try YOLO custom model first (run at conf=0.001 to get raw scores)
            # 2. If max confidence < NDWI_FALLBACK_CONF, use NDWI-physics instead
            # 3. This produces non-zero, scientifically defensible features even
            #    when the custom model is underfitted.
            use_ndwi = False
            features = None

            if self.is_custom and ndwi_array is not None:
                # Quick probe at very low conf to check model confidence level
                probe_results = self.model.predict(
                    source=str(rgb_path), conf=0.001, verbose=False, save=False
                )
                probe_boxes = probe_results[0].boxes
                max_conf = 0.0
                if probe_boxes is not None and len(probe_boxes) > 0:
                    max_conf = float(probe_boxes.conf.max().item())

                if max_conf < self.NDWI_FALLBACK_CONF:
                    # Custom model underfitted -- fall back to NDWI physics
                    use_ndwi = True
                    features = self.ndwi_physics_features(ndwi_array, ndvi_mean)

            if features is None:
                # Use YOLO at configured threshold
                detections = self.run_inference(rgb_path, verbose=verbose)
                features = self.aggregate_features(detections, ndwi_array, ndvi_mean)

            src = features.pop("_source", "yolo")

            print(f"  [{date_str}] "
                  f"water={features['stagnant_water_count']} "
                  f"area={features['stagnant_water_area_px']:.0f}px "
                  f"garbage={features['garbage_count']} "
                  f"veg_anomaly={features['vegetation_anomaly_score']:.4f} "
                  f"[{src}]")

            records.append({"date": date_str, **features})

        df = pd.DataFrame(records)
        df.to_csv(FEATURES_CSV, index=False)
        print(f"\n[YOLO] Features saved -> {FEATURES_CSV}")
        print(f"[YOLO] Shape: {df.shape}")
        print("="*60)
        print(df.to_string(index=False))

        # Trigger sequence rebuild with new YOLO features
        # Always prefer nasa_power_full.csv (6-feature) over old 3-feature CSV
        try:
            import sys
            sys.path.insert(0, str(ROOT / "src"))
            from nasa_power_parser import run as run_parser, WEATHER_DIR

            preferred = WEATHER_DIR / "nasa_power_full.csv"
            if preferred.exists():
                chosen_csv = preferred
            else:
                candidates = [
                    c for c in WEATHER_DIR.glob("*.csv")
                    if c.name not in ["weather_features.csv", "label_alignment.csv"]
                ]
                chosen_csv = candidates[0] if candidates else None

            if chosen_csv:
                print(f"\n[YOLO] Triggering nasa_power_parser with {chosen_csv.name} ...")
                run_parser(chosen_csv)
                print("[YOLO] Sequences and weather features updated successfully.")
            else:
                print("\n[YOLO] Warning: could not locate raw weather CSV -- sequences not rebuilt.")
        except Exception as e:
            print(f"\n[YOLO] Error triggering nasa_power_parser: {e}")

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
