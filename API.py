"""
Goldstone Political Instability Model — REST API
=================================================
FastAPI application exposing the PITF model as a REST service.

Endpoints
---------
POST /forecast             — Score a single country profile
POST /forecast/batch       — Score multiple profiles in one call
POST /forecast/polity      — Score using raw Polity IV score
POST /sensitivity          — One-at-a-time sensitivity analysis
POST /compare              — Side-by-side comparison of 2-10 profiles
GET  /regime-types         — Metadata on the five regime categories
GET  /risk-bands           — Risk band thresholds and labels
GET  /health               — Service liveness check

-- Pipeline / time-series endpoints --
GET  /pipeline/countries              — List all available countries
GET  /pipeline/years                  — List all available years
GET  /pipeline/series/{country}       — Full time-series analysis for one country
GET  /pipeline/compare                — Compare multiple countries over time
GET  /pipeline/rankings/{year}        — All countries ranked by risk in a year
GET  /pipeline/heatmap                — Global risk heatmap (all countries × years)
GET  /pipeline/top/{year}             — Top N highest-risk countries in a year

Usage
-----
  uvicorn api:app --reload --port 8000
  # then visit http://localhost:8000/docs
"""

from __future__ import annotations

from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from model import (
    CountryProfile,
    RegimeType,
    InstabilityForecast,
    SensitivityResult,
    score,
    score_batch,
    sensitivity_analysis,
    polity_to_regime,
    RISK_BANDS,
)

from pipeline import DataPipeline, forecast_to_dict, series_to_chart_data
from timeseries import analyse_series, compare_countries, global_heatmap, rank_by_year
from present_day import fetch_present_day

# Pipeline singleton — built once, reused across requests
_pipeline_result = None

def _get_result():
    global _pipeline_result
    if _pipeline_result is None:
        _pipeline_result = DataPipeline().run()
    return _pipeline_result



# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Goldstone Political Instability Forecasting API",
    description=(
        "REST interface for the PITF model from Goldstone et al. (2010) "
        "'A Global Model for Forecasting Political Instability', "
        "American Journal of Political Science 54(1): 190-208."
    ),
    version="1.0.0",
    contact={"name": "PITF Reference Model"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic I/O schemas
# ---------------------------------------------------------------------------

class ForecastRequest(BaseModel):
    regime_type: RegimeType = Field(
        ...,
        description="Five-category Polity-derived regime classification.",
        examples=["factionalized_democracy"],
    )
    infant_mortality: float = Field(
        ..., ge=1, le=300,
        description="Infant deaths per 1,000 live births. Range: 1–300.",
        examples=[55.0],
    )
    neighboring_conflicts: int = Field(
        ..., ge=0, le=10,
        description="Number of bordering states with active armed conflict.",
        examples=[2],
    )
    state_discrimination: bool = Field(
        ...,
        description="Active state-led political discrimination against an ethnic/political group.",
        examples=[True],
    )
    country_name: Optional[str] = Field(None, description="Optional label.", examples=["Country X"])
    year: Optional[int] = Field(None, description="Optional year label.", examples=[2024])

    model_config = {"json_schema_extra": {
        "example": {
            "regime_type": "factionalized_democracy",
            "infant_mortality": 55.0,
            "neighboring_conflicts": 2,
            "state_discrimination": True,
            "country_name": "Country X",
            "year": 2024,
        }
    }}


class PolityRequest(BaseModel):
    """Alternative input using a raw Polity IV score."""
    polity_score: int = Field(..., ge=-10, le=10, description="Raw Polity IV score (−10 to +10).")
    factional: bool = Field(False, description="Is the regime characterised by elite factionalism?")
    infant_mortality: float = Field(..., ge=1, le=300)
    neighboring_conflicts: int = Field(..., ge=0, le=10)
    state_discrimination: bool
    country_name: Optional[str] = None
    year: Optional[int] = None


class BatchForecastRequest(BaseModel):
    profiles: list[ForecastRequest] = Field(..., min_length=1, max_length=200)


class ContributionOut(BaseModel):
    variable: str
    raw_beta: float
    share_of_total: float
    direction: str


class ForecastResponse(BaseModel):
    country_name:           Optional[str]
    year:                   Optional[int]
    regime_type:            str
    infant_mortality:       float
    neighboring_conflicts:  int
    state_discrimination:   bool
    logit:                  float
    probability:            float
    probability_pct:        float
    risk_band:              str
    risk_band_threshold:    float
    contributions:          list[ContributionOut]
    odds_ratio_vs_stable:   float
    interpretation:         str


class SensitivityOut(BaseModel):
    variable:    str
    low_value:   str
    high_value:  str
    prob_low:    float
    prob_high:   float
    delta_prob:  float
    elasticity:  float


class RegimeTypeInfo(BaseModel):
    value:        str
    label:        str
    description:  str
    polity_range: str
    typical_beta: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interpretation(forecast: InstabilityForecast) -> str:
    top_driver = max(forecast.contributions, key=lambda c: c.share_of_total, default=None)
    driver_str = f" The dominant risk driver is **{top_driver.variable}** ({top_driver.share_of_total*100:.0f}% of signal)." if top_driver else ""
    return (
        f"{forecast.risk_band} risk of political instability onset within two years "
        f"(P = {forecast.probability_pct}%).{driver_str} "
        f"Odds are {forecast.odds_ratio_vs_stable}× higher than the safest reference profile."
    )


def _to_response(forecast: InstabilityForecast) -> ForecastResponse:
    return ForecastResponse(
        country_name=forecast.country_name,
        year=forecast.year,
        regime_type=forecast.regime_type,
        infant_mortality=forecast.infant_mortality,
        neighboring_conflicts=forecast.neighboring_conflicts,
        state_discrimination=forecast.state_discrimination,
        logit=forecast.logit,
        probability=forecast.probability,
        probability_pct=forecast.probability_pct,
        risk_band=forecast.risk_band,
        risk_band_threshold=forecast.risk_band_threshold,
        contributions=[
            ContributionOut(
                variable=c.variable,
                raw_beta=c.raw_beta,
                share_of_total=c.share_of_total,
                direction=c.direction,
            )
            for c in forecast.contributions
        ],
        odds_ratio_vs_stable=forecast.odds_ratio_vs_stable,
        interpretation=_interpretation(forecast),
    )


def _request_to_profile(req: ForecastRequest) -> CountryProfile:
    return CountryProfile(
        regime_type=req.regime_type,
        infant_mortality=req.infant_mortality,
        neighboring_conflicts=req.neighboring_conflicts,
        state_discrimination=req.state_discrimination,
        country_name=req.country_name,
        year=req.year,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "model": "Goldstone et al. 2010", "version": "1.0.0"}


@app.get("/regime-types", response_model=list[RegimeTypeInfo], tags=["reference"])
def regime_types():
    """Return metadata for all five regime categories."""
    from model import _REGIME_BETAS
    return [
        RegimeTypeInfo(
            value=r.value,
            label=r.label,
            description=r.description,
            polity_range=r.polity_range,
            typical_beta=round(_REGIME_BETAS[r], 3),
        )
        for r in RegimeType
    ]


@app.get("/risk-bands", tags=["reference"])
def risk_bands():
    """Return the probability thresholds and labels for each risk band."""
    return [
        {"band": band, "upper_threshold": threshold, "note": note}
        for threshold, band, note in RISK_BANDS
    ]


@app.post("/forecast", response_model=ForecastResponse, tags=["forecast"])
def forecast(req: ForecastRequest):
    """
    Score a single country-year profile and return the instability probability,
    risk band, per-variable contributions, and a plain-English interpretation.
    """
    try:
        profile  = _request_to_profile(req)
        result   = score(profile)
        return _to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/forecast/polity", response_model=ForecastResponse, tags=["forecast"])
def forecast_from_polity(req: PolityRequest):
    """
    Score using a raw Polity IV score rather than the categorical regime label.
    The `factional` flag distinguishes factionalized regimes in the −5 to +5 band.
    """
    regime = polity_to_regime(req.polity_score, req.factional)
    profile = CountryProfile(
        regime_type=regime,
        infant_mortality=req.infant_mortality,
        neighboring_conflicts=req.neighboring_conflicts,
        state_discrimination=req.state_discrimination,
        country_name=req.country_name,
        year=req.year,
    )
    result = score(profile)
    return _to_response(result)


@app.post("/forecast/batch", response_model=list[ForecastResponse], tags=["forecast"])
def forecast_batch(req: BatchForecastRequest):
    """
    Score up to 200 profiles in a single call. Useful for time-series or
    cross-country comparisons. Profiles are processed in order; any validation
    error aborts the entire batch.
    """
    try:
        profiles = [_request_to_profile(r) for r in req.profiles]
        results  = score_batch(profiles)
        return [_to_response(r) for r in results]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/sensitivity", response_model=list[SensitivityOut], tags=["analysis"])
def sensitivity(req: ForecastRequest):
    """
    One-at-a-time sensitivity analysis: vary each variable across its plausible
    range while holding others fixed. Returns results ranked by absolute impact
    (largest Δ probability first).
    """
    try:
        profile = _request_to_profile(req)
        results = sensitivity_analysis(profile)
        return [
            SensitivityOut(
                variable=r.variable,
                low_value=str(r.low_value),
                high_value=str(r.high_value),
                prob_low=r.prob_low,
                prob_high=r.prob_high,
                delta_prob=r.delta_prob,
                elasticity=r.elasticity,
            )
            for r in results
        ]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/compare", tags=["analysis"])
def compare(profiles: list[ForecastRequest]):
    """
    Compare 2–10 profiles side-by-side. Returns forecasts sorted by
    descending instability probability.
    """
    if not (2 <= len(profiles) <= 10):
        raise HTTPException(status_code=422, detail="Provide 2–10 profiles for comparison.")
    try:
        results = [_to_response(score(_request_to_profile(p))) for p in profiles]
        results.sort(key=lambda r: r.probability, reverse=True)
        return results
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ===========================================================================
# Pipeline & time-series endpoints
# ===========================================================================

@app.get("/pipeline/countries", tags=["pipeline"])
def pipeline_countries():
    """List all countries available in the historical dataset."""
    r = _get_result()
    return {"countries": r.countries, "count": len(r.countries)}


@app.get("/pipeline/years", tags=["pipeline"])
def pipeline_years():
    """List all years covered by the pipeline."""
    r = _get_result()
    return {"years": r.years}


@app.get("/pipeline/series/{country}", tags=["pipeline"])
def pipeline_series(country: str):
    """
    Return a full time-series analysis for one country: trend, peak risk,
    regime-change events, risk spikes, and chart-ready data.
    Country names are case-sensitive (e.g. 'Colombia', 'South Korea').
    """
    r = _get_result()
    if country not in r.forecasts:
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found. Use GET /pipeline/countries for the list.",
        )
    analysis = analyse_series(r.forecasts[country])
    return {
        "country":          analysis.country,
        "years":            analysis.years,
        "probabilities":    analysis.probabilities,
        "risk_bands":       analysis.risk_bands,
        "regime_types":     analysis.regime_types,
        "mean_probability": analysis.mean_probability,
        "max_probability":  analysis.max_probability,
        "min_probability":  analysis.min_probability,
        "std_dev":          analysis.std_dev,
        "peak_year":        analysis.peak_year,
        "trough_year":      analysis.trough_year,
        "trend_slope":      analysis.trend_slope,
        "trend_direction":  analysis.trend_direction,
        "regime_changes": [
            {
                "year":                 rc.year,
                "from_regime":          rc.from_regime,
                "to_regime":            rc.to_regime,
                "probability_before":   rc.probability_before,
                "probability_after":    rc.probability_after,
                "delta_probability":    rc.delta_probability,
            }
            for rc in analysis.regime_changes
        ],
        "risk_spikes": [
            {
                "year":             s.year,
                "probability_pct":  s.probability_pct,
                "delta_from_prior": s.delta_from_prior,
                "driver":           s.driver,
            }
            for s in analysis.risk_spikes
        ],
        "chart_data": analysis.chart_data,
        "summary":    analysis.summary,
    }


@app.get("/pipeline/compare", tags=["pipeline"])
def pipeline_compare(countries: str, years: Optional[str] = None):
    """
    Compare multiple countries over time.
    Pass `countries` as a comma-separated string: ?countries=Colombia,Chile,Peru
    Optionally filter years: ?years=1980,1985,1990
    """
    country_list = [c.strip() for c in countries.split(",") if c.strip()]
    year_list    = (
        [int(y.strip()) for y in years.split(",") if y.strip()]
        if years else None
    )
    if len(country_list) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 countries.")
    r = _get_result()
    try:
        comp = compare_countries(r, country_list, year_list)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "countries": comp.countries,
        "years":     comp.years,
        "series":    comp.series,
        "regime_series": comp.regime_series,
        "analyses": {
            c: {
                "mean_probability": comp.analyses[c].mean_probability,
                "peak_year":        comp.analyses[c].peak_year,
                "max_probability":  comp.analyses[c].max_probability,
                "trend_direction":  comp.analyses[c].trend_direction,
                "trend_slope":      comp.analyses[c].trend_slope,
                "summary":          comp.analyses[c].summary,
            }
            for c in comp.countries
        },
        "chart_data": [
            {
                "year":  yr,
                **{c: comp.series[c][i] for i, c in enumerate(comp.countries) if i < len(comp.series[c])}
            }
            for i, yr in enumerate(comp.years)
        ],
    }


@app.get("/pipeline/rankings/{year}", tags=["pipeline"])
def pipeline_rankings(year: int):
    """
    All countries ranked by instability probability for a given year.
    Available years: 1955, 1960, 1965, 1970, 1975, 1980, 1985, 1990, 1995, 2000, 2005.
    """
    r = _get_result()
    if year not in r.years:
        raise HTTPException(
            status_code=404,
            detail=f"Year {year} not available. Use GET /pipeline/years for options.",
        )
    return {"year": year, "rankings": rank_by_year(r, year)}


@app.get("/pipeline/top/{year}", tags=["pipeline"])
def pipeline_top(year: int, n: int = 10):
    """Top N highest-risk countries in a given year (default n=10, max 30)."""
    r = _get_result()
    if year not in r.years:
        raise HTTPException(status_code=404, detail=f"Year {year} not in dataset.")
    n = min(max(n, 1), 30)
    return {"year": year, "top": rank_by_year(r, year)[:n]}


@app.get("/pipeline/heatmap", tags=["pipeline"])
def pipeline_heatmap(years: Optional[str] = None):
    """
    Global risk heatmap — all countries × years, sorted by mean risk.
    Optionally filter: ?years=1980,1990,2000
    """
    r      = _get_result()
    y_list = (
        [int(y.strip()) for y in years.split(",") if y.strip()]
        if years else None
    )
    rows = global_heatmap(r, y_list)
    return {
        "years": y_list or r.years,
        "rows": [
            {
                "country":          row.country,
                "values":           {str(k): v for k, v in row.values.items()},
                "mean_probability": row.mean_probability,
                "peak_year":        row.peak_year,
                "peak_probability": row.peak_probability,
            }
            for row in rows
        ],
    }


# ===========================================================================
# Present-day integration (2007 & 2024)
# ===========================================================================

@app.get("/present-day", tags=["present-day"])
def present_day_forecasts():
    """
    Fetch and score present-day profiles for 2007 (from Jenny gapminder data)
    and 2024 (hand-coded). Returns forecasts grouped by country and year.
    """
    try:
        pipeline_countries = _get_result().countries
        result = fetch_present_day(pipeline_countries)
        
        return {
            "forecasts_2007": {
                country: _to_response(forecast) if hasattr(forecast, 'probability') else forecast
                for country, forecast in result.forecasts_2007.items()
            },
            "forecasts_2024": {
                country: _to_response(forecast) if hasattr(forecast, 'probability') else forecast
                for country, forecast in result.forecasts_2024.items()
            },
            "errors": result.errors,
            "summary": {
                "countries_2007": len(result.forecasts_2007),
                "countries_2024": len(result.forecasts_2024),
                "errors_count": len(result.errors),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch present-day data: {str(e)}")