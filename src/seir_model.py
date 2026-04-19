"""
seir_model.py
=============
Step 7 of the Sentin-AI build order.

Responsibilities:
  - Implement a lightweight SEIR epidemiological model in pure NumPy
  - PHRI score dynamically amplifies the transmission rate β
  - Use WorldPop population density for N (Bengaluru 5km radius)
  - Output a 14-day projected case curve
  - Return a SEIRResult dataclass with full projection + summary stats

SEIR equations (discrete daily steps):
  β_eff = base_β × (1 + phri_score)        ← README spec
  dS = -β_eff × S × I / N
  dE = +β_eff × S × I / N  - σ × E         σ = 1/incubation_period
  dI = +σ × E              - γ × I         γ = 1/infectious_period
  dR = +γ × I

Imported by: dashboard/app.py, gemini_voice.py

Usage (as module):
  from seir_model import SEIRModel
  model  = SEIRModel(disease_bucket="dengue_malaria")
  result = model.project(phri_score=0.73, days=14)
  print(result.peak_cases)
  print(result.case_curve)   # list of 14 daily new-case counts

Usage (CLI):
  python src/seir_model.py --phri 0.73 --disease dengue_malaria
  python src/seir_model.py --phri 0.55 --disease lepto_cholera --days 21
"""

import argparse
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

# ── Population parameters ──────────────────────────────────────────────────
# Bengaluru Urban, 5km radius surveillance area
# WorldPop India 2020 — ~3,500 people/km² × π×5² ≈ 275,000
# Update after downloading actual WorldPop GeoTIFF (Step 10)
DEFAULT_POPULATION = 275_000

# ── Disease-specific SEIR parameters ──────────────────────────────────────
# Sources: WHO disease fact sheets + published Indian outbreak studies
DISEASE_PARAMS = {
    "dengue_malaria": {
        "base_beta"          : 0.35,   # base transmission rate / day
        "incubation_days"    : 7,      # E → I  (extrinsic + intrinsic)
        "infectious_days"    : 5,      # I → R
        "initial_exposed"    : 10,     # seed exposed individuals
        "label"              : "Dengue / Malaria",
    },
    "lepto_cholera": {
        "base_beta"          : 0.25,
        "incubation_days"    : 7,
        "infectious_days"    : 7,
        "initial_exposed"    : 5,
        "label"              : "Leptospirosis / Cholera",
    },
    "respiratory": {
        "base_beta"          : 0.40,   # airborne — higher baseline
        "incubation_days"    : 3,
        "infectious_days"    : 5,
        "initial_exposed"    : 15,
        "label"              : "Respiratory / Airborne",
    },
    "general_risk": {
        "base_beta"          : 0.20,
        "incubation_days"    : 5,
        "infectious_days"    : 5,
        "initial_exposed"    : 5,
        "label"              : "General Outbreak Risk",
    },
    "none": {
        "base_beta"          : 0.10,
        "incubation_days"    : 5,
        "infectious_days"    : 5,
        "initial_exposed"    : 1,
        "label"              : "No Significant Risk",
    },
}


# ── Result dataclass ───────────────────────────────────────────────────────
@dataclass
class SEIRResult:
    disease_bucket  : str
    phri_score      : float
    population      : int
    projection_days : int
    beta_effective  : float          # β_eff = base_β × (1 + phri)

    # Daily compartment arrays  (length = projection_days + 1, includes day 0)
    S_curve         : list = field(default_factory=list)
    E_curve         : list = field(default_factory=list)
    I_curve         : list = field(default_factory=list)
    R_curve         : list = field(default_factory=list)
    new_cases_curve : list = field(default_factory=list)  # daily new infections

    # Summary stats
    peak_cases      : int   = 0
    peak_day        : int   = 0
    total_projected : int   = 0
    attack_rate_pct : float = 0.0    # % of population affected

    def __str__(self):
        return (
            f"SEIR [{self.disease_bucket}]  PHRI={self.phri_score:.2f}  "
            f"β_eff={self.beta_effective:.3f}\n"
            f"  Peak: {self.peak_cases} cases on day {self.peak_day}\n"
            f"  Total projected ({self.projection_days}d): {self.total_projected} cases "
            f"({self.attack_rate_pct:.2f}% attack rate)"
        )

    def summary_dict(self) -> dict:
        """Compact dict for Gemini and dashboard consumption."""
        return {
            "disease_label"    : DISEASE_PARAMS.get(self.disease_bucket, {}).get("label", ""),
            "projection_days"  : self.projection_days,
            "peak_cases"       : self.peak_cases,
            "peak_day"         : self.peak_day,
            "total_projected"  : self.total_projected,
            "attack_rate_pct"  : round(self.attack_rate_pct, 3),
            "beta_effective"   : round(self.beta_effective, 4),
            "phri_score"       : self.phri_score,
            "new_cases_curve"  : [round(v, 1) for v in self.new_cases_curve[1:]],
        }


# ── SEIR model class ───────────────────────────────────────────────────────
class SEIRModel:

    def __init__(self,
                 disease_bucket : str = "dengue_malaria",
                 population     : int = DEFAULT_POPULATION):
        if disease_bucket not in DISEASE_PARAMS:
            raise ValueError(
                f"Unknown disease bucket '{disease_bucket}'. "
                f"Choose from: {list(DISEASE_PARAMS.keys())}"
            )
        self.disease_bucket = disease_bucket
        self.population     = population
        self.params         = DISEASE_PARAMS[disease_bucket]

    def project(self,
                phri_score      : float,
                days            : int = 14,
                initial_infected: Optional[int] = None) -> SEIRResult:
        """
        Run the SEIR projection for `days` steps.

        phri_score      : float ∈ [0, 1] — from PHRIEngine
        days            : projection horizon (default 14)
        initial_infected: override seed infected count (default from params)
        """
        p   = self.params
        N   = self.population

        # β_eff = base_β × (1 + phri_score)  ← README equation
        base_beta = p["base_beta"]
        beta_eff  = base_beta * (1.0 + phri_score)
        beta_eff  = min(beta_eff, 0.99)    # cap at < 1 for stability

        sigma = 1.0 / p["incubation_days"]   # E → I rate
        gamma = 1.0 / p["infectious_days"]    # I → R rate

        # Initial conditions
        E0 = p["initial_exposed"]
        I0 = initial_infected if initial_infected is not None else 1
        R0_val = 0
        S0 = N - E0 - I0 - R0_val

        # State arrays (day 0 = current state)
        S = [float(S0)]
        E = [float(E0)]
        I = [float(I0)]
        R = [float(R0_val)]
        new_cases = [float(I0)]   # day 0 seed

        for _ in range(days):
            s, e, i, r = S[-1], E[-1], I[-1], R[-1]

            # Force of infection
            foi = beta_eff * s * i / N

            ds = -foi
            de = foi - sigma * e
            di = sigma * e - gamma * i
            dr = gamma * i

            S.append(max(s + ds, 0.0))
            E.append(max(e + de, 0.0))
            I.append(max(i + di, 0.0))
            R.append(max(r + dr, 0.0))
            new_cases.append(max(foi, 0.0))   # new infections this day

        # Summary statistics (days 1–14, excluding seed day 0)
        nc_arr      = np.array(new_cases[1:])
        peak_idx    = int(np.argmax(nc_arr))
        peak_cases  = int(round(nc_arr[peak_idx]))
        total_proj  = int(round(nc_arr.sum()))
        attack_rate = round(100.0 * total_proj / N, 4)

        result = SEIRResult(
            disease_bucket  = self.disease_bucket,
            phri_score      = phri_score,
            population      = N,
            projection_days = days,
            beta_effective  = round(beta_eff, 4),
            S_curve         = [round(v, 1) for v in S],
            E_curve         = [round(v, 1) for v in E],
            I_curve         = [round(v, 1) for v in I],
            R_curve         = [round(v, 1) for v in R],
            new_cases_curve = [round(v, 1) for v in new_cases],
            peak_cases      = peak_cases,
            peak_day        = peak_idx + 1,
            total_projected = total_proj,
            attack_rate_pct = attack_rate,
        )
        return result

    # ── Stress-test mode (for Streamlit slider) ───────────────────────────
    def stress_test(self,
                    phri_range : tuple = (0.0, 1.0),
                    steps      : int   = 11,
                    days       : int   = 14) -> list[SEIRResult]:
        """
        Run projection across a range of PHRI scores.
        Used by the Streamlit 'Stress Test' slider (Section 12 of README).
        Returns list of SEIRResult, one per PHRI value.
        """
        phri_values = np.linspace(phri_range[0], phri_range[1], steps)
        return [self.project(float(p), days=days) for p in phri_values]


# ── CLI ────────────────────────────────────────────────────────────────────
def run_cli(phri: float, disease: str, days: int):
    model  = SEIRModel(disease_bucket=disease)
    result = model.project(phri_score=phri, days=days)

    print(f"\n{'='*55}")
    print(result)
    print(f"{'='*55}")
    print(f"\n  Daily new cases (day 1 → {days}):")
    for d, v in enumerate(result.new_cases_curve[1:], 1):
        bar = "█" * int(v / max(result.peak_cases, 1) * 30)
        print(f"  Day {d:2d}: {v:6.1f}  {bar}")

    basic_r0 = model.params["base_beta"] / (1 / model.params["infectious_days"])
    eff_r0   = result.beta_effective    / (1 / model.params["infectious_days"])
    print(f"\n  Base R₀ : {basic_r0:.2f}")
    print(f"  Eff  R₀ : {eff_r0:.2f}  (PHRI-amplified)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentin-AI SEIR Projection")
    parser.add_argument("--phri",    type=float, default=0.73,
                        help="PHRI score 0.0–1.0")
    parser.add_argument("--disease", type=str,   default="dengue_malaria",
                        choices=list(DISEASE_PARAMS.keys()))
    parser.add_argument("--days",    type=int,   default=14,
                        help="Projection horizon in days")
    args = parser.parse_args()
    run_cli(args.phri, args.disease, args.days)