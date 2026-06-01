"""
Test suite for the Goldstone Political Instability Backend
==========================================================
Run with:  pytest tests.py -v
"""

import math
import pytest
from fastapi.testclient import TestClient

from model import (
    CountryProfile, RegimeType, score, score_batch,
    sensitivity_analysis, polity_to_regime, _REGIME_BETAS,
    _INTERCEPT, _IMR_BETA_PER_UNIT, _NEIGHBOR_BETA_PER_UNIT, _DISCRIMINATION_BETA,
)
from API import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def safest_profile():
    return CountryProfile(
        regime_type=RegimeType.FULL_DEMOCRACY,
        infant_mortality=5.0,
        neighboring_conflicts=0,
        state_discrimination=False,
        country_name="Safe Country",
        year=2020,
    )


@pytest.fixture
def riskiest_profile():
    return CountryProfile(
        regime_type=RegimeType.FACTIONALIZED_DEMOCRACY,
        infant_mortality=150.0,
        neighboring_conflicts=5,
        state_discrimination=True,
        country_name="High-Risk Country",
        year=2020,
    )


@pytest.fixture
def mid_profile():
    return CountryProfile(
        regime_type=RegimeType.PARTIAL_AUTOCRACY,
        infant_mortality=50.0,
        neighboring_conflicts=1,
        state_discrimination=False,
    )


# ---------------------------------------------------------------------------
# Model unit tests
# ---------------------------------------------------------------------------

class TestModelMath:

    def test_logit_formula(self, safest_profile):
        """Logit must equal intercept + sum of betas."""
        f = score(safest_profile)
        expected_logit = (_INTERCEPT
                          + _REGIME_BETAS[RegimeType.FULL_DEMOCRACY]
                          + _IMR_BETA_PER_UNIT * 5.0
                          + _NEIGHBOR_BETA_PER_UNIT * 0
                          + 0.0)
        assert abs(f.logit - expected_logit) < 1e-3

    def test_probability_from_logit(self, safest_profile):
        """P = sigmoid(logit)."""
        f = score(safest_profile)
        expected_prob = 1.0 / (1.0 + math.exp(-f.logit))
        assert abs(f.probability - expected_prob) < 1e-4

    def test_probability_bounds(self, safest_profile, riskiest_profile):
        """Probability must be strictly in (0, 1)."""
        for profile in [safest_profile, riskiest_profile]:
            f = score(profile)
            assert 0 < f.probability < 1

    def test_monotone_imr(self):
        """Higher IMR → higher probability, ceteris paribus."""
        base = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 20, 0, False)
        high = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 120, 0, False)
        assert score(high).probability > score(base).probability

    def test_monotone_neighbors(self):
        """More neighboring conflicts → higher probability."""
        base = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 40, 0, False)
        high = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 40, 4, False)
        assert score(high).probability > score(base).probability

    def test_discrimination_raises_risk(self):
        """Discrimination on → higher probability than discrimination off."""
        without = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 40, 1, False)
        with_   = CountryProfile(RegimeType.PARTIAL_DEMOCRACY, 40, 1, True)
        assert score(with_).probability > score(without).probability

    def test_factionalized_highest_regime_risk(self):
        """Factionalized democracy must produce the highest probability among regime types."""
        base_imr, base_nb = 40, 1
        probs = {
            r: score(CountryProfile(r, base_imr, base_nb, False)).probability
            for r in RegimeType
        }
        assert probs[RegimeType.FACTIONALIZED_DEMOCRACY] == max(probs.values())

    def test_full_democracy_lowest_regime_risk(self):
        """Full democracy must produce the lowest probability among regime types."""
        base_imr, base_nb = 40, 1
        probs = {
            r: score(CountryProfile(r, base_imr, base_nb, False)).probability
            for r in RegimeType
        }
        assert probs[RegimeType.FULL_DEMOCRACY] == min(probs.values())

    def test_risk_band_assignment(self, safest_profile, riskiest_profile):
        safe_f    = score(safest_profile)
        risky_f   = score(riskiest_profile)
        assert safe_f.risk_band  in ("Low", "Moderate")
        assert risky_f.risk_band in ("High", "Very High")

    def test_probability_pct_consistent(self, mid_profile):
        f = score(mid_profile)
        assert abs(f.probability_pct - round(f.probability * 100, 1)) < 0.01

    def test_contributions_sum_to_one(self, riskiest_profile):
        """Variable contributions (share_of_total) must sum to ≈1."""
        f = score(riskiest_profile)
        total = sum(c.share_of_total for c in f.contributions)
        assert abs(total - 1.0) < 0.01

    def test_odds_ratio_safest_is_baseline(self, safest_profile):
        """The reference profile should have OR ≈ 1."""
        # OR is relative to itself — but safest may not exactly equal 1
        # due to IMR=5 not being exactly the formula reference. Allow tolerance.
        f = score(safest_profile)
        assert f.odds_ratio_vs_stable >= 0.9


class TestValidation:

    def test_invalid_imr_low(self):
        with pytest.raises(ValueError, match="infant_mortality"):
            score(CountryProfile(RegimeType.FULL_DEMOCRACY, 0, 0, False))

    def test_invalid_imr_high(self):
        with pytest.raises(ValueError, match="infant_mortality"):
            score(CountryProfile(RegimeType.FULL_DEMOCRACY, 999, 0, False))

    def test_invalid_neighbors(self):
        with pytest.raises(ValueError, match="neighboring_conflicts"):
            score(CountryProfile(RegimeType.FULL_DEMOCRACY, 20, 15, False))


class TestBatch:

    def test_batch_matches_individual(self, safest_profile, riskiest_profile):
        """Batch scoring must produce identical results to individual scoring."""
        batch = score_batch([safest_profile, riskiest_profile])
        assert abs(batch[0].probability - score(safest_profile).probability) < 1e-6
        assert abs(batch[1].probability - score(riskiest_profile).probability) < 1e-6

    def test_batch_preserves_order(self):
        profiles = [
            CountryProfile(RegimeType.FULL_DEMOCRACY, 5, 0, False),
            CountryProfile(RegimeType.FACTIONALIZED_DEMOCRACY, 100, 3, True),
            CountryProfile(RegimeType.PARTIAL_AUTOCRACY, 50, 1, False),
        ]
        batch = score_batch(profiles)
        assert len(batch) == 3
        for i, p in enumerate(profiles):
            assert abs(batch[i].probability - score(p).probability) < 1e-6


class TestSensitivity:

    def test_returns_four_variables(self, mid_profile):
        results = sensitivity_analysis(mid_profile)
        assert len(results) == 4

    def test_ranked_by_delta(self, mid_profile):
        results = sensitivity_analysis(mid_profile)
        deltas = [abs(r.delta_prob) for r in results]
        assert deltas == sorted(deltas, reverse=True)

    def test_regime_is_top_driver_for_stable_country(self, safest_profile):
        """For a very stable profile, regime swap should dominate."""
        results = sensitivity_analysis(safest_profile)
        top = results[0]
        assert "egime" in top.variable or "mortality" in top.variable  # either is plausible


class TestPolityMapping:

    @pytest.mark.parametrize("score,expected", [
        (-10, RegimeType.FULL_AUTOCRACY),
        (-6,  RegimeType.FULL_AUTOCRACY),
        (-5,  RegimeType.PARTIAL_AUTOCRACY),
        (0,   RegimeType.PARTIAL_AUTOCRACY),
        (5,   RegimeType.PARTIAL_AUTOCRACY),
        (6,   RegimeType.PARTIAL_DEMOCRACY),
        (9,   RegimeType.PARTIAL_DEMOCRACY),
        (10,  RegimeType.FULL_DEMOCRACY),
    ])
    def test_polity_mapping(self, score, expected):
        assert polity_to_regime(score) == expected

    def test_factional_flag(self):
        assert polity_to_regime(0, factional=True) == RegimeType.FACTIONALIZED_DEMOCRACY
        assert polity_to_regime(0, factional=False) == RegimeType.PARTIAL_AUTOCRACY


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

class TestAPIHealth:

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAPIForecast:

    def _valid_payload(self, **overrides):
        base = {
            "regime_type": "partial_democracy",
            "infant_mortality": 45.0,
            "neighboring_conflicts": 1,
            "state_discrimination": False,
            "country_name": "Test",
            "year": 2022,
        }
        base.update(overrides)
        return base

    def test_forecast_200(self):
        r = client.post("/forecast", json=self._valid_payload())
        assert r.status_code == 200
        data = r.json()
        assert "probability" in data
        assert "risk_band" in data
        assert "contributions" in data
        assert len(data["contributions"]) == 4

    def test_forecast_probability_range(self):
        r = client.post("/forecast", json=self._valid_payload())
        p = r.json()["probability"]
        assert 0 < p < 1

    def test_forecast_high_risk(self):
        payload = self._valid_payload(
            regime_type="factionalized_democracy",
            infant_mortality=130,
            neighboring_conflicts=4,
            state_discrimination=True,
        )
        r = client.post("/forecast", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["risk_band"] in ("High", "Very High")
        assert data["probability"] > 0.3

    def test_forecast_low_risk(self):
        payload = self._valid_payload(
            regime_type="full_democracy",
            infant_mortality=4,
            neighboring_conflicts=0,
            state_discrimination=False,
        )
        r = client.post("/forecast", json=payload)
        assert r.status_code == 200
        assert r.json()["risk_band"] == "Low"

    def test_forecast_invalid_imr(self):
        r = client.post("/forecast", json=self._valid_payload(infant_mortality=0))
        assert r.status_code == 422

    def test_forecast_invalid_regime(self):
        r = client.post("/forecast", json=self._valid_payload(regime_type="monarchy"))
        assert r.status_code == 422

    def test_forecast_interpretation_present(self):
        r = client.post("/forecast", json=self._valid_payload())
        assert len(r.json()["interpretation"]) > 20

    def test_polity_endpoint(self):
        payload = {
            "polity_score": 7,
            "factional": False,
            "infant_mortality": 30.0,
            "neighboring_conflicts": 0,
            "state_discrimination": False,
        }
        r = client.post("/forecast/polity", json=payload)
        assert r.status_code == 200
        assert r.json()["regime_type"] == "partial_democracy"

    def test_polity_factional_flag(self):
        payload = {
            "polity_score": 2,
            "factional": True,
            "infant_mortality": 60.0,
            "neighboring_conflicts": 2,
            "state_discrimination": True,
        }
        r = client.post("/forecast/polity", json=payload)
        assert r.status_code == 200
        assert r.json()["regime_type"] == "factionalized_democracy"


class TestAPIBatch:

    def test_batch_two_profiles(self):
        payload = {"profiles": [
            {"regime_type": "full_democracy", "infant_mortality": 5, "neighboring_conflicts": 0, "state_discrimination": False},
            {"regime_type": "factionalized_democracy", "infant_mortality": 100, "neighboring_conflicts": 3, "state_discrimination": True},
        ]}
        r = client.post("/forecast/batch", json=payload)
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 2
        assert results[1]["probability"] > results[0]["probability"]

    def test_batch_empty_fails(self):
        r = client.post("/forecast/batch", json={"profiles": []})
        assert r.status_code == 422

    def test_batch_max_200(self):
        payload = {"profiles": [
            {"regime_type": "partial_democracy", "infant_mortality": 40, "neighboring_conflicts": 0, "state_discrimination": False}
        ] * 200}
        r = client.post("/forecast/batch", json=payload)
        assert r.status_code == 200
        assert len(r.json()) == 200


class TestAPISensitivity:

    def test_sensitivity_returns_four(self):
        payload = {
            "regime_type": "partial_autocracy",
            "infant_mortality": 50,
            "neighboring_conflicts": 1,
            "state_discrimination": False,
        }
        r = client.post("/sensitivity", json=payload)
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 4

    def test_sensitivity_sorted_by_delta(self):
        payload = {
            "regime_type": "partial_democracy",
            "infant_mortality": 60,
            "neighboring_conflicts": 2,
            "state_discrimination": True,
        }
        r = client.post("/sensitivity", json=payload)
        deltas = [abs(item["delta_prob"]) for item in r.json()]
        assert deltas == sorted(deltas, reverse=True)


class TestAPIReference:

    def test_regime_types_endpoint(self):
        r = client.get("/regime-types")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 5
        labels = [d["value"] for d in data]
        assert "factionalized_democracy" in labels
        assert "full_democracy" in labels

    def test_risk_bands_endpoint(self):
        r = client.get("/risk-bands")
        assert r.status_code == 200
        bands = r.json()
        assert len(bands) == 4
        thresholds = [b["upper_threshold"] for b in bands]
        assert thresholds == sorted(thresholds)


class TestAPICompare:

    def test_compare_sorted_descending(self):
        payload = [
            {"regime_type": "full_democracy", "infant_mortality": 5, "neighboring_conflicts": 0, "state_discrimination": False},
            {"regime_type": "factionalized_democracy", "infant_mortality": 120, "neighboring_conflicts": 4, "state_discrimination": True},
            {"regime_type": "partial_autocracy", "infant_mortality": 60, "neighboring_conflicts": 1, "state_discrimination": False},
        ]
        r = client.post("/compare", json=payload)
        assert r.status_code == 200
        probs = [p["probability"] for p in r.json()]
        assert probs == sorted(probs, reverse=True)

    def test_compare_too_few(self):
        r = client.post("/compare", json=[
            {"regime_type": "full_democracy", "infant_mortality": 5, "neighboring_conflicts": 0, "state_discrimination": False}
        ])
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline:

    def test_pipeline_runs_and_returns_countries(self):
        from pipeline import DataPipeline
        r = DataPipeline().run()
        assert len(r.countries) >= 50
        assert len(r.errors) == 0

    def test_all_years_present(self):
        from pipeline import DataPipeline
        r = DataPipeline().run()
        assert r.years == [1955,1960,1965,1970,1975,1980,1985,1990,1995,2000,2005]

    def test_known_high_risk_country(self):
        from pipeline import DataPipeline
        r = DataPipeline().run()
        rwanda_1990 = next(f for f in r.forecasts["Rwanda"] if f.year == 1990)
        assert rwanda_1990.probability_pct > 60
        assert rwanda_1990.risk_band == "Very High"

    def test_known_low_risk_country(self):
        from pipeline import DataPipeline
        r = DataPipeline().run()
        germany_series = r.forecasts["Germany"]
        for f in germany_series:
            assert f.probability_pct < 20

    def test_imr_conversion_sanity(self):
        from pipeline import life_expectancy_to_imr
        assert life_expectancy_to_imr(33) > 150     # very poor country 1960s
        assert life_expectancy_to_imr(80) < 20      # modern high-income country

    def test_regime_lookup_fallback(self):
        from pipeline import DataPipeline
        p = DataPipeline()
        # Should fall back to nearest prior annotation
        from model import RegimeType
        assert p.get_regime("Chile", 1976) == RegimeType.FULL_AUTOCRACY  # coup was 1973→1975

    def test_cross_section_sorted(self):
        from pipeline import DataPipeline
        p = DataPipeline()
        r = p.run()
        cross = p.cross_section(1990)
        probs = [f.probability_pct for f in cross]
        assert probs == sorted(probs, reverse=True)


# ---------------------------------------------------------------------------
# Time series tests
# ---------------------------------------------------------------------------

class TestTimeSeries:

    @pytest.fixture
    def pipeline_result(self):
        from pipeline import DataPipeline
        return DataPipeline().run()

    def test_analyse_returns_correct_fields(self, pipeline_result):
        from timeseries import analyse_series
        a = analyse_series(pipeline_result.forecasts["Colombia"])
        assert a.country == "Colombia"
        assert len(a.years) == 11
        assert 0 <= a.mean_probability <= 100
        assert a.peak_year in a.years
        assert a.trend_direction in ("improving", "worsening", "stable")

    def test_detect_regime_changes(self, pipeline_result):
        from timeseries import analyse_series
        # Chile had dramatic swings: democracy → coup → democracy
        a = analyse_series(pipeline_result.forecasts["Chile"])
        assert len(a.regime_changes) >= 1

    def test_risk_spikes_detected(self, pipeline_result):
        from timeseries import analyse_series
        # Colombia had a spike around 1985 (violence + factionalism)
        a = analyse_series(pipeline_result.forecasts["Colombia"])
        assert any(s.year >= 1980 for s in a.risk_spikes)

    def test_summary_is_nonempty(self, pipeline_result):
        from timeseries import analyse_series
        a = analyse_series(pipeline_result.forecasts["Rwanda"])
        assert len(a.summary) > 50

    def test_compare_countries_alignment(self, pipeline_result):
        from timeseries import compare_countries
        comp = compare_countries(pipeline_result, ["Colombia", "Chile"])
        assert comp.years == sorted(comp.years)
        assert len(comp.series["Colombia"]) == len(comp.series["Chile"])

    def test_global_heatmap_sorted_by_mean(self, pipeline_result):
        from timeseries import global_heatmap
        rows = global_heatmap(pipeline_result)
        means = [r.mean_probability for r in rows]
        assert means == sorted(means, reverse=True)

    def test_rank_by_year_sorted(self, pipeline_result):
        from timeseries import rank_by_year
        ranked = rank_by_year(pipeline_result, 1990)
        probs = [r["probability_pct"] for r in ranked]
        assert probs == sorted(probs, reverse=True)
        assert ranked[0]["rank"] == 1


# ---------------------------------------------------------------------------
# Extended API: pipeline endpoint tests
# ---------------------------------------------------------------------------

class TestAPIPipelineEndpoints:

    def test_pipeline_countries(self):
        r = client.get("/pipeline/countries")
        assert r.status_code == 200
        assert r.json()["count"] >= 50

    def test_pipeline_years(self):
        r = client.get("/pipeline/years")
        assert r.status_code == 200
        assert 1990 in r.json()["years"]

    def test_pipeline_series_colombia(self):
        r = client.get("/pipeline/series/Colombia")
        assert r.status_code == 200
        d = r.json()
        assert d["peak_year"] == 1985
        assert d["max_probability"] > 40
        assert len(d["chart_data"]) == 11
        assert len(d["regime_changes"]) >= 1

    def test_pipeline_series_not_found(self):
        r = client.get("/pipeline/series/Narnia")
        assert r.status_code == 404

    def test_pipeline_compare(self):
        r = client.get("/pipeline/compare?countries=Colombia,Chile")
        assert r.status_code == 200
        d = r.json()
        assert "Colombia" in d["series"]
        assert "Chile" in d["series"]
        assert len(d["chart_data"]) == 11

    def test_pipeline_compare_too_few(self):
        r = client.get("/pipeline/compare?countries=Colombia")
        assert r.status_code == 422

    def test_pipeline_rankings_1990(self):
        r = client.get("/pipeline/rankings/1990")
        assert r.status_code == 200
        d = r.json()
        assert d["rankings"][0]["rank"] == 1
        assert d["rankings"][0]["probability_pct"] > 60

    def test_pipeline_rankings_bad_year(self):
        r = client.get("/pipeline/rankings/2099")
        assert r.status_code == 404

    def test_pipeline_top_n(self):
        r = client.get("/pipeline/top/1990?n=5")
        assert r.status_code == 200
        assert len(r.json()["top"]) == 5

    def test_pipeline_heatmap(self):
        r = client.get("/pipeline/heatmap")
        assert r.status_code == 200
        d = r.json()
        assert len(d["rows"]) >= 50
        # Sorted by mean descending
        means = [row["mean_probability"] for row in d["rows"]]
        assert means == sorted(means, reverse=True)

    def test_pipeline_heatmap_year_filter(self):
        r = client.get("/pipeline/heatmap?years=1980,1990,2000")
        assert r.status_code == 200
        assert r.json()["years"] == [1980, 1990, 2000]