"""
Goldstone Model — Data Pipeline
================================
Fetches, normalizes, and structures historical country-year data for the
four PITF variables: regime type, infant mortality, neighboring conflict,
and state-led discrimination.

Data sources
------------
* Infant mortality (IMR): derived from life-expectancy data (Gapminder /
  Vega-datasets mirror on GitHub) using a calibrated exponential mapping.
  Formula: IMR = exp(7.29 − 0.0576 × life_expectancy), calibrated to known
  anchor points (Niger 1960 ≈ 220, USA 1960 ≈ 26).

* Regime type: hand-coded historical annotations for ~30 countries covering
  major transitions, supplemented by sensible defaults. In a production
  deployment, replace/extend with the Polity V dataset from systemicpeace.org.

* Neighboring conflicts & discrimination: hand-coded annotations for key
  cases. Production deployment would use UCDP GED (conflict) and Minorities
  at Risk (discrimination).

Architecture
------------
DataPipeline.fetch()          → pull raw data from remote + embedded sources
DataPipeline.build_profiles() → assemble CountryProfile objects for all
                                 country-years and run the model
DataPipeline.country_series() → time series of forecasts for one country
DataPipeline.all_series()     → time series for all countries
"""

from __future__ import annotations

import math
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

from model import CountryProfile, RegimeType, InstabilityForecast, score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GAPMINDER_URL = (
    "https://raw.githubusercontent.com/vega/vega-datasets/main/data/gapminder.json"
)

AVAILABLE_YEARS = [1955, 1960, 1965, 1970, 1975, 1980, 1985, 1990, 1995, 2000, 2005]


# ---------------------------------------------------------------------------
# IMR derivation from life expectancy
# ---------------------------------------------------------------------------

def life_expectancy_to_imr(life_expect: float) -> float:
    """
    Convert a life-expectancy value to an approximate infant mortality rate
    (deaths per 1,000 live births).

    Calibration anchors:
      - Niger/Afghanistan 1960: le ≈ 33 → IMR ≈ 219
      - USA 1960:               le ≈ 70 → IMR ≈ 26
      - Sweden 2000:            le ≈ 80 → IMR ≈ 15
    """
    return round(max(2.0, min(280.0, math.exp(7.29 - 0.0576 * life_expect))), 1)


# ---------------------------------------------------------------------------
# Historical regime annotations
# ---------------------------------------------------------------------------
# Format: { country_name: { year: RegimeType } }
# Annotate known transitions; years not listed fall back to nearest prior year,
# then to a region-based heuristic default.

REGIME_HISTORY: dict[str, dict[int, RegimeType]] = {
    "Afghanistan": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1970: RegimeType.FULL_AUTOCRACY,
        1980: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FULL_AUTOCRACY,
        1995: RegimeType.FULL_AUTOCRACY,
        2000: RegimeType.FULL_AUTOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Argentina": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1970: RegimeType.FULL_AUTOCRACY,
        1975: RegimeType.FULL_AUTOCRACY,
        1980: RegimeType.FULL_AUTOCRACY,
        1985: RegimeType.PARTIAL_DEMOCRACY,
        1990: RegimeType.PARTIAL_DEMOCRACY,
        1995: RegimeType.PARTIAL_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Bangladesh": {
        1955: RegimeType.FULL_AUTOCRACY,
        1975: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1995: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Bolivia": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1965: RegimeType.FULL_AUTOCRACY,
        1980: RegimeType.FULL_AUTOCRACY,
        1985: RegimeType.PARTIAL_DEMOCRACY,
        1995: RegimeType.PARTIAL_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Brazil": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1965: RegimeType.FULL_AUTOCRACY,
        1985: RegimeType.PARTIAL_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.PARTIAL_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Chile": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1970: RegimeType.FACTIONALIZED_DEMOCRACY,
        1975: RegimeType.FULL_AUTOCRACY,
        1985: RegimeType.PARTIAL_AUTOCRACY,
        1990: RegimeType.PARTIAL_DEMOCRACY,
        2000: RegimeType.FULL_DEMOCRACY,
    },
    "China": {
        1955: RegimeType.FULL_AUTOCRACY,
    },
    "Colombia": {
        1955: RegimeType.FACTIONALIZED_DEMOCRACY,
        1960: RegimeType.FACTIONALIZED_DEMOCRACY,
        1965: RegimeType.PARTIAL_DEMOCRACY,
        1980: RegimeType.FACTIONALIZED_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Cuba": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1960: RegimeType.FULL_AUTOCRACY,
    },
    "Egypt": {
        1955: RegimeType.FULL_AUTOCRACY,
    },
    "El Salvador": {
        1955: RegimeType.FULL_AUTOCRACY,
        1985: RegimeType.FACTIONALIZED_DEMOCRACY,
        1995: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Georgia": {
        1955: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1995: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.PARTIAL_AUTOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Haiti": {
        1955: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1995: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "India": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1975: RegimeType.PARTIAL_AUTOCRACY,
        1980: RegimeType.PARTIAL_DEMOCRACY,
        1990: RegimeType.PARTIAL_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Indonesia": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1965: RegimeType.FULL_AUTOCRACY,
        1999: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Iran": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1980: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FULL_AUTOCRACY,
        2000: RegimeType.PARTIAL_AUTOCRACY,
        2005: RegimeType.PARTIAL_AUTOCRACY,
    },
    "Iraq": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1970: RegimeType.FULL_AUTOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Kenya": {
        1955: RegimeType.FULL_AUTOCRACY,
        1963: RegimeType.PARTIAL_DEMOCRACY,
        1970: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.PARTIAL_AUTOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Lebanon": {
        1955: RegimeType.FACTIONALIZED_DEMOCRACY,
        1975: RegimeType.FACTIONALIZED_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Mexico": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1990: RegimeType.PARTIAL_AUTOCRACY,
        2000: RegimeType.PARTIAL_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Nigeria": {
        1955: RegimeType.FULL_AUTOCRACY,
        1960: RegimeType.PARTIAL_DEMOCRACY,
        1966: RegimeType.FULL_AUTOCRACY,
        1980: RegimeType.PARTIAL_AUTOCRACY,
        1985: RegimeType.FULL_AUTOCRACY,
        1999: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "North Korea": {
        1955: RegimeType.FULL_AUTOCRACY,
    },
    "Pakistan": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1960: RegimeType.FULL_AUTOCRACY,
        1971: RegimeType.PARTIAL_DEMOCRACY,
        1978: RegimeType.FULL_AUTOCRACY,
        1988: RegimeType.FACTIONALIZED_DEMOCRACY,
        1999: RegimeType.FULL_AUTOCRACY,
        2002: RegimeType.PARTIAL_AUTOCRACY,
        2005: RegimeType.PARTIAL_AUTOCRACY,
    },
    "Peru": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1968: RegimeType.FULL_AUTOCRACY,
        1980: RegimeType.PARTIAL_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1992: RegimeType.PARTIAL_AUTOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Philippines": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1972: RegimeType.FULL_AUTOCRACY,
        1986: RegimeType.FACTIONALIZED_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.FACTIONALIZED_DEMOCRACY,
    },
    "Rwanda": {
        1955: RegimeType.FULL_AUTOCRACY,
        1962: RegimeType.PARTIAL_AUTOCRACY,
        1973: RegimeType.FULL_AUTOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1995: RegimeType.FULL_AUTOCRACY,
        2000: RegimeType.FULL_AUTOCRACY,
        2005: RegimeType.PARTIAL_AUTOCRACY,
    },
    "Saudi Arabia": {
        1955: RegimeType.FULL_AUTOCRACY,
    },
    "South Africa": {
        1955: RegimeType.PARTIAL_AUTOCRACY,
        1994: RegimeType.PARTIAL_DEMOCRACY,
        2000: RegimeType.PARTIAL_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "South Korea": {
        1955: RegimeType.FULL_AUTOCRACY,
        1963: RegimeType.PARTIAL_AUTOCRACY,
        1972: RegimeType.FULL_AUTOCRACY,
        1988: RegimeType.PARTIAL_DEMOCRACY,
        1993: RegimeType.FULL_DEMOCRACY,
        2000: RegimeType.FULL_DEMOCRACY,
    },
    "Turkey": {
        1955: RegimeType.PARTIAL_DEMOCRACY,
        1960: RegimeType.FULL_AUTOCRACY,
        1965: RegimeType.PARTIAL_DEMOCRACY,
        1980: RegimeType.FULL_AUTOCRACY,
        1983: RegimeType.PARTIAL_DEMOCRACY,
        1995: RegimeType.FACTIONALIZED_DEMOCRACY,
        2000: RegimeType.FACTIONALIZED_DEMOCRACY,
        2005: RegimeType.PARTIAL_DEMOCRACY,
    },
    "Venezuela": {
        1955: RegimeType.FULL_AUTOCRACY,
        1959: RegimeType.FACTIONALIZED_DEMOCRACY,
        1970: RegimeType.PARTIAL_DEMOCRACY,
        1990: RegimeType.FACTIONALIZED_DEMOCRACY,
        1998: RegimeType.PARTIAL_AUTOCRACY,
        2000: RegimeType.PARTIAL_AUTOCRACY,
        2005: RegimeType.PARTIAL_AUTOCRACY,
    },
    # Western democracies — stable throughout
    "Australia":       {1955: RegimeType.FULL_DEMOCRACY},
    "Austria":         {1955: RegimeType.FULL_DEMOCRACY},
    "Belgium":         {1955: RegimeType.FULL_DEMOCRACY},
    "Canada":          {1955: RegimeType.FULL_DEMOCRACY},
    "Costa Rica":      {1955: RegimeType.FULL_DEMOCRACY},
    "Finland":         {1955: RegimeType.FULL_DEMOCRACY},
    "France":          {1955: RegimeType.FULL_DEMOCRACY},
    "Germany":         {1955: RegimeType.FULL_DEMOCRACY},
    "Greece":          {1955: RegimeType.PARTIAL_DEMOCRACY, 1967: RegimeType.FULL_AUTOCRACY, 1975: RegimeType.FULL_DEMOCRACY},
    "Iceland":         {1955: RegimeType.FULL_DEMOCRACY},
    "Ireland":         {1955: RegimeType.FULL_DEMOCRACY},
    "Israel":          {1955: RegimeType.PARTIAL_DEMOCRACY, 1980: RegimeType.FULL_DEMOCRACY},
    "Italy":           {1955: RegimeType.FACTIONALIZED_DEMOCRACY, 1980: RegimeType.PARTIAL_DEMOCRACY, 1995: RegimeType.FULL_DEMOCRACY},
    "Japan":           {1955: RegimeType.FULL_DEMOCRACY},
    "Netherlands":     {1955: RegimeType.FULL_DEMOCRACY},
    "New Zealand":     {1955: RegimeType.FULL_DEMOCRACY},
    "Norway":          {1955: RegimeType.FULL_DEMOCRACY},
    "Portugal":        {1955: RegimeType.FULL_AUTOCRACY, 1975: RegimeType.FACTIONALIZED_DEMOCRACY, 1980: RegimeType.FULL_DEMOCRACY},
    "Spain":           {1955: RegimeType.FULL_AUTOCRACY, 1978: RegimeType.PARTIAL_DEMOCRACY, 1985: RegimeType.FULL_DEMOCRACY},
    "Switzerland":     {1955: RegimeType.FULL_DEMOCRACY},
    "United Kingdom":  {1955: RegimeType.FULL_DEMOCRACY},
    "United States":   {1955: RegimeType.FULL_DEMOCRACY},
    # Others
    "Croatia":         {1955: RegimeType.FULL_AUTOCRACY, 1991: RegimeType.PARTIAL_AUTOCRACY, 2000: RegimeType.PARTIAL_DEMOCRACY, 2005: RegimeType.FULL_DEMOCRACY},
    "Cuba":            {1960: RegimeType.FULL_AUTOCRACY},
    "Dominican Republic": {1955: RegimeType.PARTIAL_AUTOCRACY, 1966: RegimeType.PARTIAL_DEMOCRACY, 2000: RegimeType.PARTIAL_DEMOCRACY},
    "Ecuador":         {1955: RegimeType.PARTIAL_AUTOCRACY, 1979: RegimeType.PARTIAL_DEMOCRACY, 2000: RegimeType.FACTIONALIZED_DEMOCRACY},
    "Hong Kong, China":{1955: RegimeType.FULL_AUTOCRACY},
    "Jamaica":         {1955: RegimeType.PARTIAL_DEMOCRACY, 1962: RegimeType.PARTIAL_DEMOCRACY},
    "Poland":          {1955: RegimeType.FULL_AUTOCRACY, 1990: RegimeType.PARTIAL_DEMOCRACY, 1995: RegimeType.FULL_DEMOCRACY},
}

# Default regime for countries without specific annotations (by broad region heuristic)
_DEFAULT_REGIME_BY_PREFIX: list[tuple[str, RegimeType]] = []
_GLOBAL_DEFAULT = RegimeType.PARTIAL_AUTOCRACY


# ---------------------------------------------------------------------------
# Historical conflict/discrimination overrides for known high-risk cases
# ---------------------------------------------------------------------------

# Format: { country: { year: (neighboring_conflicts, state_discrimination) } }
CONFLICT_DISC_HISTORY: dict[str, dict[int, tuple[int, bool]]] = {
    "Afghanistan":      {1980: (2, True), 1985: (2, True), 1990: (3, True), 1995: (3, True), 2000: (3, True), 2005: (4, True)},
    "Bangladesh":       {1971: (1, True), 1975: (1, True)},
    "Bolivia":          {1980: (1, False), 1985: (1, False)},
    "Colombia":         {1985: (1, True), 1990: (1, True), 1995: (1, True), 2000: (1, True), 2005: (1, True)},
    "El Salvador":      {1980: (2, True), 1985: (2, True), 1990: (1, True)},
    "Georgia":          {1990: (2, True), 1995: (2, True)},
    "Haiti":            {1990: (0, True), 1995: (0, True), 2000: (0, True)},
    "India":            {1965: (1, True), 1990: (1, True), 1995: (1, True), 2000: (1, True)},
    "Indonesia":        {1965: (1, True), 1975: (1, True), 1995: (1, True), 2000: (1, True)},
    "Iran":             {1980: (2, True), 1985: (2, True), 1990: (1, True)},
    "Iraq":             {1980: (2, True), 1985: (2, True), 1990: (2, True), 1995: (2, True), 2000: (1, True), 2005: (3, True)},
    "Kenya":            {1995: (1, True), 2000: (1, True), 2005: (1, True)},
    "Lebanon":          {1975: (2, True), 1980: (2, True), 1985: (3, True), 1990: (2, True), 2000: (1, True), 2005: (1, True)},
    "Nigeria":          {1965: (0, True), 1970: (0, True), 1990: (0, True), 1995: (0, True), 2000: (0, True), 2005: (0, True)},
    "North Korea":      {1955: (2, True), 1960: (1, True)},
    "Pakistan":         {1965: (1, True), 1971: (1, True), 1980: (2, True), 1985: (2, True), 1995: (1, True), 2000: (2, True), 2005: (2, True)},
    "Peru":             {1985: (1, True), 1990: (1, True), 1995: (1, True)},
    "Philippines":      {1972: (0, True), 1980: (0, True), 1990: (1, True), 2000: (1, True)},
    "Rwanda":           {1990: (1, True), 1995: (2, True), 2000: (1, True)},
    "Saudi Arabia":     {1990: (2, True), 1995: (1, True)},
    "South Africa":     {1975: (1, True), 1980: (2, True), 1985: (1, True), 1990: (1, True)},
    "Turkey":           {1980: (1, True), 1990: (1, True), 1995: (1, True), 2000: (1, True)},
    "Venezuela":        {2000: (0, False), 2005: (0, True)},
}


# ---------------------------------------------------------------------------
# Core data pipeline
# ---------------------------------------------------------------------------

@dataclass
class CountryYearRecord:
    country: str
    year: int
    life_expect: float
    imr: float
    regime_type: RegimeType
    neighboring_conflicts: int
    state_discrimination: bool


@dataclass
class PipelineResult:
    """Full pipeline output: raw records + model forecasts."""
    records: list[CountryYearRecord] = field(default_factory=list)
    forecasts: dict[str, list[InstabilityForecast]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)


class DataPipeline:
    """
    Orchestrates data fetching, normalization, and model scoring.

    Usage
    -----
    pipeline = DataPipeline()
    result   = pipeline.run()
    series   = result.forecasts["Colombia"]   # list of InstabilityForecast, one per year
    """

    def __init__(self, gapminder_url: str = GAPMINDER_URL, timeout: int = 15):
        self.gapminder_url = gapminder_url
        self.timeout = timeout
        self._gapminder_cache: Optional[list[dict]] = None

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def fetch_gapminder(self) -> list[dict]:
        """Fetch Gapminder life-expectancy data from GitHub."""
        if self._gapminder_cache is not None:
            return self._gapminder_cache
        logger.info("Fetching Gapminder data from %s", self.gapminder_url)
        resp = requests.get(self.gapminder_url, timeout=self.timeout)
        resp.raise_for_status()
        self._gapminder_cache = resp.json()
        logger.info("Fetched %d Gapminder records", len(self._gapminder_cache))
        return self._gapminder_cache

    # ------------------------------------------------------------------
    # Regime lookup (annotated historical data with fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def get_regime(country: str, year: int) -> RegimeType:
        """
        Look up regime type for a country-year.
        Uses the most recent annotation at or before `year`.
        Falls back to PARTIAL_AUTOCRACY if no annotation exists.
        """
        history = REGIME_HISTORY.get(country, {})
        if not history:
            return _GLOBAL_DEFAULT
        # Find latest annotated year ≤ requested year
        annotated_years = sorted(y for y in history if y <= year)
        if annotated_years:
            return history[annotated_years[-1]]
        # If all annotations are after the requested year, use the earliest
        return history[min(history.keys())]

    @staticmethod
    def get_conflict_disc(country: str, year: int) -> tuple[int, bool]:
        """Look up (neighboring_conflicts, discrimination) with nearest-prior fallback."""
        hist = CONFLICT_DISC_HISTORY.get(country, {})
        if not hist:
            return 0, False
        prior = sorted(y for y in hist if y <= year)
        if prior:
            return hist[prior[-1]]
        return 0, False

    # ------------------------------------------------------------------
    # Building records
    # ------------------------------------------------------------------

    def build_records(self, gapminder_rows: list[dict]) -> list[CountryYearRecord]:
        records = []
        for row in gapminder_rows:
            country    = row["country"]
            year       = int(row["year"])
            le         = row.get("life_expect")
            if le is None:
                continue
            imr        = life_expectancy_to_imr(le)
            regime     = self.get_regime(country, year)
            nb, disc   = self.get_conflict_disc(country, year)
            records.append(CountryYearRecord(
                country=country, year=year,
                life_expect=le, imr=imr,
                regime_type=regime,
                neighboring_conflicts=nb,
                state_discrimination=disc,
            ))
        return records

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def score_records(records: list[CountryYearRecord]) -> dict[str, list[InstabilityForecast]]:
        """Score each record and group results by country, sorted by year."""
        forecasts: dict[str, list[InstabilityForecast]] = {}
        for rec in records:
            profile = CountryProfile(
                regime_type=rec.regime_type,
                infant_mortality=rec.imr,
                neighboring_conflicts=rec.neighboring_conflicts,
                state_discrimination=rec.state_discrimination,
                country_name=rec.country,
                year=rec.year,
            )
            try:
                forecast = score(profile)
                forecasts.setdefault(rec.country, []).append(forecast)
            except Exception as e:
                logger.warning("Scoring failed for %s %d: %s", rec.country, rec.year, e)
        # Sort each country series by year
        for country in forecasts:
            forecasts[country].sort(key=lambda f: f.year or 0)
        return forecasts

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> PipelineResult:
        """Fetch data, build records, score all country-years."""
        result = PipelineResult()
        try:
            gm_rows = self.fetch_gapminder()
        except Exception as e:
            result.errors.append(f"Failed to fetch Gapminder data: {e}")
            logger.error("Pipeline fetch failed: %s", e)
            return result

        result.records   = self.build_records(gm_rows)
        result.forecasts = self.score_records(result.records)
        result.countries = sorted(result.forecasts.keys())
        all_years_set: set[int] = set()
        for series in result.forecasts.values():
            for f in series:
                if f.year:
                    all_years_set.add(f.year)
        result.years = sorted(all_years_set)
        logger.info(
            "Pipeline complete: %d countries × %d years = %d forecasts",
            len(result.countries), len(result.years),
            sum(len(v) for v in result.forecasts.values()),
        )
        return result

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def country_series(self, country: str) -> list[InstabilityForecast]:
        """Return the time series for a single country (runs full pipeline if needed)."""
        result = self.run()
        if country not in result.forecasts:
            raise KeyError(f"Country '{country}' not found. Available: {result.countries}")
        return result.forecasts[country]

    def cross_section(self, year: int) -> list[InstabilityForecast]:
        """Return all country forecasts for a single year, sorted by descending probability."""
        result = self.run()
        cross: list[InstabilityForecast] = []
        for series in result.forecasts.values():
            for f in series:
                if f.year == year:
                    cross.append(f)
        return sorted(cross, key=lambda f: f.probability, reverse=True)

    def top_risk_countries(self, year: int, n: int = 10) -> list[InstabilityForecast]:
        """Return the n highest-risk countries in a given year."""
        return self.cross_section(year)[:n]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def forecast_to_dict(f: InstabilityForecast) -> dict:
    """Convert a forecast to a JSON-serialisable dict."""
    return {
        "country":               f.country_name,
        "year":                  f.year,
        "regime_type":           f.regime_type,
        "infant_mortality":      f.infant_mortality,
        "neighboring_conflicts": f.neighboring_conflicts,
        "state_discrimination":  f.state_discrimination,
        "probability":           f.probability,
        "probability_pct":       f.probability_pct,
        "risk_band":             f.risk_band,
        "logit":                 f.logit,
        "odds_ratio_vs_stable":  f.odds_ratio_vs_stable,
        "contributions": [
            {
                "variable":       c.variable,
                "share_of_total": c.share_of_total,
                "direction":      c.direction,
            }
            for c in f.contributions
        ],
    }


def series_to_chart_data(forecasts: list[InstabilityForecast]) -> list[dict]:
    """
    Convert a country time series to a flat list suitable for charting:
    [{ year, probability_pct, risk_band, regime_type, imr, ... }, ...]
    """
    return [
        {
            "year":                  f.year,
            "probability_pct":       f.probability_pct,
            "risk_band":             f.risk_band,
            "regime_type":           f.regime_type,
            "infant_mortality":      f.infant_mortality,
            "neighboring_conflicts": f.neighboring_conflicts,
            "state_discrimination":  f.state_discrimination,
        }
        for f in forecasts
    ]