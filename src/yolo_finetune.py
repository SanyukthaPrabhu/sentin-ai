"""
yolo_finetune.py
================
Sentin-AI: Custom YOLOv8 Fine-Tuning and Label Studio Integration script.
Phase 1 — Steps 1-5.

This script implements:
  1. Data Separation: Splits available Sentinel-2 scenes into separate training and validation sets.
  2. Candidate Generation: Programmatically finds candidate stagnant water, garbage, and vegetation anomalies.
  3. Label Studio Bridge: Saves candidates to data/yolo_candidates/ with visual labeling instructions.
  4. Smoke Test Mode: If --smoke-test is specified, copies candidates to data/yolo_dataset/ for verification.
  5. Fine-Tuning: Trains a custom 3-class YOLOv8 segmentation model.
  6. Evaluation: Evaluates validation splits and prints mAP50 and mAP50-95 metrics.
"""

import os
import shutil
import argparse
import random
import numpy as np
import cv2
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).resolve().parent.parent
IMAGERY_DIR    = ROOT / "data" / "raw_imagery"
CANDIDATES_DIR = ROOT / "data" / "yolo_candidates"
DATASET_DIR    = ROOT / "data" / "yolo_dataset"
MODELS_DIR     = ROOT / "models"

# ── Classes ────────────────────────────────────────────────────────────────────
CLASSES = {
    0: "stagnant_water",
    1: "garbage_pile",
    2: "vegetation_anomaly"
}


def print_label_studio_instructions():
    """Prints a clear guide on the Label Studio human-in-the-loop workflow."""
    msg = """
================================================================================
      LABEL STUDIO BRIDGE - HUMAN-IN-THE-LOOP VERIFICATION WORKFLOW
================================================================================
Sentin-AI requires high-quality, human-verified labels. Follow these steps:

1. Candidate annotations have been generated in:
   📂 data/yolo_candidates/

2. Human Verification Setup:
   a. Install and start Label Studio:
      $ pip install label-studio
      $ label-studio
   b. Create a project named: "Sentin-AI Environmental Perception"
   c. Under 'Labeling Setup', select 'Semantic Segmentation with Polygons'
   d. Define three labels exactly:
      - stagnant_water
      - garbage_pile
      - vegetation_anomaly
   e. Import images from: data/yolo_candidates/images/ (train/val)
   f. Import candidate labels (or manually annotate). Verify and correct boundaries.
   g. Export the verified labels in "YOLO" format.
   h. Extract the zip file contents directly into:
      📂 data/yolo_dataset/

3. Model Training:
   Once the verified dataset is ready, run this script WITHOUT the --smoke-test flag:
   $ python src/yolo_finetune.py --epochs 30 --weights yolov8n-seg.pt
================================================================================
"""
    print(msg)


def generate_candidate_labels(img_path: Path) -> list:
    """
    Uses simple computer vision heuristics to find candidate coordinates
    representing stagnant water, garbage, and vegetation anomalies.
    Returns list of YOLO-format annotation strings.
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return []
    h, w, c = img.shape

    annotations = []

    # Helper to convert OpenCV contours to YOLO polygon string
    def contour_to_yolo_str(class_id: int, contour: np.ndarray) -> str:
        points = contour.reshape(-1, 2)
        norm_coords = []
        for pt in points:
            norm_coords.append(f"{pt[0] / w:.6f} {pt[1] / h:.6f}")
        return f"{class_id} " + " ".join(norm_coords)

    # 1. Class 0: Stagnant Water Candidates (Dark, blue/gray areas)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, water_mask = cv2.threshold(gray, 65, 255, cv2.THRESH_BINARY_INV)
    contours_water, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    water_count = 0
    for cnt in contours_water:
        area = cv2.contourArea(cnt)
        if 80 < area < 20000:  # size bounds
            annotations.append(contour_to_yolo_str(0, cnt))
            water_count += 1

    # 2. Class 1: Garbage Pile Candidates (Small, high-contrast anomalies)
    edges = cv2.Canny(gray, 60, 160)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dilated = cv2.dilate(edges, kernel)
    contours_garbage, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    garbage_count = 0
    for cnt in contours_garbage:
        area = cv2.contourArea(cnt)
        if 20 < area < 400:
            annotations.append(contour_to_yolo_str(1, cnt))
            garbage_count += 1

    # 3. Class 2: Vegetation Anomaly Candidates (Stressed brown/yellow patches)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_brown = np.array([8, 40, 40])
    upper_brown = np.array([24, 255, 180])
    veg_mask = cv2.inRange(hsv, lower_brown, upper_brown)
    contours_veg, _ = cv2.findContours(veg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    veg_count = 0
    for cnt in contours_veg:
        area = cv2.contourArea(cnt)
        if 100 < area < 12000:
            annotations.append(contour_to_yolo_str(2, cnt))
            veg_count += 1

    # Guarantee representation of all classes to avoid training errors during smoke test
    # (Adds small synthetic polygons if a class has zero candidate detections)
    if water_count == 0:
        # Mock water polygon (square near top-left)
        x, y, size = int(w * 0.1), int(h * 0.1), int(w * 0.05)
        cnt = np.array([[[x, y]], [[x+size, y]], [[x+size, y+size]], [[x, y+size]]])
        annotations.append(contour_to_yolo_str(0, cnt))
    if garbage_count == 0:
        # Mock garbage polygon (triangle near bottom-left)
        x, y, size = int(w * 0.15), int(h * 0.8), int(w * 0.03)
        cnt = np.array([[[x, y]], [[x+size, y]], [[x, y+size]]])
        annotations.append(contour_to_yolo_str(1, cnt))
    if veg_count == 0:
        # Mock vegetation anomaly polygon (square near bottom-right)
        x, y, size = int(w * 0.8), int(h * 0.8), int(w * 0.06)
        cnt = np.array([[[x, y]], [[x+size, y]], [[x+size, y+size]], [[x, y+size]]])
        annotations.append(contour_to_yolo_str(2, cnt))

    return annotations


def prepare_dataset(smoke_test: bool):
    """Selects images and generates candidates in data/yolo_candidates/."""
    print("[Dataset] Scanning raw imagery in data/raw_imagery/...")
    rgb_files = sorted(IMAGERY_DIR.glob("S2_*_rgb.png"))

    if len(rgb_files) < 7:
        raise ValueError(
            f"Insufficient satellite images in {IMAGERY_DIR} (found {len(rgb_files)}, need at least 7)."
        )

    # Separate train (5) and val (2)
    # Using deterministic splits to separate training images from validation/inference
    train_files = rgb_files[:5]
    val_files   = rgb_files[5:7]

    print(f"[Dataset] Split: Training={len(train_files)} files | Validation={len(val_files)} files")

    # Clean previous candidates
    if CANDIDATES_DIR.exists():
        shutil.rmtree(CANDIDATES_DIR)

    # Create directory structure
    for split in ["train", "val"]:
        (CANDIDATES_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (CANDIDATES_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Process and save candidate labels
    for split, files in [("train", train_files), ("val", val_files)]:
        for f in files:
            # Copy image
            shutil.copy(f, CANDIDATES_DIR / "images" / split / f.name)
            # Generate and save labels
            labels = generate_candidate_labels(f)
            lbl_name = f.stem + ".txt"
            lbl_path = CANDIDATES_DIR / "labels" / split / lbl_name
            with open(lbl_path, "w") as out:
                out.write("\n".join(labels))

    print(f"[Dataset] Candidate dataset built at {CANDIDATES_DIR}")

    # Handle Smoke Test copying if requested
    if smoke_test:
        print("[Dataset] [--smoke-test flag active] Copying candidates to data/yolo_dataset/...")
        if DATASET_DIR.exists():
            shutil.rmtree(DATASET_DIR)
        shutil.copytree(CANDIDATES_DIR, DATASET_DIR)
        print(f"[Dataset] Verified dataset folder populated at {DATASET_DIR} (Smoke Test Fallback)")


def train_yolo(epochs: int, base_weights: str):
    """Trains the custom YOLOv8 model using the verified dataset."""
    if not DATASET_DIR.exists():
        print(f"\n❌ Error: Verified dataset directory not found at {DATASET_DIR}")
        print("Please review the Label Studio workflow instructions below:")
        print_label_studio_instructions()
        return

    # Check for library
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError("ultralytics not installed. Run: pip install ultralytics")

    print("\n" + "="*60)
    print("  Sentin-AI | YOLOv8 Fine-Tuning Pipeline")
    print("="*60)

    # Create dataset yaml file
    yaml_path = DATASET_DIR / "dataset.yaml"
    yaml_content = f"""
path: {DATASET_DIR.resolve().as_posix()}
train: images/train
val: images/val
names:
  0: stagnant_water
  1: garbage_pile
  2: vegetation_anomaly
"""
    with open(yaml_path, "w") as f:
        f.write(yaml_content.strip())

    print(f"[Train] Created dataset configuration: {yaml_path}")
    print(f"[Train] Pretrained Weights model: {base_weights}")
    print(f"[Train] Fine-tuning epochs: {epochs}")

    # Resource check and warning for panel presentation
    is_nano = "n" in base_weights
    print(f"[Train] Note: Using {'YOLOv8-Nano' if is_nano else 'YOLOv8-Medium'} model.")
    if is_nano:
        print("        * Nano is selected for rapid execution on local hardware.")
        print("        * In production deployment, yolov8m-seg.pt (Medium) is selected for higher precision.")

    model = YOLO(base_weights)

    # Run fine-tuning
    # Disable cache to avoid memory overhead, set imgsz=512 matching sentinel imagery size
    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=512,
        batch=2,
        device="cpu",  # default to CPU for portability
        cache=False,
        project=str(ROOT / "runs"),
        name="segment_train"
    )

    print("\n[Train] Training completed successfully!")

    # Load custom validation metrics
    print("\n[Evaluation] Validating model on held-out validation set...")
    val_metrics = model.val()

    # Access segmentation mAP50 and mAP50-95
    # val_metrics.seg returns SegmentMetrics object
    map50 = val_metrics.seg.map50
    map95 = val_metrics.seg.map

    print("\n" + "-"*50)
    print("  YOLO VALIDATION METRICS (Segmentation)")
    print("-"*50)
    print(f"  mAP50     : {map50:.4f}")
    print(f"  mAP50-95  : {map95:.4f}")
    print("-"*50)
    print("  ⚠️  WARNING: This is a pipeline smoke test trained on mock candidate regions.")
    print("     These accuracy metrics are NOT indicative of real-world model performance.")
    print("-"*50)

    # Save to models/yolo_custom.pt
    best_weights_path = ROOT / "runs" / "segment_train" / "weights" / "best.pt"
    if best_weights_path.exists():
        MODELS_DIR.mkdir(exist_ok=True)
        out_weights = MODELS_DIR / "yolo_custom.pt"
        shutil.copy(best_weights_path, out_weights)
        print(f"\n✅ Fine-tuned weights saved successfully -> {out_weights}")
    else:
        print("\n❌ Error: Could not locate trained weights file runs/segment_train/weights/best.pt")


def main():
    parser = argparse.ArgumentParser(description="Sentin-AI: YOLOv8 Custom Fine-Tuning and Annotation Workflow")
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of fine-tuning epochs (default: 3 for smoke test)"
    )
    parser.add_argument(
        "--weights", type=str, default="yolov8n-seg.pt",
        help="Pretrained YOLO base weights to fine-tune (default: yolov8n-seg.pt)"
    )
    parser.add_argument(
        "--smoke-test", action="store_true",
        help="Execute a quick end-to-end smoke test using programmatically copied candidate labels"
    )
    args = parser.parse_args()

    # 1. Prepare candidates & handle smoke test data copy
    prepare_dataset(smoke_test=args.smoke_test)

    # 2. Train model if data_dataset exists
    train_yolo(epochs=args.epochs, base_weights=args.weights)

    # 3. Print Label Studio instructions if not run as automated smoke test
    if not args.smoke_test:
        print_label_studio_instructions()


if __name__ == "__main__":
    main()
