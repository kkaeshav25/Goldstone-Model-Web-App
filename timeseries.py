"""
Goldstone Model — Time Series Analysis
=======================================
Analytical layer on top of the data pipeline. Given a country's forecast
series, computes trend statistics, peak risk periods, regime-change events,
and cross-country comparisons over time.

Key functions
-------------
analyse_series(forecasts)       → TimeSeriesAnalysis for one country
compare_countries(result, ...)  → side-by-side panel for 2-N countries
global_heatmap(result, years)   → year × country probability matrix
rank_by_year(result, year)      → countries ranked by risk for a given year
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from model import InstabilityForecast
from pipeline import DataPipeline, PipelineResult, series_to_chart_data


# ---------------------------------------------------------------------------
# Per-country time-series analytics
# ---------------------------------------------------------------------------

@dataclass
class RegimeChangeEvent:
    year: int
    from_regime: str
    to_regime: str
    probability_before: float
    probability_after: float
    delta_probability: float


@dataclass
class RiskSpike:
    """A year where probability jumped sharply relative to the prior period."""
    year: int
    probability_pct: float
    delta_from_prior: float     # pp change from previous data point
    driver: str                 # variable with highest contribution share


@dataclass
class TimeSeriesAnalysis:
    country: str
    years: list[int]
    probabilities: list[float]          # 0-100
    risk_bands: list[str]
    regime_types: list[str]

    # Summary statistics
    mean_probability:   float
    max_probability:    float
    min_probability:    float
    std_dev:            float
    peak_year:          int
    trough_year:        int
    trend_slope:        float           # pp per year (OLS), + = worsening
    trend_direction:    str             # "improving" | "worsening" | "stable"

    # Events
    regime_changes:     list[RegimeChangeEvent] = field(default_factory=list)
    risk_spikes:        list[RiskSpike]          = field(default_factory=list)

    # Chart-ready series
    chart_data:         list[dict]               = field(default_factory=list)

    # Narrative
    summary:            str = ""


@dataclass
class CountryComparison:
    countries: list[str]
    years: list[int]
    series: dict[str, list[float]]          # country → list of probability_pct per year
    regime_series: dict[str, list[str]]     # country → list of regime labels per year
    analyses: dict[str, TimeSeriesAnalysis]


@dataclass
class GlobalHeatmapRow:
    country: str
    values: dict[int, float]        # year → probability_pct
    mean_probability: float
    peak_year: int
    peak_probability: float


# ---------------------------------------------------------------------------
# OLS trend slope (no external dependencies)
# ---------------------------------------------------------------------------

def _ols_slope(xs: list[float], ys: list[float]) -> float:
    """Compute the OLS slope β₁ of ys ~ β₀ + β₁ xs."""
    n = len(xs)
    if n < 2:
        return 0.0
    x_bar = sum(xs) / n
    y_bar = sum(ys) / n
    num = sum((xs[i] - x_bar) * (ys[i] - y_bar) for i in range(n))
    den = sum((xs[i] - x_bar) ** 2 for i in range(n))
    return round(num / den, 4) if den != 0 else 0.0


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyse_series(forecasts: list[InstabilityForecast]) -> TimeSeriesAnalysis:
    """
    Compute full time-series analytics for a single country's forecast series.
    `forecasts` must be sorted ascending by year.
    """
    if not forecasts:
        raise ValueError("Empty forecast series")

    country     = forecasts[0].country_name or "Unknown"
    years       = [f.year for f in forecasts]
    probs       = [f.probability_pct for f in forecasts]
    bands       = [f.risk_band for f in forecasts]
    regimes     = [f.regime_type for f in forecasts]

    mean_p  = round(statistics.mean(probs), 2)
    max_p   = max(probs)
    min_p   = min(probs)
    std_p   = round(statistics.stdev(probs) if len(probs) > 1 else 0.0, 2)
    peak_yr = years[probs.index(max_p)]
    trough_yr = years[probs.index(min_p)]

    slope     = _ols_slope([float(y) for y in years], probs)
    direction = "worsening" if slope > 0.3 else ("improving" if slope < -0.3 else "stable")

    # Regime-change events
    regime_changes: list[RegimeChangeEvent] = []
    for i in range(1, len(forecasts)):
        if forecasts[i].regime_type != forecasts[i - 1].regime_type:
            regime_changes.append(RegimeChangeEvent(
                year=forecasts[i].year,
                from_regime=forecasts[i - 1].regime_type,
                to_regime=forecasts[i].regime_type,
                probability_before=forecasts[i - 1].probability_pct,
                probability_after=forecasts[i].probability_pct,
                delta_probability=round(
                    forecasts[i].probability_pct - forecasts[i - 1].probability_pct, 2
                ),
            ))

    # Risk spikes: jumps of ≥ 10 pp from prior year
    risk_spikes: list[RiskSpike] = []
    for i in range(1, len(forecasts)):
        delta = probs[i] - probs[i - 1]
        if delta >= 10.0:
            # Find dominant driver
            top_contrib = max(
                forecasts[i].contributions,
                key=lambda c: c.share_of_total,
                default=None,
            )
            driver = top_contrib.variable if top_contrib else "Unknown"
            risk_spikes.append(RiskSpike(
                year=years[i],
                probability_pct=probs[i],
                delta_from_prior=round(delta, 2),
                driver=driver,
            ))

    # Narrative summary
    summary = _build_narrative(country, mean_p, peak_yr, max_p, direction,
                                regime_changes, risk_spikes, slope)

    return TimeSeriesAnalysis(
        country=country,
        years=years,
        probabilities=probs,
        risk_bands=bands,
        regime_types=regimes,
        mean_probability=mean_p,
        max_probability=max_p,
        min_probability=min_p,
        std_dev=std_p,
        peak_year=peak_yr,
        trough_year=trough_yr,
        trend_slope=slope,
        trend_direction=direction,
        regime_changes=regime_changes,
        risk_spikes=risk_spikes,
        chart_data=series_to_chart_data(forecasts),
        summary=summary,
    )


def _build_narrative(
    country: str,
    mean_p: float,
    peak_yr: int,
    max_p: float,
    direction: str,
    changes: list[RegimeChangeEvent],
    spikes: list[RiskSpike],
    slope: float,
) -> str:
    parts = [
        f"{country} had a mean instability probability of {mean_p:.1f}% "
        f"across the study period, peaking at {max_p:.1f}% in {peak_yr}."
    ]
    if direction == "worsening":
        parts.append(f"The overall trend was worsening (+{slope:.2f} pp/year).")
    elif direction == "improving":
        parts.append(f"The overall trend was improving ({slope:.2f} pp/year).")
    else:
        parts.append("Risk remained broadly stable over the period.")

    if changes:
        c = changes[0]
        parts.append(
            f"A notable regime transition occurred in {c.year} "
            f"({c.from_regime.replace('_', ' ')} → {c.to_regime.replace('_', ' ')}), "
            f"{'raising' if c.delta_probability > 0 else 'lowering'} risk by "
            f"{abs(c.delta_probability):.1f} pp."
        )
    if spikes:
        s = spikes[0]
        parts.append(
            f"The sharpest single-period increase was +{s.delta_from_prior:.1f} pp "
            f"in {s.year}, driven primarily by {s.driver.lower()}."
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Cross-country comparison
# ---------------------------------------------------------------------------

def compare_countries(
    result: PipelineResult,
    countries: list[str],
    years: Optional[list[int]] = None,
) -> CountryComparison:
    """
    Build a side-by-side comparison panel for the given countries.
    `years` defaults to all years available in the pipeline result.
    """
    use_years = sorted(years or result.years)
    missing   = [c for c in countries if c not in result.forecasts]
    if missing:
        raise KeyError(f"Countries not found in pipeline: {missing}. "
                       f"Available: {result.countries}")

    series:        dict[str, list[float]] = {}
    regime_series: dict[str, list[str]]   = {}
    analyses:      dict[str, TimeSeriesAnalysis] = {}

    for country in countries:
        forecasts = result.forecasts[country]
        # Build year-indexed lookup
        by_year = {f.year: f for f in forecasts}

        probs   = []
        regimes = []
        aligned: list[InstabilityForecast] = []
        for yr in use_years:
            if yr in by_year:
                f = by_year[yr]
                probs.append(f.probability_pct)
                regimes.append(f.regime_type)
                aligned.append(f)

        series[country]        = probs
        regime_series[country] = regimes
        analyses[country]      = analyse_series(aligned)

    return CountryComparison(
        countries=countries,
        years=use_years,
        series=series,
        regime_series=regime_series,
        analyses=analyses,
    )


# ---------------------------------------------------------------------------
# Global heatmap
# ---------------------------------------------------------------------------

def global_heatmap(
    result: PipelineResult,
    years: Optional[list[int]] = None,
) -> list[GlobalHeatmapRow]:
    """
    Build a year × country probability matrix, sorted by mean probability
    descending (highest-risk countries first).
    """
    use_years = sorted(years or result.years)
    rows: list[GlobalHeatmapRow] = []

    for country, forecasts in result.forecasts.items():
        by_year = {f.year: f.probability_pct for f in forecasts}
        values  = {yr: by_year.get(yr, 0.0) for yr in use_years}
        filled  = [v for v in values.values() if v > 0]
        mean_p  = round(sum(filled) / len(filled), 2) if filled else 0.0
        peak_yr = max(values, key=values.get) if values else use_years[0]
        peak_p  = values[peak_yr]
        rows.append(GlobalHeatmapRow(
            country=country,
            values=values,
            mean_probability=mean_p,
            peak_year=peak_yr,
            peak_probability=peak_p,
        ))

    rows.sort(key=lambda r: r.mean_probability, reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

def rank_by_year(result: PipelineResult, year: int) -> list[dict]:
    """
    Return all countries ranked by instability probability for a given year.
    Each entry: { rank, country, probability_pct, risk_band, regime_type }
    """
    cross = result.forecasts
    ranked = []
    for country, forecasts in cross.items():
        by_year = {f.year: f for f in forecasts}
        if year in by_year:
            f = by_year[year]
            ranked.append({
                "country":         country,
                "probability_pct": f.probability_pct,
                "risk_band":       f.risk_band,
                "regime_type":     f.regime_type,
                "infant_mortality": f.infant_mortality,
            })
    ranked.sort(key=lambda x: x["probability_pct"], reverse=True)
    for i, row in enumerate(ranked):
        row["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# Convenience: run everything from scratch
# ---------------------------------------------------------------------------

def run_full_analysis(countries: Optional[list[str]] = None) -> dict:
    """
    Run the full pipeline and return a ready-to-serve dict with:
      - per-country time series analyses
      - global heatmap
      - rankings for each available year
    """
    pipeline = DataPipeline()
    result   = pipeline.run()

    target_countries = countries or result.countries
    available        = [c for c in target_countries if c in result.forecasts]

    analyses  = {c: analyse_series(result.forecasts[c]) for c in available}
    heatmap   = global_heatmap(result)
    rankings  = {yr: rank_by_year(result, yr) for yr in result.years}

    return {
        "countries":  available,
        "years":      result.years,
        "analyses":   analyses,
        "heatmap":    heatmap,
        "rankings":   rankings,
        "errors":     result.errors,
    }