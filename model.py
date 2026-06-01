"""
Goldstone et al. (2010) Political Instability Model
====================================================
Implements the PITF conditional logistic regression model from:
  Goldstone, J.A. et al. "A Global Model for Forecasting Political Instability."
  American Journal of Political Science 54(1): 190-208. 2010.

The model predicts the probability of political instability onset within two years
based on four variables:
  1. Regime type      (5-category Polity IV–derived classification)
  2. Infant mortality (per 1,000 live births — proxy for state capacity)
  3. Neighboring armed conflict (count of bordering states at war)
  4. State-led political discrimination (binary)

Coefficients are calibrated to the published odds ratios and directional effects
from Table 1 of the paper. The intercept is set so that the model's base-rate
probability (~2%) matches the empirical 1955-2003 rate for a full democracy with
low IMR, no neighbours at war, and no discrimination.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Regime type taxonomy (Polity IV five-category scheme)
# ---------------------------------------------------------------------------

class RegimeType(str, Enum):
    FULL_AUTOCRACY        = "full_autocracy"
    PARTIAL_AUTOCRACY     = "partial_autocracy"
    FACTIONALIZED_DEMOCRACY = "factionalized_democracy"
    PARTIAL_DEMOCRACY     = "partial_democracy"
    FULL_DEMOCRACY        = "full_democracy"

    @property
    def label(self) -> str:
        return {
            "full_autocracy":           "Full Autocracy",
            "partial_autocracy":        "Partial Autocracy",
            "factionalized_democracy":  "Factionalized Democracy",
            "partial_democracy":        "Partial Democracy",
            "full_democracy":           "Full Democracy",
        }[self.value]

    @property
    def description(self) -> str:
        return {
            "full_autocracy":           "No competitive elections; highly repressive (e.g. Saudi Arabia, Sudan)",
            "partial_autocracy":        "Competitive elections for national office but repressed participation",
            "factionalized_democracy":  "Competing blocs sharply polarised; may involve intimidation — HIGHEST RISK",
            "partial_democracy":        "Open, competitive elections but weakly institutionalised",
            "full_democracy":           "Free & fair elections with open, institutionalised participation (e.g. OECD)",
        }[self.value]

    @property
    def polity_range(self) -> str:
        return {
            "full_autocracy":           "Polity ≤ −6",
            "partial_autocracy":        "Polity −5 to +5 (non-factional)",
            "factionalized_democracy":  "Polity −5 to +5 (factional)",
            "partial_democracy":        "Polity +6 to +9",
            "full_democracy":           "Polity = +10",
        }[self.value]


# ---------------------------------------------------------------------------
# Published (approximate) log-odds contributions derived from Table 1
# Goldstone et al. report odds ratios relative to the full-democracy baseline.
# We convert: β = ln(OR). These are the *marginal* regime contributions.
# ---------------------------------------------------------------------------
#
# Regime OR (vs full democracy):
#   full_autocracy         ~2.5  → β ≈  0.92
#   partial_autocracy      ~4.0  → β ≈  1.39
#   factionalized_democracy ~9.5 → β ≈  2.25  ← largest single predictor
#   partial_democracy       ~3.2 → β ≈  1.16
#   full_democracy           1.0 → β =  0.00  (reference)
#
# IMR: per PITF, 75th vs 25th pctile OR ≈ 2.3  (roughly +45 deaths/1000)
#   → β per unit = ln(2.3) / 45 ≈ 0.019
#
# Neighbouring conflict: OR per additional neighbour ≈ 1.4
#   → β per neighbour = ln(1.4) ≈ 0.34
#
# Discrimination: OR ≈ 2.9  → β ≈ 1.06

_REGIME_BETAS: dict[RegimeType, float] = {
    RegimeType.FULL_AUTOCRACY:           0.92,
    RegimeType.PARTIAL_AUTOCRACY:        1.39,
    RegimeType.FACTIONALIZED_DEMOCRACY:  2.25,
    RegimeType.PARTIAL_DEMOCRACY:        1.16,
    RegimeType.FULL_DEMOCRACY:           0.00,
}

_IMR_BETA_PER_UNIT:       float = 0.019   # per 1 death / 1000 live births
_NEIGHBOR_BETA_PER_UNIT:  float = 0.336   # per additional bordering conflict
_DISCRIMINATION_BETA:     float = 1.064   # binary 0/1

# Intercept calibrated so that a full democracy, IMR=5, 0 neighbours, no
# discrimination gives P ≈ 0.015 (~base rate).
_INTERCEPT: float = -4.20


# ---------------------------------------------------------------------------
# Input / Output data classes
# ---------------------------------------------------------------------------

@dataclass
class CountryProfile:
    """A single country-year observation to score."""
    regime_type:          RegimeType
    infant_mortality:     float          # deaths per 1,000 live births, range 1–300
    neighboring_conflicts: int           # 0–10 bordering states with active armed conflict
    state_discrimination: bool           # active state-led political discrimination?
    country_name:         Optional[str]  = None
    year:                 Optional[int]  = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not (1 <= self.infant_mortality <= 300):
            errors.append(f"infant_mortality must be 1–300 (got {self.infant_mortality})")
        if not (0 <= self.neighboring_conflicts <= 10):
            errors.append(f"neighboring_conflicts must be 0–10 (got {self.neighboring_conflicts})")
        return errors


@dataclass
class VariableContribution:
    variable:         str
    raw_beta:         float          # log-odds contribution
    share_of_total:   float          # proportion of total positive log-odds (0–1)
    direction:        str            # "stabilising" | "destabilising" | "neutral"
    note:             str            = ""


@dataclass
class InstabilityForecast:
    """Full model output for a single CountryProfile."""
    country_name:       Optional[str]
    year:               Optional[int]
    regime_type:        str
    infant_mortality:   float
    neighboring_conflicts: int
    state_discrimination: bool

    # Core prediction
    logit:              float
    probability:        float          # 0–1
    probability_pct:    float          # 0–100, rounded 1dp
    risk_band:          str            # "Low" | "Moderate" | "High" | "Very High"
    risk_band_threshold: float         # cutoff probability used

    # Decomposition
    contributions:      list[VariableContribution] = field(default_factory=list)

    # Odds ratios vs reference category
    odds_ratio_vs_stable: float = 1.0   # OR compared to "safest" profile

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Risk-band configuration
# ---------------------------------------------------------------------------

RISK_BANDS = [
    (0.15, "Low",       "Below the historical base rate (~2%). Institutional structure appears robust."),
    (0.35, "Moderate",  "Elevated above base rate. One risk factor present; qualitative monitoring advisable."),
    (0.60, "High",      "Significantly elevated. Multiple structural vulnerabilities co-present."),
    (1.01, "Very High", "Strong instability signal. Multiple co-occurring factors; model places country in top-decile risk."),
]


def _risk_band(p: float) -> tuple[str, float, str]:
    for threshold, label, note in RISK_BANDS:
        if p < threshold:
            return label, threshold, note
    return "Very High", 1.0, RISK_BANDS[-1][2]


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

def score(profile: CountryProfile) -> InstabilityForecast:
    """
    Compute the Goldstone instability probability for a single CountryProfile.

    Returns an InstabilityForecast with probability, risk band, and
    per-variable contributions.
    """
    errors = profile.validate()
    if errors:
        raise ValueError(f"Invalid profile: {'; '.join(errors)}")

    regime_beta  = _REGIME_BETAS[profile.regime_type]
    imr_beta     = _IMR_BETA_PER_UNIT * profile.infant_mortality
    neighbor_beta = _NEIGHBOR_BETA_PER_UNIT * profile.neighboring_conflicts
    disc_beta    = _DISCRIMINATION_BETA if profile.state_discrimination else 0.0

    logit = _INTERCEPT + regime_beta + imr_beta + neighbor_beta + disc_beta
    prob  = 1.0 / (1.0 + math.exp(-logit))

    band, threshold, _ = _risk_band(prob)

    # Variable contributions (share of total *positive* log-odds above intercept)
    positive_contributions = [
        ("Regime type",               regime_beta),
        ("Infant mortality",           imr_beta),
        ("Neighboring armed conflict", neighbor_beta),
        ("State-led discrimination",   disc_beta),
    ]
    total_positive = sum(max(b, 0) for _, b in positive_contributions) or 1e-9

    contributions = []
    for label, beta in positive_contributions:
        share = max(beta, 0) / total_positive
        direction = "destabilising" if beta > 0.05 else ("stabilising" if beta < -0.05 else "neutral")
        contributions.append(VariableContribution(
            variable=label,
            raw_beta=round(beta, 4),
            share_of_total=round(share, 4),
            direction=direction,
        ))

    # OR vs safest reference profile (full democracy, IMR=5, 0 neighbours, no disc)
    logit_ref  = _INTERCEPT + 0.0 + (_IMR_BETA_PER_UNIT * 5) + 0.0 + 0.0
    prob_ref   = 1.0 / (1.0 + math.exp(-logit_ref))
    odds_country = prob / (1 - prob)
    odds_ref     = prob_ref / (1 - prob_ref)
    or_vs_stable = round(odds_country / odds_ref, 2) if odds_ref > 0 else float("inf")

    return InstabilityForecast(
        country_name=profile.country_name,
        year=profile.year,
        regime_type=profile.regime_type.value,
        infant_mortality=round(profile.infant_mortality, 1),
        neighboring_conflicts=profile.neighboring_conflicts,
        state_discrimination=profile.state_discrimination,
        logit=round(logit, 4),
        probability=round(prob, 4),
        probability_pct=round(prob * 100, 1),
        risk_band=band,
        risk_band_threshold=threshold,
        contributions=contributions,
        odds_ratio_vs_stable=or_vs_stable,
    )


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------

@dataclass
class SensitivityResult:
    variable:    str
    low_value:   float | str | bool
    high_value:  float | str | bool
    prob_low:    float
    prob_high:   float
    delta_prob:  float      # high - low
    elasticity:  float      # proportional change in prob per unit change in variable


def sensitivity_analysis(base_profile: CountryProfile) -> list[SensitivityResult]:
    """
    One-at-a-time sensitivity: vary each variable across its plausible range
    while holding the others at their base values. Returns ranked results
    (largest absolute delta first).
    """
    results: list[SensitivityResult] = []
    base_prob = score(base_profile).probability

    # IMR: 5th pctile (≈10) vs 95th pctile (≈150)
    for low_imr, high_imr in [(10, 150)]:
        p_low  = score(CountryProfile(base_profile.regime_type, low_imr,  base_profile.neighboring_conflicts, base_profile.state_discrimination)).probability
        p_high = score(CountryProfile(base_profile.regime_type, high_imr, base_profile.neighboring_conflicts, base_profile.state_discrimination)).probability
        delta = p_high - p_low
        elas  = abs(delta / (high_imr - low_imr)) * (1 / (base_prob + 1e-9))
        results.append(SensitivityResult("Infant mortality", low_imr, high_imr, round(p_low,4), round(p_high,4), round(delta,4), round(elas,4)))

    # Neighbours: 0 vs 5
    p_low  = score(CountryProfile(base_profile.regime_type, base_profile.infant_mortality, 0, base_profile.state_discrimination)).probability
    p_high = score(CountryProfile(base_profile.regime_type, base_profile.infant_mortality, 5, base_profile.state_discrimination)).probability
    delta = p_high - p_low
    results.append(SensitivityResult("Neighboring conflicts", 0, 5, round(p_low,4), round(p_high,4), round(delta,4), round(abs(delta)/5,4)))

    # Discrimination: off vs on
    p_low  = score(CountryProfile(base_profile.regime_type, base_profile.infant_mortality, base_profile.neighboring_conflicts, False)).probability
    p_high = score(CountryProfile(base_profile.regime_type, base_profile.infant_mortality, base_profile.neighboring_conflicts, True)).probability
    delta = p_high - p_low
    results.append(SensitivityResult("State discrimination", False, True, round(p_low,4), round(p_high,4), round(delta,4), round(abs(delta),4)))

    # Regime sweep: best vs worst
    p_best  = score(CountryProfile(RegimeType.FULL_DEMOCRACY,           base_profile.infant_mortality, base_profile.neighboring_conflicts, base_profile.state_discrimination)).probability
    p_worst = score(CountryProfile(RegimeType.FACTIONALIZED_DEMOCRACY,  base_profile.infant_mortality, base_profile.neighboring_conflicts, base_profile.state_discrimination)).probability
    delta = p_worst - p_best
    results.append(SensitivityResult("Regime type", "Full democracy", "Factionalized democracy", round(p_best,4), round(p_worst,4), round(delta,4), round(abs(delta),4)))

    results.sort(key=lambda r: abs(r.delta_prob), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

def score_batch(profiles: list[CountryProfile]) -> list[InstabilityForecast]:
    return [score(p) for p in profiles]


# ---------------------------------------------------------------------------
# Convenience: build a profile from a Polity IV score + raw data
# ---------------------------------------------------------------------------

def polity_to_regime(polity_score: int, factional: bool = False) -> RegimeType:
    """
    Map a raw Polity IV score (−10 to +10) to the five-category scheme.
    The 'factional' flag distinguishes partial autocracies with factionalism
    from standard partial democracies in the −5 to +5 band.
    """
    if polity_score <= -6:
        return RegimeType.FULL_AUTOCRACY
    elif -5 <= polity_score <= 5:
        return RegimeType.FACTIONALIZED_DEMOCRACY if factional else RegimeType.PARTIAL_AUTOCRACY
    elif 6 <= polity_score <= 9:
        return RegimeType.PARTIAL_DEMOCRACY
    else:  # +10
        return RegimeType.FULL_DEMOCRACY 

                
