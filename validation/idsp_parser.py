"""
idsp_parser.py
==============
Step 2 of the Sentin-AI build order.

Responsibilities:
  - Scan data/idsp_bulletins/raw_pdfs/ for all IDSP weekly PDFs
  - Extract outbreak tables from each PDF using pdfplumber
  - Filter rows for Karnataka / Bengaluru Urban district
  - Normalize disease names into Sentin-AI buckets
  - Output:
      data/idsp_bulletins/parsed/idsp_outbreaks.csv   ← one row per outbreak event
      data/idsp_bulletins/parsed/weekly_labels.csv    ← one row per ISO week (label=0/1)

Usage:
  python validation/idsp_parser.py
  python validation/idsp_parser.py --pdf_dir data/idsp_bulletins/raw_pdfs
"""

import argparse
import re
import sys
import warnings
import numpy as np
import pandas as pd
import pdfplumber
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
PDF_DIR   = ROOT / "data" / "idsp_bulletins" / "raw_pdfs"
OUT_DIR   = ROOT / "data" / "idsp_bulletins" / "parsed"
OUT_EVENTS  = OUT_DIR / "idsp_outbreaks.csv"
OUT_LABELS  = OUT_DIR / "weekly_labels.csv"

# ── Config ─────────────────────────────────────────────────────────────────
# Weeks and years we care about (monsoon window per README)
TARGET_YEARS = [2023, 2024]
TARGET_WEEKS = list(range(22, 44))   # weeks 22–43 inclusive

# Location filter — rows must contain one of these strings (case-insensitive)
LOCATION_KEYWORDS = [
    "karnataka", "bengaluru", "bangalore",
    "bengaluru urban", "bangalore urban",
]

# Disease name → Sentin-AI bucket mapping
DISEASE_BUCKET_MAP = {
    # Dengue / Malaria bucket
    "dengue"        : "dengue_malaria",
    "malaria"       : "dengue_malaria",
    "chikungunya"   : "dengue_malaria",
    # Leptospirosis / Cholera bucket
    "leptospirosis" : "lepto_cholera",
    "cholera"       : "lepto_cholera",
    "typhoid"       : "lepto_cholera",
    "diarrhoea"     : "lepto_cholera",
    "diarrhea"      : "lepto_cholera",
    "gastroenteritis": "lepto_cholera",
    # Respiratory bucket
    "influenza"     : "respiratory",
    "pneumonia"     : "respiratory",
    "covid"         : "respiratory",
    "ari"           : "respiratory",
    "sari"          : "respiratory",
    # Other / unknown
}


# ── 1. PDF file discovery ──────────────────────────────────────────────────
def discover_pdfs(pdf_dir: Path) -> list:
    """
    Return sorted list of PDF paths.
    Expected naming pattern (flexible):
      idsp_wk22_2023.pdf  /  week22_2023.pdf  /  22_2023.pdf  / etc.
    """
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs found in {pdf_dir}.\n"
            "Place your 44 IDSP weekly PDFs there and re-run."
        )
    print(f"[1/5] Found {len(pdfs)} PDF(s) in {pdf_dir}")
    return pdfs


# ── 2. Year / week extractor from filename ─────────────────────────────────
def parse_week_year_from_filename(filename: str):
    """
    Try to extract (year, week) from common IDSP filename patterns.
    Handles:
      - Ordinal: '22nd 2023', '33rd 2024', '41st 2023'
      - Prefix:  'wk22_2023', 'week22_2023'
      - Generic: '_22_2023'
    Returns (year, week) ints or (None, None).
    """
    name = filename.lower()
    year_match = re.search(r"(2023|2024)", name)
    year = int(year_match.group(1)) if year_match else None

    # Ordinal pattern: leading digits followed by st/nd/rd/th  e.g. "22nd", "33rd"
    ordinal_match = re.match(r"^(\d{1,2})(?:st|nd|rd|th)\b", name.strip())
    if ordinal_match:
        week = int(ordinal_match.group(1))
    else:
        week_match = re.search(r"wk\s*(\d{1,2})|week\s*(\d{1,2})|_(\d{2})_", name)
        if week_match:
            week = int(next(g for g in week_match.groups() if g is not None))
        else:
            week = None
    return year, week


# ── 3. Table extractor from a single PDF ──────────────────────────────────
def extract_tables_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Open a PDF with pdfplumber, extract all tables across all pages,
    flatten into a list of row-dicts.
    """
    records = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    # First row = header
                    header = [
                        str(h).strip().lower().replace("\n", " ")
                        if h else f"col_{i}"
                        for i, h in enumerate(table[0])
                    ]
                    for row in table[1:]:
                        if not any(row):
                            continue
                        record = {
                            header[i]: str(cell).strip() if cell else ""
                            for i, cell in enumerate(row)
                            if i < len(header)
                        }
                        record["_source_pdf"]  = pdf_path.name
                        record["_page"]        = page_num
                        records.append(record)
    except Exception as e:
        print(f"    ⚠  Could not parse {pdf_path.name}: {e}")
    return records


# ── 4. Location filter ─────────────────────────────────────────────────────
def is_karnataka_row(row: dict) -> bool:
    """Return True if any cell in the row mentions Karnataka / Bengaluru."""
    combined = " ".join(str(v).lower() for v in row.values())
    return any(kw in combined for kw in LOCATION_KEYWORDS)


# ── 5. Disease bucket classifier ──────────────────────────────────────────
def classify_disease(row: dict) -> str:
    """Map raw disease text to a Sentin-AI bucket."""
    combined = " ".join(str(v).lower() for v in row.values())
    for keyword, bucket in DISEASE_BUCKET_MAP.items():
        if keyword in combined:
            return bucket
    return "other"


# ── 6. Case count extractor ────────────────────────────────────────────────
_NUM_RE = re.compile(r"\d+")

def extract_case_count(row: dict) -> int:
    """
    Try to pull a case count from columns likely named:
    'cases', 'no. of cases', 'human cases', 'affected', etc.
    Falls back to scanning all numeric cells.
    """
    priority_keys = [k for k in row if any(
        kw in k for kw in ["case", "affect", "human", "ill", "attack"]
    )]
    for k in priority_keys:
        nums = _NUM_RE.findall(str(row[k]))
        if nums:
            return int(nums[0])
    # Fallback: largest number found anywhere in row
    all_nums = []
    for v in row.values():
        all_nums.extend(int(n) for n in _NUM_RE.findall(str(v)))
    return max(all_nums) if all_nums else 0


# ── 7. Main parse loop ─────────────────────────────────────────────────────
def parse_all_pdfs(pdf_dir: Path) -> pd.DataFrame:
    pdfs = discover_pdfs(pdf_dir)

    print("[2/5] Extracting tables from PDFs ...")
    all_events = []

    for pdf_path in pdfs:
        year, week = parse_week_year_from_filename(pdf_path.stem)
        raw_rows   = extract_tables_from_pdf(pdf_path)

        karnataka_rows = [r for r in raw_rows if is_karnataka_row(r)]

        for row in karnataka_rows:
            event = {
                "year"          : year,
                "iso_week"      : week,
                "disease_raw"   : " | ".join(
                    str(v) for v in row.values()
                    if v and not str(v).startswith("_")
                )[:120],
                "disease_bucket": classify_disease(row),
                "case_count"    : extract_case_count(row),
                "source_pdf"    : row.get("_source_pdf", ""),
                "page"          : row.get("_page", ""),
            }
            all_events.append(event)

        status = f"{len(karnataka_rows)} Karnataka rows" if karnataka_rows else "no Karnataka rows"
        print(f"    {pdf_path.name:40s}  wk={week} yr={year}  → {status}")

    if not all_events:
        print("\n  ⚠  No Karnataka rows found across all PDFs.")
        print("     This may mean the table structure differs — see TROUBLESHOOTING below.")
        _print_troubleshooting()
        # Return empty frame so pipeline doesn't crash
        return pd.DataFrame(columns=[
            "year", "iso_week", "disease_raw", "disease_bucket", "case_count", "source_pdf", "page"
        ])

    df = pd.DataFrame(all_events)
    print(f"\n[3/5] Extracted {len(df)} Karnataka outbreak events total")
    return df


def _print_troubleshooting():
    print("""
  TROUBLESHOOTING — if zero rows extracted:
  ─────────────────────────────────────────
  1. Run with --debug flag to dump raw table text from first PDF.
  2. IDSP PDFs sometimes use image-scanned pages (no selectable text).
     In that case you need OCR: pip install pytesseract pdf2image
     and set --ocr flag (see bottom of this file for OCR stub).
  3. Check that 'Karnataka' or 'Bengaluru' appears as text (not an image)
     inside the PDF tables.
""")


# ── 8. Build weekly label grid ─────────────────────────────────────────────
def build_weekly_labels(df_events: pd.DataFrame) -> pd.DataFrame:
    """
    Create a row for every (year, week) in TARGET_YEARS × TARGET_WEEKS.
    label = 1 if any outbreak event was recorded that week, else 0.
    """
    print("[4/5] Building weekly label grid ...")

    rows = []
    for year in TARGET_YEARS:
        for week in TARGET_WEEKS:
            # Approximate week start date (ISO week Monday)
            week_start = pd.Timestamp.fromisocalendar(year, week, 1)
            week_end   = week_start + pd.Timedelta(days=6)

            if len(df_events):
                match = df_events[
                    (df_events["year"] == year) &
                    (df_events["iso_week"] == week)
                ]
                label         = 1 if len(match) > 0 else 0
                case_total    = int(match["case_count"].sum()) if len(match) else 0
                disease_list  = ",".join(match["disease_bucket"].unique()) if len(match) else ""
            else:
                label, case_total, disease_list = 0, 0, ""

            rows.append({
                "year"          : year,
                "iso_week"      : week,
                "week_start"    : week_start.date(),
                "week_end"      : week_end.date(),
                "label"         : label,
                "case_total"    : case_total,
                "disease_buckets": disease_list,
            })

    df_labels = pd.DataFrame(rows)
    outbreak_weeks = df_labels["label"].sum()
    print(f"    Total weeks: {len(df_labels)}  |  Outbreak weeks (label=1): {outbreak_weeks}")
    return df_labels


# ── 9. Save ────────────────────────────────────────────────────────────────
def save_outputs(df_events: pd.DataFrame, df_labels: pd.DataFrame):
    print("[5/5] Saving outputs ...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_events.to_csv(OUT_EVENTS, index=False)
    df_labels.to_csv(OUT_LABELS, index=False)
    print(f"    ✅ {OUT_EVENTS}")
    print(f"    ✅ {OUT_LABELS}")


# ── Debug helper ───────────────────────────────────────────────────────────
def debug_first_pdf(pdf_dir: Path):
    """Dump raw text + table structure of the first PDF for inspection."""
    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found.")
        return
    pdf_path = pdfs[0]
    print(f"\n=== DEBUG: {pdf_path.name} ===")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:3], 1):
            print(f"\n--- Page {i} text (first 500 chars) ---")
            text = page.extract_text() or ""
            print(text[:500])
            print(f"\n--- Page {i} tables ---")
            for j, tbl in enumerate(page.extract_tables()):
                print(f"  Table {j}: {len(tbl)} rows × {len(tbl[0]) if tbl else 0} cols")
                if tbl:
                    print(f"  Header: {tbl[0]}")
                    print(f"  Row 1 : {tbl[1] if len(tbl) > 1 else 'N/A'}")


# ── Main ───────────────────────────────────────────────────────────────────
def run(pdf_dir: Path, debug: bool = False):
    if debug:
        debug_first_pdf(pdf_dir)
        return None, None

    df_events = parse_all_pdfs(pdf_dir)
    df_labels = build_weekly_labels(df_events)
    save_outputs(df_events, df_labels)
    print("\n🎉 idsp_parser.py complete — ready for Step 3 (backtest.py skeleton)")
    return df_events, df_labels


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse IDSP Weekly PDFs for Sentin-AI")
    parser.add_argument(
        "--pdf_dir", type=str, default=str(PDF_DIR),
        help="Folder containing IDSP weekly PDFs"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Dump raw text/table structure of first PDF and exit"
    )
    args = parser.parse_args()
    run(Path(args.pdf_dir), debug=args.debug)