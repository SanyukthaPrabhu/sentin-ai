"""
gee_pipeline.py
===============
Step 9 of the Sentin-AI build order.  Phase 4 — Satellite.

Responsibilities:
  - Initialise Google Earth Engine with project 'sentin-ai-public-health-model'
  - Define the Bengaluru 5 km Region of Interest (ROI)
  - Filter COPERNICUS/S2_SR_HARMONIZED by date + bounds + cloud cover
  - Apply QA60 cloud masking (bits 10 and 11) per README spec
  - Compute per-image NDWI  = (Green − NIR)  / (Green + NIR)
  - Compute per-image NDVI  = (NIR  − Red)   / (NIR  + Red)
  - Download thumbnail GeoTIFFs locally → data/raw_imagery/
  - Save a metadata CSV (date, cloud_pct, ndwi_mean, ndvi_mean)

Two download strategies are supported:
  1. getThumbURL  — fast, small PNG/GeoTIFF directly from GEE (used here)
     Limit: ~1 MB per image; fine for 5 km AOI at 20 m resolution.
  2. Export.image.toDrive — for full-resolution exports (optional, commented out)

Usage (CLI):
  python src/gee_pipeline.py
  python src/gee_pipeline.py --start 2023-06-01 --end 2024-10-31
  python src/gee_pipeline.py --start 2023-06-01 --end 2023-06-30 --max_cloud 20

Usage (as module):
  from gee_pipeline import GEEPipeline
  pipeline = GEEPipeline()
  records  = pipeline.run(start_date="2023-06-01", end_date="2024-10-31")
"""

import argparse
import os
import time
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Dependencies ───────────────────────────────────────────────────────────────
try:
    import ee
except ImportError:
    raise ImportError("earthengine-api not installed. Run: pip install earthengine-api")

try:
    from PIL import Image
    import io
except ImportError:
    raise ImportError("Pillow not installed. Run: pip install Pillow")

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
IMAGERY_DIR = ROOT / "data" / "raw_imagery"
IMAGERY_DIR.mkdir(parents=True, exist_ok=True)

METADATA_CSV = IMAGERY_DIR / "sentinel2_metadata.csv"

# ── Config ─────────────────────────────────────────────────────────────────────
GEE_PROJECT       = os.getenv("GEE_PROJECT_ID", "sentin-ai-public-health-model")
TARGET_LAT        = float(os.getenv("TARGET_LAT", 12.98))
TARGET_LON        = float(os.getenv("TARGET_LON", 77.58))
SURVEILLANCE_KM   = float(os.getenv("SURVEILLANCE_RADIUS_KM", 5))

# Sentinel-2 band names (SR Harmonized collection)
BAND_GREEN = "B3"
BAND_RED   = "B4"
BAND_NIR   = "B8"
BAND_QA60  = "QA60"

# Visualisation params for RGB thumbnail download
VIZ_RGB = {
    "bands": ["B4", "B3", "B2"],   # Red, Green, Blue
    "min": 0,
    "max": 3000,
    "gamma": 1.4,
}

VIZ_NDWI = {
    "bands": ["NDWI"],
    "min": -0.5,
    "max": 0.5,
    "palette": ["brown", "white", "blue"],
}

# ── GEEPipeline class ──────────────────────────────────────────────────────────

class GEEPipeline:
    """
    Sentinel-2 download pipeline for Sentin-AI.

    Workflow
    --------
    1. Initialise EE
    2. Build 5 km ROI around Bengaluru
    3. Fetch filtered + cloud-masked image collection
    4. For each image: compute NDWI, NDVI, download thumbnail
    5. Return metadata DataFrame
    """

    def __init__(self, project: str = GEE_PROJECT, lat: float = TARGET_LAT, lon: float = TARGET_LON, radius_km: float = SURVEILLANCE_KM):
        self.project   = project
        self.lat       = lat
        self.lon       = lon
        self.radius_km = radius_km
        self._init_ee()
        self.roi = self._build_roi()

    # ── Init ───────────────────────────────────────────────────────────────────

    def _init_ee(self):
        """Initialise Earth Engine. Uses cached credentials from `earthengine authenticate`."""
        try:
            ee.Initialize(project=self.project)
            print(f"[GEE] Initialised with project: {self.project}")
        except ee.EEException as exc:
            raise RuntimeError(
                f"Earth Engine initialisation failed: {exc}\n"
                "Run `earthengine authenticate` first."
            )

    def _build_roi(self) -> ee.Geometry.Point:
        """Build a circular ROI (buffer in metres) around the target coordinates."""
        point  = ee.Geometry.Point([self.lon, self.lat])
        buffer = point.buffer(self.radius_km * 1000)   # metres
        print(f"[GEE] ROI: {self.lat}°N, {self.lon}°E  radius={self.radius_km} km")
        return buffer

    # ── Cloud masking ──────────────────────────────────────────────────────────

    @staticmethod
    def _mask_clouds(image: ee.Image) -> ee.Image:
        """
        Apply QA60 bitmask cloud masking per README spec.
        Bit 10 = opaque clouds, Bit 11 = cirrus clouds.
        """
        qa         = image.select(BAND_QA60)
        cloud_mask = (
            qa.bitwiseAnd(1 << 10).eq(0)
            .And(qa.bitwiseAnd(1 << 11).eq(0))
        )
        return image.updateMask(cloud_mask)

    # ── Index computation ──────────────────────────────────────────────────────

    @staticmethod
    def _add_ndwi(image: ee.Image) -> ee.Image:
        """NDWI = (Green − NIR) / (Green + NIR).  Positive → water."""
        ndwi = image.normalizedDifference([BAND_GREEN, BAND_NIR]).rename("NDWI")
        return image.addBands(ndwi)

    @staticmethod
    def _add_ndvi(image: ee.Image) -> ee.Image:
        """NDVI = (NIR − Red) / (NIR + Red).  Positive → vegetation."""
        ndvi = image.normalizedDifference([BAND_NIR, BAND_RED]).rename("NDVI")
        return image.addBands(ndvi)

    # ── Collection fetch ───────────────────────────────────────────────────────

    def fetch_collection(
        self,
        start_date:  str,
        end_date:    str,
        max_cloud:   float = 30.0,
    ) -> ee.ImageCollection:
        """
        Fetch Sentinel-2 SR Harmonized collection filtered by date, bounds
        and maximum cloud-cover percentage.

        Parameters
        ----------
        start_date : str  — "YYYY-MM-DD"
        end_date   : str  — "YYYY-MM-DD"
        max_cloud  : float — max CLOUDY_PIXEL_PERCENTAGE (0–100)

        Returns
        -------
        ee.ImageCollection  (cloud-masked, NDWI + NDVI bands added)
        """
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
            .map(self._mask_clouds)
            .map(self._add_ndwi)
            .map(self._add_ndvi)
        )
        count = collection.size().getInfo()
        print(f"[GEE] Found {count} images ({start_date} to {end_date}, cloud<{max_cloud}%)")
        return collection

    # ── Metadata extraction ────────────────────────────────────────────────────

    def _get_image_metadata(self, image: ee.Image) -> dict:
        """Extract date, cloud %, mean NDWI, mean NDVI for one image."""
        date_ms  = image.date().millis().getInfo()
        date_str = datetime.utcfromtimestamp(date_ms / 1000).strftime("%Y-%m-%d")

        cloud_pct = image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()

        # Compute mean NDWI over ROI
        ndwi_stats = (
            image.select("NDWI")
            .reduceRegion(
                reducer  = ee.Reducer.mean(),
                geometry = self.roi,
                scale    = 20,
                maxPixels= 1e8,
            )
            .getInfo()
        )
        ndwi_mean = ndwi_stats.get("NDWI", None)

        # Compute mean NDVI over ROI
        ndvi_stats = (
            image.select("NDVI")
            .reduceRegion(
                reducer  = ee.Reducer.mean(),
                geometry = self.roi,
                scale    = 20,
                maxPixels= 1e8,
            )
            .getInfo()
        )
        ndvi_mean = ndvi_stats.get("NDVI", None)

        return {
            "date":       date_str,
            "cloud_pct":  round(cloud_pct, 2) if cloud_pct is not None else None,
            "ndwi_mean":  round(ndwi_mean, 4) if ndwi_mean is not None else None,
            "ndvi_mean":  round(ndvi_mean, 4) if ndvi_mean is not None else None,
        }

    # ── Thumbnail download ─────────────────────────────────────────────────────

    def _download_thumbnail(
        self,
        image:    ee.Image,
        date_str: str,
        kind:     str = "rgb",
    ) -> Path | None:
        """
        Download a PNG thumbnail from GEE using getThumbURL.

        Parameters
        ----------
        image    : ee.Image
        date_str : str  — used for filename
        kind     : "rgb" | "ndwi"

        Returns
        -------
        Path to saved PNG, or None on failure.
        """
        filename = IMAGERY_DIR / f"S2_{date_str}_{kind}.png"
        if filename.exists():
            print(f"  [skip] {filename.name} already exists")
            return filename

        viz = VIZ_RGB if kind == "rgb" else VIZ_NDWI

        try:
            url = image.getThumbURL({
                **viz,
                "region":     self.roi,
                "dimensions": 512,
                "format":     "png",
            })
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            img = Image.open(io.BytesIO(response.content))
            img.save(filename)
            print(f"  [saved] {filename.name} ({img.size[0]}×{img.size[1]})")
            return filename

        except Exception as exc:
            print(f"  [warn] Failed to download {kind} thumbnail for {date_str}: {exc}")
            return None

    # ── NDWI array extraction ──────────────────────────────────────────────────

    def _extract_ndwi_array(self, image: ee.Image, date_str: str) -> Path | None:
        """
        Extract NDWI pixel values as a NumPy .npy file for YOLO preprocessing.

        Returns
        -------
        Path to saved .npy file, or None on failure.
        """
        npy_path = IMAGERY_DIR / f"S2_{date_str}_ndwi.npy"
        if npy_path.exists():
            print(f"  [skip] {npy_path.name} already exists")
            return npy_path

        try:
            # Sample pixel values via reduceRegion at 20m scale
            stats = (
                image.select("NDWI")
                .reduceRegion(
                    reducer  = ee.Reducer.toList(),
                    geometry = self.roi,
                    scale    = 20,
                    maxPixels= 1e6,
                )
                .getInfo()
            )
            values = stats.get("NDWI", [])
            if values:
                arr = np.array(values, dtype=np.float32)
                np.save(npy_path, arr)
                print(f"  [saved] {npy_path.name} shape=({len(arr)},)")
                return npy_path
            else:
                print(f"  [warn] Empty NDWI array for {date_str}")
                return None

        except Exception as exc:
            print(f"  [warn] NDWI extraction failed for {date_str}: {exc}")
            return None

    # ── Main run loop ──────────────────────────────────────────────────────────

    def run(
        self,
        start_date: str = "2023-06-01",
        end_date:   str = "2024-10-31",
        max_cloud:  float = 30.0,
        max_images: int = 50,
    ) -> pd.DataFrame:
        """
        Full pipeline: fetch → download → metadata.

        Parameters
        ----------
        start_date : str   — default covers monsoon seasons 2023 + 2024
        end_date   : str
        max_cloud  : float — max cloud cover filter
        max_images : int   — cap to avoid EECU exhaustion

        Returns
        -------
        pd.DataFrame  with columns: date, cloud_pct, ndwi_mean, ndvi_mean,
                                    rgb_path, ndwi_png_path, ndwi_npy_path
        """
        print("\n" + "="*60)
        print("  Sentin-AI | GEE Sentinel-2 Pipeline")
        print("="*60)

        collection = self.fetch_collection(start_date, end_date, max_cloud)
        image_list = collection.toList(max_images)
        n_images   = min(collection.size().getInfo(), max_images)

        if n_images == 0:
            print("[GEE] No images found. Try relaxing cloud filter or extending date range.")
            return pd.DataFrame()

        records = []

        for i in range(n_images):
            print(f"\n[{i+1}/{n_images}] Processing image...")
            image = ee.Image(image_list.get(i))

            # ── Metadata ──────────────────────────────────────────────────
            meta = self._get_image_metadata(image)
            date_str = meta["date"]
            print(f"  Date: {date_str}  Cloud: {meta['cloud_pct']}%  "
                  f"NDWI: {meta['ndwi_mean']}  NDVI: {meta['ndvi_mean']}")

            # ── Download RGB thumbnail ────────────────────────────────────
            rgb_path  = self._download_thumbnail(image, date_str, kind="rgb")

            # ── Download NDWI thumbnail ───────────────────────────────────
            ndwi_path = self._download_thumbnail(image, date_str, kind="ndwi")

            # ── Extract NDWI NumPy array ──────────────────────────────────
            npy_path  = self._extract_ndwi_array(image, date_str)

            records.append({
                **meta,
                "rgb_path":      str(rgb_path)  if rgb_path  else None,
                "ndwi_png_path": str(ndwi_path) if ndwi_path else None,
                "ndwi_npy_path": str(npy_path)  if npy_path  else None,
            })

            # Brief pause to avoid hammering GEE API
            time.sleep(0.5)

        df = pd.DataFrame(records)
        df.to_csv(METADATA_CSV, index=False)
        print(f"\n[GEE] Metadata saved -> {METADATA_CSV}")
        print(f"[GEE] Downloaded {len(df)} images to {IMAGERY_DIR}")
        print("="*60 + "\n")
        return df

    def fetch_latest_image(self, lookback_days: int = 90, max_cloud: float = 60.0) -> dict:
        """
        Fetch the single most recent Sentinel-2 image over Bengaluru.
        Used by real-time mode to get live satellite imagery.
        """
        end_dt = datetime.utcnow()
        start_dt = end_dt - pd.Timedelta(days=lookback_days)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        print(f"\n[GEE Realtime] Searching for latest Sentinel-2 scene ({start_str} to {end_str})...")
        collection = self.fetch_collection(start_str, end_str, max_cloud=max_cloud)
        # Sort by system:time_start descending
        collection_sorted = collection.sort("system:time_start", False)
        count = collection_sorted.size().getInfo()

        if count == 0:
            print("[GEE Realtime] No recent scene found. Relaxing cloud threshold...")
            collection_sorted = self.fetch_collection(start_str, end_str, max_cloud=100.0).sort("system:time_start", False)
            count = collection_sorted.size().getInfo()
            if count == 0:
                raise RuntimeError("No Sentinel-2 image found in the given window.")

        latest_img = ee.Image(collection_sorted.first())
        meta = self._get_image_metadata(latest_img)
        date_str = meta["date"]
        print(f"[GEE Realtime] Selected latest scene: {date_str} (Cloud: {meta['cloud_pct']}%)")

        rgb_path = self._download_thumbnail(latest_img, date_str, kind="rgb")
        ndwi_path = self._download_thumbnail(latest_img, date_str, kind="ndwi")
        npy_path = self._extract_ndwi_array(latest_img, date_str)

        latest_meta = {
            **meta,
            "rgb_path": str(rgb_path) if rgb_path else None,
            "ndwi_png_path": str(ndwi_path) if ndwi_path else None,
            "ndwi_npy_path": str(npy_path) if npy_path else None,
        }

        # Update or append to metadata CSV
        if METADATA_CSV.exists():
            df = pd.read_csv(METADATA_CSV)
            if date_str not in df["date"].values:
                df = pd.concat([df, pd.DataFrame([latest_meta])], ignore_index=True)
                df.to_csv(METADATA_CSV, index=False)
        else:
            df = pd.DataFrame([latest_meta])
            df.to_csv(METADATA_CSV, index=False)

        return latest_meta

    def compute_ndwi_delta(self, current_date: str, lookback_days: int = 90,
                           max_cloud: float = 60.0) -> dict:
        """
        NDWI Temporal Differencing (Gap 3 fix).

        Compares the NDWI of the current satellite scene against a baseline
        scene from the same calendar window one year prior.

        Purpose:
          - Permanent water bodies (lakes, rivers) have consistently high NDWI
            in BOTH current and baseline → delta ≈ 0  → not a flood risk
          - Temporary stagnant water (monsoon puddles, blocked drains) has
            high current NDWI but LOW baseline NDWI → delta > 0 → ALERT

        Returns:
            dict with:
              ndwi_current  : float  — mean NDWI of current scene
              ndwi_baseline : float  — mean NDWI of prior-year baseline
              ndwi_delta    : float  — current − baseline (positive = new water)
              new_water_flag: bool   — True if delta > 0.05 (significant new water)
              current_date  : str
              baseline_date : str
        """
        from datetime import datetime, timedelta

        cur_dt = datetime.strptime(current_date, "%Y-%m-%d")

        # ── Current scene NDWI ────────────────────────────────────────────
        cur_start = (cur_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        cur_end   = cur_dt.strftime("%Y-%m-%d")

        cur_col = self.fetch_collection(cur_start, cur_end, max_cloud=max_cloud)
        cur_col = cur_col.sort("system:time_start", False)
        cur_count = cur_col.size().getInfo()

        if cur_count == 0:
            print("[NDWI Delta] No current scene found")
            return {"ndwi_delta": 0.0, "new_water_flag": False,
                    "ndwi_current": 0.0, "ndwi_baseline": 0.0,
                    "current_date": current_date, "baseline_date": "N/A"}

        cur_img  = ee.Image(cur_col.first())
        cur_meta = self._get_image_metadata(cur_img)
        cur_ndwi = cur_meta["ndwi_mean"]

        # ── Baseline NDWI (same window, prior year) ───────────────────────
        base_dt    = cur_dt - timedelta(days=365)
        base_start = (base_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        base_end   = base_dt.strftime("%Y-%m-%d")

        base_col   = self.fetch_collection(base_start, base_end, max_cloud=max_cloud)
        base_col   = base_col.sort("system:time_start", False)
        base_count = base_col.size().getInfo()

        if base_count == 0:
            print("[NDWI Delta] No prior-year baseline scene — using 0.0")
            base_ndwi    = 0.0
            baseline_date = "N/A"
        else:
            base_img      = ee.Image(base_col.first())
            base_meta     = self._get_image_metadata(base_img)
            base_ndwi     = base_meta["ndwi_mean"]
            baseline_date = base_meta["date"]

        # ── Delta computation ─────────────────────────────────────────────
        ndwi_delta     = round(float(cur_ndwi) - float(base_ndwi), 4)
        new_water_flag = ndwi_delta > 0.05   # > 5% increase = significant new water

        print(f"[NDWI Delta] Current ({cur_meta['date']}): {cur_ndwi:.4f} | "
              f"Baseline ({baseline_date}): {base_ndwi:.4f} | "
              f"Delta: {ndwi_delta:+.4f} | New water: {new_water_flag}")

        return {
            "ndwi_current"  : float(cur_ndwi),
            "ndwi_baseline" : float(base_ndwi),
            "ndwi_delta"    : ndwi_delta,
            "new_water_flag": new_water_flag,
            "current_date"  : cur_meta["date"],
            "baseline_date" : baseline_date,
        }



# ── Sentinel-1 SAR fallback (stub) ────────────────────────────────────────────

class SAR_Pipeline:
    """
    Sentinel-1 SAR fallback for monsoon cloud cover.
    Used when Sentinel-2 optical images are unavailable.
    Implements VV polarisation water body detection.
    """

    def __init__(self, project: str = GEE_PROJECT):
        self.project = project
        ee.Initialize(project=self.project)
        self.roi = (
            ee.Geometry.Point([TARGET_LON, TARGET_LAT])
            .buffer(SURVEILLANCE_KM * 1000)
        )

    def fetch_sar(self, start_date: str, end_date: str) -> ee.ImageCollection:
        """
        Fetch Sentinel-1 GRD (Ground Range Detected) VV polarisation.
        Negative dB values below threshold indicate open water.
        """
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(self.roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV")
        )
        count = collection.size().getInfo()
        print(f"[SAR] Found {count} Sentinel-1 images")
        return collection

    def detect_water_sar(self, image: ee.Image, threshold_db: float = -15.0) -> ee.Image:
        """
        Simple threshold-based water detection on VV band.
        Pixels < threshold_db are flagged as water.
        """
        water_mask = image.lt(threshold_db).rename("SAR_water")
        return image.addBands(water_mask)


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sentin-AI: GEE Sentinel-2 download pipeline"
    )
    parser.add_argument(
        "--start", default="2023-06-01",
        help="Start date YYYY-MM-DD (default: 2023-06-01)"
    )
    parser.add_argument(
        "--end", default="2024-10-31",
        help="End date YYYY-MM-DD (default: 2024-10-31)"
    )
    parser.add_argument(
        "--max_cloud", type=float, default=30.0,
        help="Max cloud cover %% (default: 30)"
    )
    parser.add_argument(
        "--max_images", type=int, default=50,
        help="Max images to download (default: 50)"
    )
    parser.add_argument(
        "--sar", action="store_true",
        help="Also fetch Sentinel-1 SAR collection (fallback)"
    )
    args = parser.parse_args()

    pipeline = GEEPipeline()
    df = pipeline.run(
        start_date = args.start,
        end_date   = args.end,
        max_cloud  = args.max_cloud,
        max_images = args.max_images,
    )

    if not df.empty:
        print(df[["date", "cloud_pct", "ndwi_mean", "ndvi_mean"]].to_string(index=False))

    if args.sar:
        print("\n[SAR] Fetching Sentinel-1 fallback...")
        sar = SAR_Pipeline()
        sar_col = sar.fetch_sar(args.start, args.end)
        print(f"[SAR] {sar_col.size().getInfo()} SAR images available.")


if __name__ == "__main__":
    main()
