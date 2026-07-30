"""
gemini_voice.py  (now powered by Groq LLM)
==========================================
Step 8 of the Sentin-AI build order.  Phase 3 — Communication.

Responsibilities:
  - Accept PHRIResult + DiseaseRoute + SEIRResult
  - Build a structured prompt for Groq LLM API
  - Call llama-3.3-70b-versatile via Groq and parse the JSON response
  - Return a BulletinResult dataclass with:
      • health_bulletin   — 2-3 paragraph public health advisory
      • headline          — one-line newspaper headline
      • action_items      — bulleted list of public actions
      • officer_note      — technical note for health officers

Imported by: dashboard/app.py, realtime_pipeline.py

Usage (as module):
  from gemini_voice import GeminiVoice
  voice    = GeminiVoice()
  bulletin = voice.generate(phri_result, disease_route, seir_result)
  print(bulletin.headline)

Usage (CLI):
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

# ── Groq config ────────────────────────────────────────────────────────────
GROQ_MODEL   = "llama-3.3-70b-versatile"
MAX_TOKENS   = 1024
TEMPERATURE  = 0.4    # low — factual, consistent health bulletins


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
    fallback_used  : bool = False   # True if Groq failed, used template

    def __str__(self):
        actions = "\n".join(f"  - {a}" for a in self.action_items)
        src = "Groq LLM" if not self.fallback_used else "Template"
        return (
            f"News: {self.headline}\n\n"
            f"{self.health_bulletin}\n\n"
            f"Actions:\n{actions}\n\n"
            f"[Officer] {self.officer_note}\n"
            f"[Source] {src}"
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
    Build a structured prompt from pipeline outputs.
    Instructs the LLM to respond in JSON so we can parse reliably.
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
      "officer_note": "1-2 sentences of technical context for the district health officer. Include PHRI threshold, model confidence, and recommended alert level."
    }}
    """).strip()

    return prompt


# ── Groq caller ────────────────────────────────────────────────────────────
def _call_groq(prompt: str, api_key: str) -> str:
    """Call Groq API and return raw text response."""
    from groq import Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a public health AI assistant. "
                    "You always respond with valid JSON only — no markdown, no preamble."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content


# ── Response parser ────────────────────────────────────────────────────────
def _parse_response(raw: str) -> dict:
    """
    Parse LLM JSON response. Strip markdown fences if present.
    Falls back to empty dict on failure.
    """
    text = raw.strip()

    # Strip ```json ... ``` fences
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


# ── Fallback template (no API key or Groq failure) ─────────────────────────
def _fallback_bulletin(phri_score   : float,
                       risk_level   : str,
                       disease_label: str,
                       disease_meta : dict,
                       seir_summary : dict,
                       location     : str) -> dict:
    """
    Template-based bulletin when Groq is unavailable.
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
            f"{risk_level} {disease_label} Alert in {location} — "
            f"Health Advisory Issued by Sentin-AI"
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
            "Eliminate all stagnant water sources within and around your home",
            f"Seek medical attention immediately if you develop {warn.lower()[:60]}",
            "Boil drinking water and maintain strict hand hygiene during this period",
            "Avoid areas with visible garbage accumulation or waterlogging",
            "Report unusual illness clusters to your local BBMP/Municipal health ward",
        ],
        "officer_note": (
            f"PHRI={phri_score:.3f} (alert threshold: 0.70). "
            f"SEIR projects {total} cases over 14 days "
            f"(attack rate {seir_summary.get('attack_rate_pct', 0):.3f}%). "
            f"LLM bulletin unavailable — template fallback active. "
            f"Add GROQ_API_KEY=gsk_... to your .env file to enable AI bulletins."
        ),
    }


# ── Main GeminiVoice class (Groq-powered, same interface) ──────────────────
class GeminiVoice:
    """
    Drop-in replacement for the old Gemini-based voice module.
    Uses Groq LLM (llama-3.3-70b-versatile) under the hood.
    Same generate() interface — no changes needed in dashboard/app.py.
    """

    def __init__(self, api_key: Optional[str] = None):
        # Try GROQ_API_KEY first
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def generate(self,
                 phri_result   ,   # PHRIResult
                 disease_route ,   # DiseaseRoute
                 seir_result   ,   # SEIRResult
                 location      : str = "Bengaluru, Karnataka") -> BulletinResult:
        """
        Full pipeline: build prompt → call Groq → parse → return BulletinResult.
        Falls back to template if Groq fails or key is missing.
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

        if not self.api_key:
            print("[LLMVoice] ! No GROQ_API_KEY found — using template bulletin")
            print("[LLMVoice]   Add GROQ_API_KEY=gsk_... to your .env file")
            fallback = True
        else:
            try:
                print(f"[LLMVoice] Calling Groq API ({GROQ_MODEL})...")
                raw    = _call_groq(prompt, self.api_key)
                parsed = _parse_response(raw)
                if not parsed.get("headline"):
                    raise ValueError("Empty or malformed Groq response")
                print("[LLMVoice] OK: Groq response parsed successfully")
            except Exception as e:
                print(f"[LLMVoice] ! Groq call failed ({e}) -- using template")
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
    parser = argparse.ArgumentParser(description="Sentin-AI LLM Voice Demo (Groq)")
    parser.add_argument("--phri",    type=float, default=0.73, help="PHRI score 0.0-1.0")
    parser.add_argument("--disease", type=str,   default="dengue_malaria", help="Disease bucket")
    parser.add_argument("--loc",     type=str,   default="Bengaluru, Karnataka", help="Location")
    args = parser.parse_args()

    class MockResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        def summary_dict(self):
            return self.summary

    phri_res = MockResult(
        phri_score = args.phri,
        risk_level = "CRITICAL" if args.phri > 0.75 else "HIGH" if args.phri > 0.6 else "MEDIUM"
    )
    disease_res = MockResult(
        primary_bucket = args.disease,
        meta = {
            "label"          : args.disease.replace("_", " ").title(),
            "vector"         : "Aedes mosquitoes (dengue) / Anopheles (malaria)",
            "warning_signs"  : "High fever, severe headache, joint/muscle pain, rash",
            "prevention"     : "Eliminate stagnant water, use mosquito nets and repellents.",
            "incubation_days": "4–10 days"
        }
    )
    seir_res = MockResult(
        summary = {
            "peak_cases"      : 24,
            "peak_day"        : 9,
            "total_projected" : 142,
            "attack_rate_pct" : 0.052,
            "beta_effective"  : 0.61,
            "new_cases_curve" : [2, 4, 7, 11, 17, 22, 24, 23, 20, 16, 11, 7, 4, 2]
        }
    )

    voice    = GeminiVoice()
    bulletin = voice.generate(phri_res, disease_res, seir_res, location=args.loc)

    print("\n" + "="*65)
    print("  SENTIN-AI HEALTH BULLETIN  (Groq LLM)")
    print("="*65)
    print(bulletin)
    print("="*65 + "\n")


if __name__ == "__main__":
    main()

