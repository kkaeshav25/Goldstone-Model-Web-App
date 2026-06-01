"""
Goldstone Model — Present-Day Data (2007 & 2024)
=================================================
Extends the historical pipeline with two additional data points:

  * 2007  — derived from Jenny Bryan's gapminder TSV (142 countries, lifeExp)
             available on GitHub at raw.githubusercontent.com
  * 2024  — hand-coded "current" profiles based on publicly available data:
             - IMR: World Bank / UNICEF 2022-2023 estimates
             - Regime type: V-Dem + Freedom House + author judgement
             - Neighboring conflicts: UCDP active conflicts as of 2024
             - Discrimination: V-Dem / US State Dept reports 2023-2024

Data sources for 2024 manual coding
-------------------------------------
IMR:        UNICEF State of the World's Children 2023; World Bank WDI 2022
Regime:     V-Dem v13 (2023); Freedom House Freedom in the World 2024
Conflict:   UCDP Conflict Encyclopedia 2023; ACLED 2024 summary reports
Discrim.:   US State Dept Country Reports on Human Rights Practices 2023;
            Minorities at Risk / MAR-X 2022

All values are best-effort estimates for an academic/educational model.
"""

from __future__ import annotations

import csv
import io
import logging
import math
from dataclasses import dataclass
from typing import Optional

import requests

from model import CountryProfile, RegimeType

logger = logging.getLogger(__name__)

JENNY_GAPMINDER_URL = (
    "https://raw.githubusercontent.com/jennybc/gapminder"
    "/master/inst/extdata/gapminder.tsv"
)

# Name mapping: jenny/gapminder → our dataset names
_JENNY_NAME_MAP: dict[str, str] = {
    "Korea, Dem. Rep.": "North Korea",
    "Korea, Rep.":      "South Korea",
}

# Hand-filled IMR for the 4 countries missing from jenny gapminder (2007 values)
_MANUAL_IMR_2007: dict[str, float] = {
    "Bahamas":   13.0,
    "Barbados":  11.5,
    "Georgia":   22.0,
    "Grenada":   14.0,
}

def life_to_imr(le: float) -> float:
    return round(max(2.0, min(280.0, math.exp(7.29 - 0.0576 * le))), 1)


# ===========================================================================
# 2024 PRESENT-DAY PROFILES
# ===========================================================================
# Format: country → (imr, regime_type, neighboring_conflicts, discrimination)
#
# IMR source: World Bank / UNICEF 2022 estimates (deaths per 1,000 live births)
# Regime:     V-Dem + Freedom House 2024
# Neighbors:  UCDP active armed conflicts 2023 (state-based, ≥25 deaths/yr)
# Discrim.:   US State Dept Human Rights Reports 2023

PRESENT_DAY_2024: dict[str, tuple[float, RegimeType, int, bool]] = {
    # ── Afghanistan ─────────────────────────────────────────────────────────
    # IMR ~55 (UNICEF 2022); Taliban full autocracy; neighbors: Pakistan (conflict),
    # Iran; discrimination against women, minorities (severe)
    "Afghanistan":      (55.0,  RegimeType.FULL_AUTOCRACY,           2, True),

    # ── Argentina ───────────────────────────────────────────────────────────
    # IMR ~8.8; polarized democracy (Milei election 2023); no neighbors at war
    "Argentina":        (8.8,   RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Australia ───────────────────────────────────────────────────────────
    "Australia":        (3.2,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Austria ─────────────────────────────────────────────────────────────
    "Austria":          (3.0,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Bahamas ─────────────────────────────────────────────────────────────
    "Bahamas":          (9.5,   RegimeType.PARTIAL_DEMOCRACY,        0, False),

    # ── Bangladesh ──────────────────────────────────────────────────────────
    # IMR ~25; Hasina autocratisation (now post-coup 2024); Myanmar neighbor conflict
    "Bangladesh":       (25.0,  RegimeType.PARTIAL_AUTOCRACY,        1, True),

    # ── Barbados ────────────────────────────────────────────────────────────
    "Barbados":         (8.5,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Belgium ─────────────────────────────────────────────────────────────
    "Belgium":          (3.1,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Bolivia ─────────────────────────────────────────────────────────────
    # IMR ~21; polarized (MAS vs opposition, 2023 attempted coup)
    "Bolivia":          (21.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Brazil ──────────────────────────────────────────────────────────────
    # IMR ~13; factionalized (Lula vs Bolsonaro blocs, Jan 6-style riots 2023)
    "Brazil":           (13.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Canada ──────────────────────────────────────────────────────────────
    "Canada":           (4.3,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Chile ───────────────────────────────────────────────────────────────
    # IMR ~6.5; stable democracy despite constitutional turbulence
    "Chile":            (6.5,   RegimeType.PARTIAL_DEMOCRACY,        0, False),

    # ── China ───────────────────────────────────────────────────────────────
    # IMR ~5.6; full autocracy; neighbors: Myanmar (conflict), North Korea
    "China":            (5.6,   RegimeType.FULL_AUTOCRACY,           2, True),

    # ── Colombia ────────────────────────────────────────────────────────────
    # IMR ~12; partial democracy (Petro); ongoing FARC dissidents/ELN conflict
    "Colombia":         (12.0,  RegimeType.PARTIAL_DEMOCRACY,        1, True),

    # ── Costa Rica ──────────────────────────────────────────────────────────
    "Costa Rica":       (7.5,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Croatia ─────────────────────────────────────────────────────────────
    "Croatia":          (4.5,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Cuba ────────────────────────────────────────────────────────────────
    # IMR ~4.3; full autocracy; economic crisis 2023-24
    "Cuba":             (4.3,   RegimeType.FULL_AUTOCRACY,           0, True),

    # ── Dominican Republic ──────────────────────────────────────────────────
    # IMR ~22; neighbor Haiti crisis
    "Dominican Republic": (22.0, RegimeType.PARTIAL_DEMOCRACY,       1, False),

    # ── Ecuador ─────────────────────────────────────────────────────────────
    # IMR ~14; crisis state (gang violence, Noboa emergency 2024); Colombia neighbor
    "Ecuador":          (14.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  1, True),

    # ── Egypt ───────────────────────────────────────────────────────────────
    # IMR ~16; full autocracy (Sisi); neighbors: Sudan (conflict), Libya, Gaza
    "Egypt":            (16.0,  RegimeType.FULL_AUTOCRACY,           3, True),

    # ── El Salvador ─────────────────────────────────────────────────────────
    # IMR ~12; Bukele autocratisation; no active neighbors
    "El Salvador":      (12.0,  RegimeType.PARTIAL_AUTOCRACY,        0, True),

    # ── Finland ─────────────────────────────────────────────────────────────
    # NATO member; Russia neighbor but not counted as "armed conflict"
    "Finland":          (2.3,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── France ──────────────────────────────────────────────────────────────
    "France":           (3.6,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Georgia ─────────────────────────────────────────────────────────────
    # IMR ~9; democratic backsliding 2024 (disputed elections, Russian influence)
    "Georgia":          (9.0,   RegimeType.FACTIONALIZED_DEMOCRACY,  1, False),

    # ── Germany ─────────────────────────────────────────────────────────────
    "Germany":          (3.1,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Greece ──────────────────────────────────────────────────────────────
    "Greece":           (3.7,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Grenada ─────────────────────────────────────────────────────────────
    "Grenada":          (13.0,  RegimeType.PARTIAL_DEMOCRACY,        0, False),

    # ── Haiti ───────────────────────────────────────────────────────────────
    # IMR ~46; state collapse 2024 (gang control of Port-au-Prince, no government)
    "Haiti":            (46.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  0, True),

    # ── Hong Kong, China ────────────────────────────────────────────────────
    # IMR ~2.5; full autocracy post-NSL 2020
    "Hong Kong, China": (2.5,   RegimeType.FULL_AUTOCRACY,           0, True),

    # ── Iceland ─────────────────────────────────────────────────────────────
    "Iceland":          (1.6,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── India ───────────────────────────────────────────────────────────────
    # IMR ~27; partial democracy (BJP majoritarianism, press freedom concerns);
    # neighbors: Pakistan (nuclear standoff counts), Myanmar
    "India":            (27.0,  RegimeType.PARTIAL_DEMOCRACY,        2, True),

    # ── Indonesia ───────────────────────────────────────────────────────────
    # IMR ~19; partial democracy; Papua conflict
    "Indonesia":        (19.0,  RegimeType.PARTIAL_DEMOCRACY,        0, True),

    # ── Iran ────────────────────────────────────────────────────────────────
    # IMR ~13; full autocracy; neighbors: Iraq (low-level), Yemen proxy, Azerbaijan
    "Iran":             (13.0,  RegimeType.FULL_AUTOCRACY,           3, True),

    # ── Iraq ────────────────────────────────────────────────────────────────
    # IMR ~22; factionalized democracy; neighbors: Syria, Iran, ISIS remnants
    "Iraq":             (22.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  3, True),

    # ── Ireland ─────────────────────────────────────────────────────────────
    "Ireland":          (2.9,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Israel ──────────────────────────────────────────────────────────────
    # IMR ~3.2; factionalized democracy (judicial crisis + Gaza war 2023-24);
    # neighbors: Gaza/Hamas, Lebanon/Hezbollah, Syria
    "Israel":           (3.2,   RegimeType.FACTIONALIZED_DEMOCRACY,  3, True),

    # ── Italy ───────────────────────────────────────────────────────────────
    "Italy":            (2.7,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Jamaica ─────────────────────────────────────────────────────────────
    "Jamaica":          (13.0,  RegimeType.PARTIAL_DEMOCRACY,        0, False),

    # ── Japan ───────────────────────────────────────────────────────────────
    "Japan":            (1.8,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Kenya ───────────────────────────────────────────────────────────────
    # IMR ~32; factionalized (Ruto vs Odinga; 2024 protests); neighbors: Sudan, Somalia, DRC
    "Kenya":            (32.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  3, True),

    # ── Lebanon ─────────────────────────────────────────────────────────────
    # IMR ~7; state collapse, Hezbollah war 2024; neighbors: Israel/Gaza, Syria
    "Lebanon":          (7.0,   RegimeType.FACTIONALIZED_DEMOCRACY,  2, True),

    # ── Mexico ──────────────────────────────────────────────────────────────
    # IMR ~12; partial democracy (AMLO→Sheinbaum); cartel violence counts as conflict
    "Mexico":           (12.0,  RegimeType.PARTIAL_DEMOCRACY,        0, True),

    # ── Netherlands ─────────────────────────────────────────────────────────
    "Netherlands":      (3.3,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── New Zealand ─────────────────────────────────────────────────────────
    "New Zealand":      (3.5,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Nigeria ─────────────────────────────────────────────────────────────
    # IMR ~70; factionalized (Tinubu disputed election 2023); Boko Haram, Niger coup neighbor
    "Nigeria":          (70.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  2, True),

    # ── North Korea ─────────────────────────────────────────────────────────
    # IMR ~18 (estimated); full autocracy
    "North Korea":      (18.0,  RegimeType.FULL_AUTOCRACY,           0, True),

    # ── Norway ──────────────────────────────────────────────────────────────
    "Norway":           (1.7,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Pakistan ────────────────────────────────────────────────────────────
    # IMR ~55; partial autocracy (military dominance, Imran Khan imprisoned);
    # neighbors: Afghanistan (Taliban), India (standoff)
    "Pakistan":         (55.0,  RegimeType.PARTIAL_AUTOCRACY,        2, True),

    # ── Peru ────────────────────────────────────────────────────────────────
    # IMR ~13; factionalized (Boluarte crisis, Castillo impeachment aftermath)
    "Peru":             (13.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Philippines ─────────────────────────────────────────────────────────
    # IMR ~22; factionalized (Marcos Jr vs Duterte split 2024); Mindanao conflict
    "Philippines":      (22.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  0, True),

    # ── Poland ──────────────────────────────────────────────────────────────
    # IMR ~4; full democracy (Tusk restored 2024); Ukraine neighbor
    "Poland":           (4.0,   RegimeType.FULL_DEMOCRACY,           1, False),

    # ── Portugal ────────────────────────────────────────────────────────────
    "Portugal":         (2.6,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Rwanda ──────────────────────────────────────────────────────────────
    # IMR ~29; full autocracy (Kagame); DRC war neighbor
    "Rwanda":           (29.0,  RegimeType.FULL_AUTOCRACY,           1, True),

    # ── Saudi Arabia ────────────────────────────────────────────────────────
    # IMR ~5.5; full autocracy; neighbors: Yemen war, Iraq
    "Saudi Arabia":     (5.5,   RegimeType.FULL_AUTOCRACY,           2, True),

    # ── South Africa ────────────────────────────────────────────────────────
    # IMR ~25; factionalized (ANC lost majority 2024, GNU coalition); Mozambique neighbor
    "South Africa":     (25.0,  RegimeType.FACTIONALIZED_DEMOCRACY,  1, False),

    # ── South Korea ─────────────────────────────────────────────────────────
    # IMR ~2.5; factionalized (Yoon martial law crisis Dec 2024)
    "South Korea":      (2.5,   RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Spain ───────────────────────────────────────────────────────────────
    "Spain":            (2.6,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Switzerland ─────────────────────────────────────────────────────────
    "Switzerland":      (3.5,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── Turkey ──────────────────────────────────────────────────────────────
    # IMR ~8.5; partial autocracy (Erdogan); neighbors: Syria, Iraq, Armenia
    "Turkey":           (8.5,   RegimeType.PARTIAL_AUTOCRACY,        3, True),

    # ── United Kingdom ──────────────────────────────────────────────────────
    "United Kingdom":   (3.6,   RegimeType.FULL_DEMOCRACY,           0, False),

    # ── United States ───────────────────────────────────────────────────────
    # IMR ~5.4; factionalized democracy (Jan 6 legacy, deep polarisation 2024)
    "United States":    (5.4,   RegimeType.FACTIONALIZED_DEMOCRACY,  0, False),

    # ── Venezuela ───────────────────────────────────────────────────────────
    # IMR ~21; full autocracy (Maduro stole 2024 election); Colombia border conflict
    "Venezuela":        (21.0,  RegimeType.FULL_AUTOCRACY,           1, True),
}


# ===========================================================================
# Fetching 2007 data from jenny/gapminder
# ===========================================================================

def fetch_imr_2007(timeout: int = 15) -> dict[str, float]:
    """
    Fetch 2007 IMR estimates derived from Jenny Bryan's gapminder TSV.
    Returns { country_name: imr } for ~142 countries.
    Falls back to manual estimates for the 4 countries not in the dataset.
    """
    logger.info("Fetching Jenny gapminder (2007 life expectancy data)")
    resp = requests.get(JENNY_GAPMINDER_URL, timeout=timeout)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text), delimiter="\t")
    result: dict[str, float] = {}
    for row in reader:
        if row["year"] != "2007":
            continue
        name = _JENNY_NAME_MAP.get(row["country"], row["country"])
        try:
            result[name] = life_to_imr(float(row["lifeExp"]))
        except (ValueError, KeyError):
            pass

    result.update(_MANUAL_IMR_2007)
    logger.info("2007 IMR data: %d countries", len(result))
    return result


# ===========================================================================
# Building profiles
# ===========================================================================

def build_profiles_2007(
    imr_2007: dict[str, float],
    pipeline_countries: list[str],
) -> list[CountryProfile]:
    """
    Build 2007 CountryProfiles for all countries in the pipeline dataset.
    Uses IMR from jenny/gapminder; regime/conflict/discrimination from the
    pipeline's existing 2005 annotations (nearest prior year fallback).
    """
    from pipeline import DataPipeline
    dp = DataPipeline()

    profiles = []
    for country in pipeline_countries:
        imr = imr_2007.get(country)
        if imr is None:
            logger.warning("No 2007 IMR for %s, skipping", country)
            continue
        regime  = dp.get_regime(country, 2007)
        nb, disc = dp.get_conflict_disc(country, 2007)
        profiles.append(CountryProfile(
            regime_type=regime,
            infant_mortality=imr,
            neighboring_conflicts=nb,
            state_discrimination=disc,
            country_name=country,
            year=2007,
        ))
    return profiles


def build_profiles_2024(pipeline_countries: list[str]) -> list[CountryProfile]:
    """
    Build 2024 CountryProfiles from the hand-coded PRESENT_DAY_2024 table.
    Only includes countries present in both the pipeline dataset and the 2024 table.
    """
    profiles = []
    for country in pipeline_countries:
        if country not in PRESENT_DAY_2024:
            logger.info("No 2024 data for %s", country)
            continue
        imr, regime, nb, disc = PRESENT_DAY_2024[country]
        profiles.append(CountryProfile(
            regime_type=regime,
            infant_mortality=imr,
            neighboring_conflicts=nb,
            state_discrimination=disc,
            country_name=country,
            year=2024,
        ))
    return profiles


# ===========================================================================
# Public API
# ===========================================================================

@dataclass
class PresentDayResult:
    forecasts_2007: dict[str, object]   # country → InstabilityForecast
    forecasts_2024: dict[str, object]   # country → InstabilityForecast
    errors: list[str]


def fetch_present_day(pipeline_countries: list[str]) -> PresentDayResult:
    """
    Fetch 2007 data remotely and combine with hand-coded 2024 profiles.
    Score both years and return a PresentDayResult.
    """
    from model import score

    errors: list[str] = []
    forecasts_2007: dict[str, object] = {}
    forecasts_2024: dict[str, object] = {}

    # ── 2007 ────────────────────────────────────────────────────────────────
    try:
        imr_2007 = fetch_imr_2007()
        for profile in build_profiles_2007(imr_2007, pipeline_countries):
            try:
                forecasts_2007[profile.country_name] = score(profile)
            except Exception as e:
                errors.append(f"2007 score failed for {profile.country_name}: {e}")
    except Exception as e:
        errors.append(f"Failed to fetch 2007 data: {e}")

    # ── 2024 ────────────────────────────────────────────────────────────────
    for profile in build_profiles_2024(pipeline_countries):
        try:
            forecasts_2024[profile.country_name] = score(profile)
        except Exception as e:
            errors.append(f"2024 score failed for {profile.country_name}: {e}")

    logger.info(
        "Present-day: 2007=%d countries, 2024=%d countries, errors=%d",
        len(forecasts_2007), len(forecasts_2024), len(errors),
    )
    return PresentDayResult(
        forecasts_2007=forecasts_2007,
        forecasts_2024=forecasts_2024,
        errors=errors,
    )