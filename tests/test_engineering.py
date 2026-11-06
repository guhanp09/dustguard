import json
from dataclasses import replace
from math import isclose, sqrt
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from dustguard.model import (
    Model,
    conductance,
    evaluate,
    heat_loss_fraction,
    maintenance_threshold,
)
from dustguard.study import comparison, load_config, sensitivity, threshold_study


@pytest.fixture
def model():
    config = Path(__file__).resolve().parents[1] / "configs" / "baseline.json"
    return Model(**json.loads(config.read_text())["model"])


def test_numerical_intersection_matches_independent_quadratic_root(model):
    for ambient in (35, 43, 50):
        for severity in (0, 0.2, 0.5, 1):
            resistance = (
                model.core_resistance_pa_s2_m6 * (1 + model.pressure_fouling_coefficient * severity)
                + model.duct_resistance_pa_s2_m6
            )
            exact = sqrt(
                model.fan_shutoff_pa
                / (model.fan_shutoff_pa / model.fan_free_flow_m3_s**2 + resistance)
            )
            result = evaluate(model, ambient, severity)
            assert result.flow_m3_s == pytest.approx(exact, rel=1e-11)
            assert abs(result.pressure_balance_error_pa) < 1e-8


def test_fan_curve_endpoints_and_pressure_partition(model):
    assert model.fan_pressure(0, 43) == pytest.approx(150)
    assert model.fan_pressure(model.fan_free_flow_m3_s, 43) == 0
    result = evaluate(model, 43, 0.5)
    assert result.fan_pressure_pa == pytest.approx(
        result.core_pressure_pa + result.duct_pressure_pa
    )
    assert result.hydraulic_power_w == pytest.approx(result.fan_pressure_pa * result.flow_m3_s)


def test_fouling_and_added_duct_resistance_reduce_airflow(model):
    flows = [model.operating_flow(43, severity) for severity in np.linspace(0, 1, 21)]
    assert np.all(np.diff(flows) < 0)
    restrictive = replace(model, duct_resistance_pa_s2_m6=200)
    assert restrictive.operating_flow(43, 0) < flows[0]


def test_density_scaling_cancels_volume_flow_but_not_mass_or_power(model):
    cool, hot = evaluate(model, 35, 0.5), evaluate(model, 50, 0.5)
    assert cool.flow_m3_s == pytest.approx(hot.flow_m3_s, rel=1e-12)
    density_ratio = (50 + 273.15) / (35 + 273.15)
    assert cool.mass_flow_kg_s / hot.mass_flow_kg_s == pytest.approx(density_ratio)
    assert cool.hydraulic_power_w / hot.hydraulic_power_w == pytest.approx(density_ratio)


def test_effectiveness_limits_and_heat_bounds(model):
    for ambient in (35, 43, 50):
        for severity in (0, 0.2, 0.5, 1):
            result = evaluate(model, ambient, severity)
            assert 0 <= result.effectiveness <= 1
            assert (
                0
                <= result.heat_rejection_w
                <= min(result.capacity_rate_w_k, result.ua_effective_w_k) * (60 - ambient)
            )
            assert ambient <= result.outlet_air_c <= 60
            assert result.heat_rejection_w == pytest.approx(
                result.capacity_rate_w_k * (result.outlet_air_c - ambient)
            )


def test_thermal_formula_matches_independent_energy_ode(model):
    result = evaluate(model, 43, 0.5)
    solution = solve_ivp(
        lambda _, air: result.ua_effective_w_k / result.capacity_rate_w_k * (60 - air),
        (0, 1),
        [43],
        rtol=1e-11,
        atol=1e-11,
    )
    assert solution.success
    assert result.outlet_air_c == pytest.approx(solution.y[0, -1], rel=1e-10)


def test_series_resistance_is_applied_once(model):
    clean = evaluate(model, 43, 0)
    fouled = evaluate(model, 43, 0.5)
    assert clean.ua_effective_w_k == pytest.approx(clean.ua_flow_w_k)
    assert 1 / fouled.ua_effective_w_k - 1 / fouled.ua_flow_w_k == pytest.approx(0.0015)
    assert fouled.ua_effective_w_k < fouled.ua_flow_w_k < clean.ua_flow_w_k


def test_heat_conductance_zero_and_large_limits():
    assert conductance(0, 250) == (0, 0)
    assert conductance(230, 0) == (0, 0)
    epsilon, gain = conductance(1e8, 250)
    assert epsilon == pytest.approx(1)
    assert gain == pytest.approx(250)
    _, gain = conductance(230, 1e12)
    assert gain == pytest.approx(230, rel=1e-9)


def test_infinite_fouling_resistance_limit(model):
    insulated = evaluate(replace(model, thermal_fouling_k_w=1e12), 43, 1)
    assert insulated.heat_rejection_w < 1e-9
    assert insulated.ua_effective_w_k > 0


def test_zero_temperature_difference_and_required_duty_inverse(model):
    result = evaluate(model, 43, 0.5, hot_side_c=43)
    assert result.heat_rejection_w == 0
    assert result.outlet_air_c == 43
    inverse = evaluate(model, 43, 0.5, hot_side_c=result.required_hot_side_c)
    assert inverse.heat_rejection_w == pytest.approx(2500)
    zero_duty = evaluate(model, 43, 0, thermal_duty_w=0)
    assert zero_duty.required_hot_side_c == 43


def test_efficiency_changes_only_electrical_power(model):
    reference = evaluate(model, 43, 0.5)
    efficient = evaluate(replace(model, fan_efficiency=0.7), 43, 0.5)
    assert efficient.electrical_power_w == pytest.approx(reference.electrical_power_w / 2)
    assert efficient.hydraulic_power_w == reference.hydraulic_power_w
    assert efficient.flow_m3_s == reference.flow_m3_s
    assert efficient.heat_rejection_w == reference.heat_rejection_w


def test_pressure_only_and_thermal_only_have_distinct_effects(model):
    clean = evaluate(model, 43, 0)
    pressure_only = evaluate(replace(model, thermal_fouling_k_w=0), 43, 0.5)
    thermal_only = evaluate(replace(model, pressure_fouling_coefficient=0), 43, 0.5)
    combined = evaluate(model, 43, 0.5)
    assert thermal_only.flow_m3_s == clean.flow_m3_s
    assert thermal_only.ua_flow_w_k == clean.ua_flow_w_k
    assert pressure_only.flow_m3_s == combined.flow_m3_s < clean.flow_m3_s
    assert (
        combined.heat_rejection_w
        < min(pressure_only.heat_rejection_w, thermal_only.heat_rejection_w)
        < clean.heat_rejection_w
    )


def test_heat_loss_monotonic_and_independent_of_fixed_hot_temperature(model):
    losses = [heat_loss_fraction(model, 43, severity) for severity in np.linspace(0, 1, 21)]
    assert losses[0] == 0
    assert np.all(np.diff(losses) > 0)
    for hot in (55, 60, 75):
        clean = evaluate(model, 43, 0, hot)
        dirty = evaluate(model, 43, 0.5, hot)
        assert 1 - dirty.heat_rejection_w / clean.heat_rejection_w == pytest.approx(
            heat_loss_fraction(model, 43, 0.5)
        )


def test_maintenance_root_and_unreached_criterion(model):
    threshold = maintenance_threshold(model, 43, 0.15)
    assert 0 < threshold < 1
    assert heat_loss_fraction(model, 43, threshold) == pytest.approx(0.15, abs=1e-10)
    less_insulation = replace(model, thermal_fouling_k_w=0.0015)
    assert maintenance_threshold(less_insulation, 43, 0.15) > threshold
    unaffected = replace(model, pressure_fouling_coefficient=0, thermal_fouling_k_w=0)
    assert maintenance_threshold(unaffected, 43, 0.15) is None
    assert maintenance_threshold(model, 43, 0.99) is None


def test_rejects_unphysical_model_inputs(model):
    for key, value in (
        ("fan_shutoff_pa", -1),
        ("fan_free_flow_m3_s", 0),
        ("ua_reference_w_k", 0),
        ("core_resistance_pa_s2_m6", -1),
        ("thermal_fouling_k_w", -1),
        ("fan_efficiency", 1.1),
        ("fan_efficiency", 0),
        ("flow_exponent", -0.1),
        ("flow_exponent", 1.1),
        ("reference_ambient_c", -273.15),
        ("pressure_pa", float("nan")),
    ):
        with pytest.raises(ValueError):
            replace(model, **{key: value})


def test_rejects_invalid_scenarios_and_curve_extrapolation(model):
    for severity in (-0.01, 1.01, float("nan")):
        with pytest.raises(ValueError):
            evaluate(model, 43, severity)
    with pytest.raises(ValueError):
        evaluate(model, 65, 0, hot_side_c=60)
    with pytest.raises(ValueError):
        evaluate(model, -273.15, 0)
    with pytest.raises(ValueError):
        model.fan_pressure(0.31, 43)
    with pytest.raises(ValueError):
        model.pressure_losses(-1, 43, 0)
    for criterion in (0, 1, float("inf")):
        with pytest.raises(ValueError):
            maintenance_threshold(model, 43, criterion)
    with pytest.raises(ValueError):
        conductance(-1, 100)


def test_configured_study_covers_scenarios_and_bounds_thresholds():
    path = Path(__file__).resolve().parents[1] / "configs" / "baseline.json"
    data, model = load_config(path)
    rows = comparison(data, model)
    assert {(r["ambient_c"], r["severity"]) for r in rows} == {
        (ambient, severity) for ambient in (35, 43, 50) for severity in (0, 0.2, 0.5, 1)
    }
    one_at_time, mechanisms = sensitivity(data, model)
    eta_rows = [r for r in one_at_time if r["parameter"] == "fan_efficiency"]
    assert all(isclose(r["heat_change_percent"], 0, abs_tol=1e-12) for r in eta_rows)
    assert mechanisms[0]["flow_m3_s"] == mechanisms[2]["flow_m3_s"]
    corners, summaries = threshold_study(data, model)
    assert len(corners) == 16 * 3
    for summary in summaries:
        assert summary["unreached_cases"] == 0
        assert (
            summary["minimum_reached_severity"]
            < summary["nominal_severity"]
            < summary["upper_severity"]
        )
