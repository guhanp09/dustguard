"""Steady dry-air model with an isothermal hot side; all inputs use SI units."""

from dataclasses import dataclass
from math import expm1, isfinite

from scipy.optimize import brentq


def nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def temperature(value: float) -> None:
    if not isfinite(value) or value <= -273.15:
        raise ValueError("temperature must be finite and above absolute zero")


def severity_check(severity: float) -> None:
    if not isfinite(severity) or not 0 <= severity <= 1:
        raise ValueError("severity must be within [0, 1]")


@dataclass(frozen=True)
class Model:
    pressure_pa: float
    gas_constant_j_kg_k: float
    air_cp_j_kg_k: float
    reference_ambient_c: float
    fan_shutoff_pa: float
    fan_free_flow_m3_s: float
    core_resistance_pa_s2_m6: float
    duct_resistance_pa_s2_m6: float
    pressure_fouling_coefficient: float
    ua_reference_w_k: float
    reference_flow_m3_s: float
    flow_exponent: float
    thermal_fouling_k_w: float
    fan_efficiency: float

    def __post_init__(self) -> None:
        for name in (
            "pressure_pa",
            "gas_constant_j_kg_k",
            "air_cp_j_kg_k",
            "fan_shutoff_pa",
            "fan_free_flow_m3_s",
            "core_resistance_pa_s2_m6",
            "ua_reference_w_k",
            "reference_flow_m3_s",
            "fan_efficiency",
        ):
            positive(name, getattr(self, name))
        for name in (
            "duct_resistance_pa_s2_m6",
            "pressure_fouling_coefficient",
            "thermal_fouling_k_w",
        ):
            nonnegative(name, getattr(self, name))
        temperature(self.reference_ambient_c)
        if not isfinite(self.flow_exponent) or not 0 <= self.flow_exponent <= 1:
            raise ValueError("flow_exponent must be within [0, 1]")
        if self.fan_efficiency > 1:
            raise ValueError("fan_efficiency must be at most 1")

    def density(self, ambient_c: float) -> float:
        temperature(ambient_c)
        return self.pressure_pa / (self.gas_constant_j_kg_k * (ambient_c + 273.15))

    def fan_pressure(self, flow_m3_s: float, ambient_c: float) -> float:
        nonnegative("flow", flow_m3_s)
        if flow_m3_s > self.fan_free_flow_m3_s:
            raise ValueError("fan curve is defined only up to free flow")
        density_ratio = self.density(ambient_c) / self.density(self.reference_ambient_c)
        return (
            self.fan_shutoff_pa * density_ratio * (1 - (flow_m3_s / self.fan_free_flow_m3_s) ** 2)
        )

    def pressure_losses(
        self, flow_m3_s: float, ambient_c: float, severity: float
    ) -> tuple[float, float]:
        nonnegative("flow", flow_m3_s)
        severity_check(severity)
        factor = self.density(ambient_c) / self.density(self.reference_ambient_c)
        core = (
            self.core_resistance_pa_s2_m6
            * (1 + self.pressure_fouling_coefficient * severity)
            * factor
            * flow_m3_s**2
        )
        duct = self.duct_resistance_pa_s2_m6 * factor * flow_m3_s**2
        return core, duct

    def operating_flow(self, ambient_c: float, severity: float) -> float:
        temperature(ambient_c)
        severity_check(severity)

        def balance(flow: float) -> float:
            return self.fan_pressure(flow, ambient_c) - sum(
                self.pressure_losses(flow, ambient_c, severity)
            )

        return float(brentq(balance, 0.0, self.fan_free_flow_m3_s, xtol=1e-14, rtol=1e-12))


def conductance(ua_w_k: float, capacity_w_k: float) -> tuple[float, float]:
    """Return (effectiveness, G) for Cr=0; epsilon is defined as zero at zero flow."""
    nonnegative("UA", ua_w_k)
    nonnegative("capacity rate", capacity_w_k)
    if capacity_w_k == 0:
        return 0.0, 0.0
    effectiveness = -expm1(-ua_w_k / capacity_w_k)
    return effectiveness, capacity_w_k * effectiveness


@dataclass(frozen=True)
class Performance:
    ambient_c: float
    severity: float
    density_kg_m3: float
    flow_m3_s: float
    mass_flow_kg_s: float
    core_pressure_pa: float
    duct_pressure_pa: float
    fan_pressure_pa: float
    pressure_balance_error_pa: float
    hydraulic_power_w: float
    electrical_power_w: float
    ua_flow_w_k: float
    fouling_resistance_k_w: float
    ua_effective_w_k: float
    capacity_rate_w_k: float
    effectiveness: float
    conductance_w_k: float
    heat_rejection_w: float
    outlet_air_c: float
    required_hot_side_c: float


def evaluate(
    model: Model,
    ambient_c: float,
    severity: float,
    hot_side_c: float = 60.0,
    thermal_duty_w: float = 2500.0,
) -> Performance:
    temperature(ambient_c)
    temperature(hot_side_c)
    severity_check(severity)
    nonnegative("thermal duty", thermal_duty_w)
    if hot_side_c < ambient_c:
        raise ValueError("heat-rejection study requires hot side >= ambient")
    flow = model.operating_flow(ambient_c, severity)
    density = model.density(ambient_c)
    mass_flow = density * flow
    core, duct = model.pressure_losses(flow, ambient_c, severity)
    fan = model.fan_pressure(flow, ambient_c)
    hydraulic = fan * flow
    reference_mass = model.density(model.reference_ambient_c) * model.reference_flow_m3_s
    ua_flow = model.ua_reference_w_k * (mass_flow / reference_mass) ** model.flow_exponent
    rf = model.thermal_fouling_k_w * severity
    ua_effective = 1 / (1 / ua_flow + rf)
    capacity = mass_flow * model.air_cp_j_kg_k
    effectiveness, gain = conductance(ua_effective, capacity)
    heat = gain * (hot_side_c - ambient_c)
    return Performance(
        ambient_c,
        severity,
        density,
        flow,
        mass_flow,
        core,
        duct,
        fan,
        fan - core - duct,
        hydraulic,
        hydraulic / model.fan_efficiency,
        ua_flow,
        rf,
        ua_effective,
        capacity,
        effectiveness,
        gain,
        heat,
        ambient_c + heat / capacity,
        ambient_c + thermal_duty_w / gain,
    )


def heat_loss_fraction(model: Model, ambient_c: float, severity: float) -> float:
    # The common hot-side temperature difference cancels from this ratio.
    clean = evaluate(model, ambient_c, 0.0, hot_side_c=ambient_c)
    fouled = evaluate(model, ambient_c, severity, hot_side_c=ambient_c)
    return 1 - fouled.conductance_w_k / clean.conductance_w_k


def maintenance_threshold(
    model: Model, ambient_c: float, loss_fraction: float = 0.15
) -> float | None:
    """First severity giving the chosen relative heat loss, or None if not reached."""
    if not isfinite(loss_fraction) or not 0 < loss_fraction < 1:
        raise ValueError("loss_fraction must be strictly within (0, 1)")
    if heat_loss_fraction(model, ambient_c, 1.0) < loss_fraction:
        return None
    return float(
        brentq(
            lambda s: heat_loss_fraction(model, ambient_c, s) - loss_fraction, 0.0, 1.0, xtol=1e-12
        )
    )
