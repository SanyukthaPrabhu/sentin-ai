"""
gemini_voice.py
===============
Step 8 of the Sentin-AI build order.  Phase 3 — Communication.

Responsibilities:
  - Accept PHRIResult + DiseaseRoute + SEIRResult
  - Build a structured prompt for Gemini API
  - Call gemini-pro and parse the response
  - Return a BulletinResult dataclass with:
      • health_bulletin   — 2-3 paragraph public health advisory
      • headline          — one-line newspaper headline
      • action_items      — bulleted list of public actions
      • officer_note      — technical note for health officers

Imported by: dashboard/app.py

Usage (as module):
  from gemini_voice import GeminiVoice
  voice   = GeminiVoice()
  bulletin = voice.generate(phri_result, disease_route, seir_result)
  print(bulletin.headline)
  print(bulletin.health_bulletin)

Usage (CLI — demo with mock data):
  python src/gemini_voice.py
  python src/gemini_voice.py --phri 0.82 --disease dengue_malaria
"""

import argparse
import os
import json
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── Gemini config ──────────────────────────────────────────────────────────
GEMINI_MODEL   = "gemini-2.0-flash"
MAX_TOKENS     = 1024
TEMPERATURE    = 0.4    # low — we want factual, consistent health bulletins


# ── Result dataclass ───────────────────────────────────────────────────────
@dataclass
class BulletinResult:
    headline       : str
    health_bulletin: str
    action_items   : list
    officer_note   : str
    phri_score     : float
    risk_level     : str
    disease_label  : str
    generated_date : date = field(default_factory=date.today)
    raw_response   : str  = field(default="", repr=False)
    fallback_used  : bool = False   # True if Gemini failed, used template

    def __str__(self):
        actions = "\n".join(f"  - {a}" for a in self.action_items)
        return (
            f"News: {self.headline}\n\n"
            f"{self.health_bulletin}\n\n"
            f"Actions:\n{actions}\n\n"
            f"[Officer] {self.officer_note}"
        )

    def to_dict(self) -> dict:
        return {
            "headline"       : self.headline,
            "health_bulletin": self.health_bulletin,
            "action_items"   : self.action_items,
            "officer_note"   : self.officer_note,
            "phri_score"     : self.phri_score,
            "risk_level"     : self.risk_level,
            "disease_label"  : self.disease_label,
            "generated_date" : str(self.generated_date),
            "fallback_used"  : self.fallback_used,
        }


# ── Prompt builder ─────────────────────────────────────────────────────────
def _build_prompt(phri_score    : float,
                  risk_level    : str,
                  disease_label : str,
                  disease_meta  : dict,
                  seir_summary  : dict,
                  location      : str = "Bengaluru, Karnataka") -> str:
    """
    Build a structured Gemini prompt from pipeline outputs.
    Instructs Gemini to respond in JSON so we can parse reliably.
    """

    seir_curve = seir_summary.get("new_cases_curve", [])
    curve_str  = ", ".join(str(int(v)) for v in seir_curve[:14])

    prompt = textwrap.dedent(f"""
    You are a public health communication specialist for {location}.
    The Sentin-AI early warning system has produced the following analysis.
    Generate a public health communication in the JSON format specified below.

    === SENTIN-AI ANALYSIS ===
    Location        : {location} (5km hyper-local scan)
    Date            : {date.today().strftime("%d %B %Y")}
    PHRI Score      : {phri_score:.2f} / 1.00
    Risk Level      : {risk_level}
    Primary Risk    : {disease_label}
    Vector          : {disease_meta.get("vector", "Unknown")}
    Warning Signs   : {disease_meta.get("warning_signs", "Unknown")}
    Prevention      : {disease_meta.get("prevention", "Unknown")}
    Incubation      : {disease_meta.get("incubation_days", "Unknown")}

    === 14-DAY SEIR PROJECTION ===
    Projected peak  : {seir_summary.get("peak_cases", 0)} cases on day {seir_summary.get("peak_day", 0)}
    Total projected : {seir_summary.get("total_projected", 0)} cases over 14 days
    Attack rate     : {seir_summary.get("attack_rate_pct", 0):.3f}% of surveillance population
    Daily new cases : [{curve_str}]
    Effective R\u2080    : {seir_summary.get("beta_effective", 0) / (1/5):.2f} (estimated)

    === OUTPUT FORMAT ===
    Respond ONLY with a valid JSON object — no preamble, no markdown, no backticks.
    Use this exact structure:

    {{
      "headline": "One punchy newspaper headline (max 15 words). Must mention the disease and location.",
      "health_bulletin": "2-3 paragraph public advisory. Paragraph 1: what the risk is. Paragraph 2: what the public should do. Paragraph 3: reassurance + next steps. Plain language, no jargon. Do not use bullet points here.",
      "action_items": [
        "Action item 1 (specific, actionable, under 15 words)",
        "Action item 2",
        "Action item 3",
        "Action item 4",
        "Action item 5"
      ],
      "officer_note": "1-2 sentences of technical context for the district health officer. May include R0, PHRI threshold, model confidence."
    }}
    """).strip()

    return prompt


# ── Gemini caller (à google.genai SDK) ──────────────────────────────────────
def _call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini API via the new google.genai SDK and return raw text."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=TEMPERATURE,
            max_output_tokens=MAX_TOKENS,
        ),
    )
    return response.text


# ── Response parser ────────────────────────────────────────────────────────
def _parse_response(raw: str) -> dict:
    """
    Parse Gemini JSON response. Strip markdown fences if present.
    Falls back to empty dict on failure.
    """
    text = raw.strip()

    # Strip ```json ... ``` fences if Gemini added them despite instructions
    if text.startswith("```"):
        lines = text.split("\n")
        text  = "\n".join(
            l for l in lines
            if not l.strip().startswith("```")
        ).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object from within the text
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
    return {}


# ── Fallback template (no API key or Gemini failure) ──────────────────────
def _fallback_bulletin(phri_score   : float,
                       risk_level   : str,
                       disease_label: str,
                       disease_meta : dict,
                       seir_summary : dict,
                       location     : str) -> dict:
    """
    Template-based bulletin when Gemini is unavailable.
    Ensures the dashboard always has something to display.
    """
    peak   = seir_summary.get("peak_cases", 0)
    peak_d = seir_summary.get("peak_day", 0)
    total  = seir_summary.get("total_projected", 0)
    prev   = disease_meta.get("prevention", "Maintain hygiene practices.")
    warn   = disease_meta.get("warning_signs", "Fever and fatigue.")
    vector = disease_meta.get("vector", "environmental conditions")

    return {
        "headline": (
            f"{risk_level} {disease_label} Risk Detected in {location} — "
            f"Health Advisory Issued"
        ),
        "health_bulletin": (
            f"The Sentin-AI public health monitoring system has detected a "
            f"{risk_level.lower()} risk of {disease_label} in {location} "
            f"with a Public Health Risk Index (PHRI) score of {phri_score:.2f}. "
            f"Environmental sensors indicate elevated {vector} activity in the 5km surveillance area.\n\n"
            f"Residents are advised to take immediate precautions. {prev} "
            f"Watch for early symptoms including {warn.lower()}. "
            f"If symptoms appear, seek medical attention promptly and avoid self-medication.\n\n"
            f"The SEIR epidemiological model projects approximately {total} cases "
            f"over the next 14 days, peaking around day {peak_d} with up to {peak} "
            f"new cases per day. District health teams have been notified and are monitoring "
            f"the situation. Updated advisories will be issued daily."
        ),
        "action_items": [
            f"Eliminate stagnant water sources within and around your home",
            f"Seek medical attention immediately if you develop {warn.lower()[:50]}",
            f"Boil drinking water and maintain hand hygiene during this period",
            f"Avoid areas with visible garbage accumulation or waterlogging",
            f"Report unusual clusters of illness to your local BBMP health ward",
        ],
        "officer_note": (
            f"PHRI={phri_score:.3f} (threshold 0.70). SEIR beta_eff={seir_summary.get('beta_effective',0):.3f}. "
            f"Projected {total} cases over 14 days (attack rate "
            f"{seir_summary.get('attack_rate_pct',0):.3f}%). "
            f"Gemini bulletin unavailable — template used."
        ),
    }


# ── Main GeminiVoice class ─────────────────────────────────────────────────
class GeminiVoice:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def generate(self,
                 phri_result   ,   # PHRIResult
                 disease_route ,   # DiseaseRoute
                 seir_result   ,   # SEIRResult
                 location      : str = "Bengaluru, Karnataka") -> BulletinResult:
        """
        Full pipeline: build prompt → call Gemini → parse → return BulletinResult.
        Falls back to template if Gemini fails or key is missing.
        """
        phri_score    = phri_result.phri_score
        risk_level    = phri_result.risk_level
        disease_label = disease_route.meta.get("label", disease_route.primary_bucket)
        disease_meta  = disease_route.meta
        seir_summary  = seir_result.summary_dict()

        prompt   = _build_prompt(phri_score, risk_level, disease_label,
                                 disease_meta, seir_summary, location)
        raw      = ""
        parsed   = {}
        fallback = False

        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("[GeminiVoice] ! No API key — using template bulletin")
            fallback = True
        else:
            try:
                print("[GeminiVoice] Calling Gemini API ...")
                raw    = _call_gemini(prompt, self.api_key)
                parsed = _parse_response(raw)
                if not parsed.get("headline"):
                    raise ValueError("Empty or malformed Gemini response")
                print("[GeminiVoice] OK: Gemini response parsed successfully")
            except Exception as e:
                print(f"[GeminiVoice] ! Gemini call failed ({e}) -- using template")
                fallback = True

        if fallback or not parsed:
            parsed   = _fallback_bulletin(phri_score, risk_level, disease_label,
                                          disease_meta, seir_summary, location)
            fallback = True

        return BulletinResult(
            headline        = parsed.get("headline", "Health Advisory"),
            health_bulletin = parsed.get("health_bulletin", ""),
            action_items    = parsed.get("action_items", []),
            officer_note    = parsed.get("officer_note", ""),
            phri_score      = phri_score,
            risk_level      = risk_level,
            disease_label   = disease_label,
            raw_response    = raw,
            fallback_used   = fallback,
        )


# ── CLI / Demo ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Sentin-AI Gemini Voice Demo")
    parser.add_argument("--phri",    type=float, default=0.73, help="PHRI score 0.0-1.0")
    parser.add_argument("--disease", type=str,   default="dengue_malaria", help="Disease bucket")
    parser.add_argument("--loc",     type=str,   default="Bengaluru, Karnataka", help="Location")
    args = parser.parse_args()

    # 1. Provide mock pipeline results
    # We use simple objects that have the attributes generate() expects
    class MockResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        def summary_dict(self):
            return self.summary

    phri_res = MockResult(
        phri_score = args.phri,
        risk_level = "HIGH" if args.phri > 0.6 else "MEDIUM"
    )

    disease_res = MockResult(
        primary_bucket = args.disease,
        meta = {
            "label"          : args.disease.replace("_", " ").title(),
            "vector"         : "Aedes mosquitoes",
            "warning_signs"  : "Fever, joint pain",
            "prevention"     : "Eliminate stagnant water",
            "incubation_days": "7 days"
        }
    )

    seir_res = MockResult(
        summary = {
            "peak_cases"      : 120,
            "peak_day"        : 8,
            "total_projected" : 850,
            "attack_rate_pct" : 0.31,
            "beta_effective"  : 0.65,
            "new_cases_curve" : [10, 15, 25, 45, 80, 110, 120, 115, 100, 80, 60, 40, 30, 20]
        }
    )

    # 2. Generate bulletin
    voice = GeminiVoice()
    bulletin = voice.generate(phri_res, disease_res, seir_res, location=args.loc)

    # 3. Print result
    print("\n" + "="*60)
    print(" SENTIN-AI HEALTH BULLETIN GENERATION")
    print("="*60)
    print(bulletin)
    print("="*60 + "\n")


if __name__ == "__main__":
    main()