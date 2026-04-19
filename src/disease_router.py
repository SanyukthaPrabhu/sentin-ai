"""
disease_router.py
=================
Step 6 of the Sentin-AI build order.

Responsibilities:
  - Accept a PHRIResult + current weather snapshot
  - Apply the rule table from README Section 2 to classify disease risk
  - Return a DiseaseRoute dataclass with bucket, confidence, and reasoning

Rule table (from README):
  Stagnant water + Temp >28°C + Humidity >70%  → Dengue / Malaria
  Garbage        + Rainfall spike               → Leptospirosis / Cholera
  High AOD       + Humidity                     → Respiratory / Airborne

This is a pure rule engine — no ML model needed.
Imported by: phri_engine.py, dashboard/app.py

Usage (as module):
  from disease_router import DiseaseRouter
  router = DiseaseRouter()
  route  = router.classify(phri_result, weather_dict, yolo_dict)
  print(route.primary_bucket)    # e.g. "dengue_malaria"
  print(route.reasoning)         # human-readable explanation
"""

from dataclasses import dataclass, field
from typing import Optional
from phri_engine import PHRIResult

# ── Disease buckets ────────────────────────────────────────────────────────
BUCKET_DENGUE_MALARIA  = "dengue_malaria"
BUCKET_LEPTO_CHOLERA   = "lepto_cholera"
BUCKET_RESPIRATORY     = "respiratory"
BUCKET_GENERAL         = "general_risk"    # PHRI elevated but no specific match
BUCKET_NONE            = "none"            # PHRI below alert threshold

PHRI_ALERT_THRESHOLD   = 0.40             # below this → no alert


# ── Disease metadata ───────────────────────────────────────────────────────
DISEASE_META = {
    BUCKET_DENGUE_MALARIA: {
        "label"          : "Dengue / Malaria",
        "vector"         : "Aedes / Anopheles mosquitoes",
        "incubation_days": "4–14 days",
        "warning_signs"  : "High fever, joint pain, rash, chills",
        "prevention"     : "Eliminate stagnant water, use repellents, sleep under nets",
        "color"          : "#FF6B35",
    },
    BUCKET_LEPTO_CHOLERA: {
        "label"          : "Leptospirosis / Cholera",
        "vector"         : "Contaminated floodwater / water supply",
        "incubation_days": "2–30 days",
        "warning_signs"  : "Fever, muscle pain, jaundice, severe diarrhoea",
        "prevention"     : "Avoid wading in floodwater, boil drinking water, improve sanitation",
        "color"          : "#8B4513",
    },
    BUCKET_RESPIRATORY: {
        "label"          : "Respiratory / Airborne",
        "vector"         : "Airborne droplets / particulate matter",
        "incubation_days": "1–14 days",
        "warning_signs"  : "Cough, breathlessness, fever, sore throat",
        "prevention"     : "Wear masks outdoors, avoid crowded spaces, stay indoors on high AQI days",
        "color"          : "#6A5ACD",
    },
    BUCKET_GENERAL: {
        "label"          : "General Outbreak Risk",
        "vector"         : "Multiple pathways",
        "incubation_days": "Varies",
        "warning_signs"  : "Monitor local health advisories",
        "prevention"     : "Maintain hygiene, stay hydrated, report unusual symptoms",
        "color"          : "#FFA500",
    },
    BUCKET_NONE: {
        "label"          : "No Significant Risk",
        "vector"         : "—",
        "incubation_days": "—",
        "warning_signs"  : "—",
        "prevention"     : "Continue routine hygiene practices",
        "color"          : "#4CAF50",
    },
}


# ── Result dataclass ───────────────────────────────────────────────────────
@dataclass
class DiseaseRoute:
    primary_bucket   : str             # main disease bucket
    secondary_buckets: list            # other triggered buckets (co-risk)
    phri_score       : float
    risk_level       : str
    rules_triggered  : list            # which rules fired
    reasoning        : str             # human-readable summary
    meta             : dict = field(default_factory=dict)   # from DISEASE_META

    def __str__(self):
        sec = f"  Co-risk: {self.secondary_buckets}" if self.secondary_buckets else ""
        return (
            f"Disease: {self.meta.get('label','?')}  "
            f"PHRI={self.phri_score:.3f}  Risk={self.risk_level}"
            f"{sec}\n  Reason: {self.reasoning}"
        )


# ── Rule engine ────────────────────────────────────────────────────────────
class DiseaseRouter:
    """
    Stateless rule engine.  Call .classify() for each inference cycle.
    """

    # ── Individual rule checks ─────────────────────────────────────────────

    @staticmethod
    def _rule_dengue_malaria(weather: dict, yolo: Optional[dict]) -> tuple[bool, str]:
        """
        Trigger: stagnant water detected  AND  temp >28°C  AND  humidity >70%
        If YOLO not available, fall back to humidity + temp alone (lower confidence).
        """
        temp     = weather.get("temperature_2m_c", 0)
        humidity = weather.get("relative_humidity_pct", 0)
        water    = yolo.get("stagnant_water_count", 0) if yolo else 0
        area     = yolo.get("stagnant_water_area_px", 0) if yolo else 0

        temp_hot   = temp     > 28.0
        humid_high = humidity > 70.0

        if yolo is not None:
            water_present = water > 0 or area > 0
            triggered = water_present and temp_hot and humid_high
            reason = (
                f"Stagnant water detected ({water} sites, {area:.0f}px), "
                f"Temp={temp:.1f}°C >28°C, Humidity={humidity:.0f}% >70%"
                if triggered else ""
            )
        else:
            # No YOLO — use weather proxy (monsoon season pattern)
            triggered = temp_hot and humid_high and weather.get("precipitation_imerg_mm", 0) > 5
            reason = (
                f"High-risk weather: Temp={temp:.1f}°C, Humidity={humidity:.0f}%, "
                f"Rain={weather.get('precipitation_imerg_mm',0):.1f}mm (YOLO not available)"
                if triggered else ""
            )

        return triggered, reason

    @staticmethod
    def _rule_lepto_cholera(weather: dict, yolo: Optional[dict]) -> tuple[bool, str]:
        """
        Trigger: garbage detected  AND  rainfall spike (>20mm/day)
        Rainfall alone with no drainage also qualifies.
        """
        precip  = weather.get("precipitation_imerg_mm", 0)
        garbage = yolo.get("garbage_count", 0) if yolo else 0

        rain_spike    = precip > 20.0
        garbage_found = garbage > 0

        if yolo is not None:
            triggered = garbage_found and rain_spike
            reason = (
                f"Garbage accumulation ({garbage} sites) + "
                f"rainfall spike ({precip:.1f}mm > 20mm)"
                if triggered else ""
            )
        else:
            # Proxy: heavy rain + high humidity = flood/contamination risk
            humidity = weather.get("relative_humidity_pct", 0)
            triggered = rain_spike and humidity > 80
            reason = (
                f"Heavy rainfall ({precip:.1f}mm) + high humidity ({humidity:.0f}%) "
                f"— flood/contamination risk (YOLO not available)"
                if triggered else ""
            )

        return triggered, reason

    @staticmethod
    def _rule_respiratory(weather: dict, yolo: Optional[dict]) -> tuple[bool, str]:
        """
        Trigger: vegetation anomaly (proxy for AOD / air quality degradation)
                 AND humidity >60%
        Also triggers on low insolation (haze/smog conditions).
        """
        humidity    = weather.get("relative_humidity_pct", 0)
        insolation  = weather.get("all_sky_insolation_clearness", 1.0)
        veg_anomaly = yolo.get("vegetation_anomaly_score", 0) if yolo else 0

        hazy         = insolation < 0.4
        humid_mid    = humidity   > 60.0
        veg_stressed = veg_anomaly > 0.4

        if yolo is not None:
            triggered = veg_stressed and humid_mid
            reason = (
                f"Vegetation anomaly score={veg_anomaly:.2f} >0.4 "
                f"(AOD proxy) + Humidity={humidity:.0f}% >60%"
                if triggered else ""
            )
        else:
            triggered = hazy and humid_mid
            reason = (
                f"Low insolation clearness={insolation:.2f} <0.4 (haze/smog) "
                f"+ Humidity={humidity:.0f}% >60%"
                if triggered else ""
            )

        return triggered, reason

    # ── Main classify method ───────────────────────────────────────────────
    def classify(self,
                 phri_result : PHRIResult,
                 weather     : dict,
                 yolo        : Optional[dict] = None) -> DiseaseRoute:
        """
        Run all rules against current inputs.
        Returns DiseaseRoute with primary + secondary buckets.

        Priority order (if multiple rules fire):
          1. dengue_malaria  (highest mortality risk in Bengaluru)
          2. lepto_cholera
          3. respiratory
        """
        score = phri_result.phri_score

        # Below threshold — no alert
        if score < PHRI_ALERT_THRESHOLD:
            return DiseaseRoute(
                primary_bucket    = BUCKET_NONE,
                secondary_buckets = [],
                phri_score        = score,
                risk_level        = phri_result.risk_level,
                rules_triggered   = [],
                reasoning         = f"PHRI={score:.3f} below alert threshold {PHRI_ALERT_THRESHOLD}. No action required.",
                meta              = DISEASE_META[BUCKET_NONE],
            )

        # Run all three rules
        dm_hit,  dm_reason  = self._rule_dengue_malaria(weather, yolo)
        lc_hit,  lc_reason  = self._rule_lepto_cholera(weather, yolo)
        res_hit, res_reason = self._rule_respiratory(weather, yolo)

        hits = []
        if dm_hit:  hits.append((BUCKET_DENGUE_MALARIA, dm_reason))
        if lc_hit:  hits.append((BUCKET_LEPTO_CHOLERA,  lc_reason))
        if res_hit: hits.append((BUCKET_RESPIRATORY,     res_reason))

        if not hits:
            # PHRI elevated but no specific rule fires → general risk
            primary   = BUCKET_GENERAL
            secondary = []
            triggered = []
            reasoning = (
                f"PHRI={score:.3f} elevated but no specific environmental "
                f"trigger pattern matched. Monitor closely."
            )
        else:
            primary   = hits[0][0]
            secondary = [h[0] for h in hits[1:]]
            triggered = [h[0] for h in hits]
            reasoning = "  |  ".join(h[1] for h in hits)

        return DiseaseRoute(
            primary_bucket    = primary,
            secondary_buckets = secondary,
            phri_score        = score,
            risk_level        = phri_result.risk_level,
            rules_triggered   = triggered,
            reasoning         = reasoning,
            meta              = DISEASE_META[primary],
        )