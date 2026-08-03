"""Tests de propiedades — RebalancingEngine."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from benchmark.engines.rebalancing import PrimaryDataMetrics, RebalancingEngine


@pytest.fixture
def engine():
    return RebalancingEngine()


def test_zero_data_gives_zero_primary(engine):
    m = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=0, n_target=50,
        quality_score=0.0, representativeness=0.0,
        recency_score=0.0, stability_score=0.0,
    )
    w = engine.calculate_weights(m)
    assert w.primary_weight == 0.0
    assert w.public_weight == 1.0


def test_weights_sum_to_one(engine):
    m = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=30, n_target=50,
        quality_score=0.8, representativeness=0.7,
        recency_score=0.9, stability_score=0.85,
    )
    w = engine.calculate_weights(m)
    assert abs(w.primary_weight + w.public_weight - 1.0) < 1e-5


def test_full_data_gives_high_primary(engine):
    m = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=100, n_target=50,
        quality_score=1.0, representativeness=1.0,
        recency_score=1.0, stability_score=1.0,
    )
    w = engine.calculate_weights(m)
    assert w.primary_weight > 0.8


def test_weak_factor_penalizes_weight(engine):
    good = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=100, n_target=50,
        quality_score=1.0, representativeness=1.0,
        recency_score=1.0, stability_score=1.0,
    )
    with_weak = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=100, n_target=50,
        quality_score=1.0, representativeness=0.1,  # factor débil
        recency_score=1.0, stability_score=1.0,
    )
    w_good = engine.calculate_weights(good)
    w_weak = engine.calculate_weights(with_weak)
    assert w_weak.primary_weight < w_good.primary_weight


def test_five_factors_present(engine):
    m = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=10, n_target=50,
        quality_score=0.5, representativeness=0.5,
        recency_score=0.5, stability_score=0.5,
    )
    w = engine.calculate_weights(m)
    assert set(w.factors.keys()) == {"sufficiency", "quality", "representativeness", "recency", "stability"}


@given(
    n=st.integers(min_value=0, max_value=500),
    quality=st.floats(min_value=0.0, max_value=1.0),
    rep=st.floats(min_value=0.0, max_value=1.0),
    rec=st.floats(min_value=0.0, max_value=1.0),
    stab=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_property_weights_always_sum_to_one(n, quality, rep, rec, stab):
    engine = RebalancingEngine()
    m = PrimaryDataMetrics(
        dimension="visibility", cohort_id="global",
        n_effective=n, n_target=50,
        quality_score=quality, representativeness=rep,
        recency_score=rec, stability_score=stab,
    )
    w = engine.calculate_weights(m)
    assert abs(w.primary_weight + w.public_weight - 1.0) < 1e-5
    assert 0.0 <= w.primary_weight <= 1.0
    assert 0.0 <= w.public_weight <= 1.0
