"""Reproduce the scenario comparison, mechanism split, and bounded sensitivity study."""

import argparse
import csv
import json
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .model import Model, evaluate, heat_loss_fraction, maintenance_threshold, positive

COLORS = ["#21618c", "#148f77", "#d68910", "#a93226"]


def load_config(path: Path) -> tuple[dict, Model]:
    data = json.loads(path.read_text())
    model = Model(**data["model"])
    study = data["study"]
    positive("thermal duty", study["thermal_duty_w"])
    if not study["ambient_c"] or not study["scenarios"]:
        raise ValueError("ambient and scenario lists cannot be empty")
    points = study["severity_points"]
    if isinstance(points, bool) or not isinstance(points, int) or points < 3:
        raise ValueError("severity_points must be an integer >= 3")
    for ambient, severity in product(study["ambient_c"], study["scenarios"].values()):
        evaluate(model, ambient, severity, study["hot_side_c"], study["thermal_duty_w"])
    maintenance_threshold(
        model, study["sensitivity_ambient_c"], study["maintenance_heat_loss_fraction"]
    )
    evaluate(
        model,
        study["sensitivity_ambient_c"],
        study["sensitivity_severity"],
        study["hot_side_c"],
        study["thermal_duty_w"],
    )
    for section in ("sensitivity", "threshold_envelope"):
        if not data[section]:
            raise ValueError(f"{section} cannot be empty")
        for key, values in data[section].items():
            if len(values) != 2 or values[0] >= values[1]:
                raise ValueError(f"{section}.{key} needs two increasing endpoints")
            for value in values:
                replace(model, **{key: value})
    return data, model


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def corner_models(data: dict, model: Model) -> list[tuple[dict, Model]]:
    keys = list(data["threshold_envelope"])
    return [
        (
            dict(zip(keys, values, strict=True)),
            replace(model, **dict(zip(keys, values, strict=True))),
        )
        for values in product(*(data["threshold_envelope"][key] for key in keys))
    ]


def comparison(data: dict, model: Model) -> list[dict]:
    study = data["study"]
    rows = []
    for ambient in study["ambient_c"]:
        for scenario, severity in study["scenarios"].items():
            result = evaluate(
                model, ambient, severity, study["hot_side_c"], study["thermal_duty_w"]
            )
            rows.append(
                {
                    "scenario": scenario,
                    **asdict(result),
                    "heat_loss_fraction": heat_loss_fraction(model, ambient, severity),
                }
            )
    return rows


def sensitivity(data: dict, model: Model) -> tuple[list[dict], list[dict]]:
    study = data["study"]
    ambient, severity = study["sensitivity_ambient_c"], study["sensitivity_severity"]
    reference = evaluate(model, ambient, severity, study["hot_side_c"], study["thermal_duty_w"])
    rows = []
    for parameter, values in data["sensitivity"].items():
        for value in values:
            varied = replace(model, **{parameter: value})
            result = evaluate(
                varied, ambient, severity, study["hot_side_c"], study["thermal_duty_w"]
            )
            rows.append(
                {
                    "parameter": parameter,
                    "value": value,
                    "heat_rejection_w": result.heat_rejection_w,
                    "electrical_power_w": result.electrical_power_w,
                    "heat_change_percent": 100
                    * (result.heat_rejection_w / reference.heat_rejection_w - 1),
                    "power_change_percent": 100
                    * (result.electrical_power_w / reference.electrical_power_w - 1),
                }
            )
    mechanisms = []
    for name, pressure_enabled, thermal_enabled in (
        ("clean", False, False),
        ("pressure only", True, False),
        ("thermal only", False, True),
        ("both", True, True),
    ):
        varied = replace(
            model,
            pressure_fouling_coefficient=model.pressure_fouling_coefficient
            if pressure_enabled
            else 0,
            thermal_fouling_k_w=model.thermal_fouling_k_w if thermal_enabled else 0,
        )
        result = evaluate(varied, ambient, severity, study["hot_side_c"], study["thermal_duty_w"])
        mechanisms.append({"mechanism": name, **asdict(result)})
    return rows, mechanisms


def threshold_study(data: dict, model: Model) -> tuple[list[dict], list[dict]]:
    loss = data["study"]["maintenance_heat_loss_fraction"]
    rows, summaries = [], []
    for ambient in data["study"]["ambient_c"]:
        thresholds = []
        for index, (parameters, varied) in enumerate(corner_models(data, model)):
            threshold = maintenance_threshold(varied, ambient, loss)
            thresholds.append(threshold)
            rows.append(
                {
                    "case": index,
                    "ambient_c": ambient,
                    **parameters,
                    "threshold_severity": threshold,
                    "threshold_reached": threshold is not None,
                }
            )
        finite = [value for value in thresholds if value is not None]
        unreached = len(thresholds) - len(finite)
        summaries.append(
            {
                "ambient_c": ambient,
                "nominal_severity": maintenance_threshold(model, ambient, loss),
                "minimum_reached_severity": min(finite) if finite else None,
                "upper_severity": max(finite) if finite and not unreached else None,
                "unreached_cases": unreached,
                "corner_cases": len(thresholds),
            }
        )
    return rows, summaries


def figures(
    data: dict,
    model: Model,
    rows: list[dict],
    one_at_time: list[dict],
    mechanisms: list[dict],
    thresholds: list[dict],
    out: Path,
) -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
            "figure.dpi": 150,
        }
    )
    study = data["study"]
    scenarios = list(study["scenarios"])
    scenario_colors = [COLORS[i % len(COLORS)] for i in range(len(scenarios))]
    ambients = study["ambient_c"]

    def save(fig, name):
        fig.savefig(out / name, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(1, len(ambients), figsize=(13, 4), squeeze=False, layout="constrained")
    flow = np.linspace(0, model.fan_free_flow_m3_s, 301)
    for axis, ambient in zip(axes[0], ambients, strict=True):
        axis.plot(
            flow * 1000,
            [model.fan_pressure(q, ambient) for q in flow],
            color="#202a35",
            label="Assumed fan",
        )
        for color, name in zip(scenario_colors, scenarios, strict=True):
            severity = study["scenarios"][name]
            pressure = [sum(model.pressure_losses(q, ambient, severity)) for q in flow]
            result = next(r for r in rows if r["ambient_c"] == ambient and r["scenario"] == name)
            axis.plot(flow * 1000, pressure, color=color, linestyle="--", label=name)
            axis.scatter(
                result["flow_m3_s"] * 1000, result["fan_pressure_pa"], color=color, zorder=4
            )
        axis.set(
            xlabel="Volume flow (L/s)",
            ylabel="Pressure rise / loss (Pa)",
            title=f"{ambient:g} °C",
            ylim=(0, model.fan_shutoff_pa * 1.4),
        )
    axes[0, -1].legend(fontsize=8)
    save(fig, "operating_points.png")

    reference_rows = [
        evaluate(
            model,
            study["sensitivity_ambient_c"],
            study["scenarios"][name],
            study["hot_side_c"],
            study["thermal_duty_w"],
        )
        for name in scenarios
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    axes[0].bar(scenarios, [r.flow_m3_s * 1000 for r in reference_rows], color=scenario_colors)
    axes[0].set(
        ylabel="Volume flow (L/s)", title=f"Airflow at {study['sensitivity_ambient_c']:g} °C"
    )
    core = [r.core_pressure_pa for r in reference_rows]
    axes[1].bar(scenarios, core, color=scenario_colors, label="Core")
    axes[1].bar(
        scenarios,
        [r.duct_pressure_pa for r in reference_rows],
        bottom=core,
        color="#aeb6bf",
        label="Duct",
    )
    axes[1].set(ylabel="Pressure drop (Pa)", title="Pressure partition at operating point")
    axes[1].legend()
    save(fig, "airflow_pressure.png")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    fields = [
        ("heat_rejection_w", "Heat rejection (W)", f"Hot side fixed at {study['hot_side_c']:g} °C"),
        (
            "required_hot_side_c",
            "Required hot side (°C)",
            f"Duty fixed at {study['thermal_duty_w']:g} W",
        ),
        ("hydraulic_power_w", "Fan hydraulic power (W)", "Air power"),
        (
            "electrical_power_w",
            "Estimated fan electrical power (W)",
            f"Fixed efficiency {model.fan_efficiency:.2f}",
        ),
    ]
    for axis, (field, label, title) in zip(axes.flat, fields, strict=True):
        for color, scenario in zip(scenario_colors, scenarios, strict=True):
            subset = [r for r in rows if r["scenario"] == scenario]
            axis.plot(
                [r["ambient_c"] for r in subset],
                [r[field] for r in subset],
                "o-",
                color=color,
                label=scenario,
            )
        axis.set(xlabel="Ambient (°C)", ylabel=label, title=title)
    axes[0, 0].legend(fontsize=8)
    save(fig, "thermal_and_power.png")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    for axis, field, title in zip(
        axes,
        ["flow_m3_s", "ua_effective_w_k", "heat_rejection_w"],
        ["Airflow", "Effective UA", "Heat rejection"],
        strict=True,
    ):
        axis.bar(
            [r["mechanism"] for r in mechanisms],
            [100 * r[field] / mechanisms[0][field] for r in mechanisms],
            color=COLORS,
        )
        axis.set(ylabel="Percent of clean value", title=title, ylim=(0, 110))
        axis.tick_params(axis="x", labelrotation=25)
    fig.suptitle(
        f"Mechanism split: severity {study['sensitivity_severity']:g}, {study['sensitivity_ambient_c']:g} °C"
    )
    save(fig, "mechanism_comparison.png")

    names = list(data["sensitivity"])
    parameter_labels = {
        "fan_shutoff_pa": "Fan shutoff pressure",
        "core_resistance_pa_s2_m6": "Clean core resistance",
        "ua_reference_w_k": "Reference UA",
        "thermal_fouling_k_w": "Thermal fouling resistance",
        "pressure_fouling_coefficient": "Pressure fouling coefficient",
        "flow_exponent": "Airflow exponent",
        "fan_efficiency": "Fan efficiency",
    }
    labels = [parameter_labels.get(name, name.replace("_", " ")) for name in names]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained", sharey=True)
    for axis, field, title in zip(
        axes,
        ["heat_change_percent", "power_change_percent"],
        ["Heat rejection", "Fan electrical power"],
        strict=True,
    ):
        for i, name in enumerate(names):
            pair = [r for r in one_at_time if r["parameter"] == name]
            values = [r[field] for r in pair]
            axis.plot(values, [i, i], color="#aeb6bf", linewidth=3)
            axis.scatter(
                values[0], i, color=COLORS[0], label="Low input" if i == 0 else None, zorder=3
            )
            axis.scatter(
                values[1], i, color=COLORS[3], label="High input" if i == 0 else None, zorder=3
            )
        axis.axvline(0, color="#444444", linewidth=0.8)
        axis.set(
            yticks=range(len(names)),
            yticklabels=labels,
            xlabel="Change from nominal (%)",
            title=title,
        )
    axes[0].invert_yaxis()
    axes[1].legend(fontsize=8)
    save(fig, "sensitivity.png")

    severity = np.linspace(0, 1, study["severity_points"])
    ambient = study["sensitivity_ambient_c"]
    corner_losses = np.array(
        [
            [heat_loss_fraction(varied, ambient, s) for s in severity]
            for _, varied in corner_models(data, model)
        ]
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    axes[0].fill_between(
        severity,
        100 * corner_losses.min(axis=0),
        100 * corner_losses.max(axis=0),
        color="#d5d8dc",
        label="Assumption envelope",
    )
    axes[0].plot(
        severity,
        [100 * heat_loss_fraction(model, ambient, s) for s in severity],
        color=COLORS[0],
        label="Nominal",
    )
    axes[0].axhline(
        100 * study["maintenance_heat_loss_fraction"],
        color=COLORS[3],
        linestyle="--",
        label="Maintenance criterion",
    )
    axes[0].set(
        xlabel="Scenario severity (dimensionless)",
        ylabel="Heat rejection loss (%)",
        title=f"Same-temperature loss at {ambient:g} °C",
    )
    axes[0].legend(fontsize=8)
    axes[1].fill_between(
        [r["ambient_c"] for r in thresholds],
        [
            r["minimum_reached_severity"] if r["minimum_reached_severity"] is not None else np.nan
            for r in thresholds
        ],
        [r["upper_severity"] if r["upper_severity"] is not None else np.nan for r in thresholds],
        color="#d5d8dc",
        label="Assumption envelope",
    )
    axes[1].plot(
        [r["ambient_c"] for r in thresholds],
        [
            r["nominal_severity"] if r["nominal_severity"] is not None else np.nan
            for r in thresholds
        ],
        "o-",
        color=COLORS[0],
        label="Nominal",
    )
    axes[1].set(
        xlabel="Ambient (°C)",
        ylabel="Threshold severity",
        ylim=(0, 1),
        title="No mapping to dust mass or time",
    )
    if any(r["unreached_cases"] for r in thresholds):
        axes[1].text(
            0.03,
            0.95,
            "Some cases do not reach threshold; see CSV",
            transform=axes[1].transAxes,
            va="top",
            fontsize=8,
        )
    axes[1].legend(fontsize=8)
    save(fig, "maintenance_threshold.png")


def run(config_path: Path, output: Path) -> dict:
    data, model = load_config(config_path)
    output.mkdir(parents=True, exist_ok=True)
    rows = comparison(data, model)
    one_at_time, mechanisms = sensitivity(data, model)
    corner_rows, thresholds = threshold_study(data, model)
    write_csv(output / "scenario_comparison.csv", rows)
    write_csv(output / "sensitivity.csv", one_at_time)
    write_csv(output / "mechanisms.csv", mechanisms)
    write_csv(output / "threshold_corners.csv", corner_rows)
    write_csv(output / "maintenance_thresholds.csv", thresholds)
    ambient = data["study"]["sensitivity_ambient_c"]
    clean = evaluate(
        model, ambient, 0, data["study"]["hot_side_c"], data["study"]["thermal_duty_w"]
    )
    heavy = evaluate(
        model, ambient, 1, data["study"]["hot_side_c"], data["study"]["thermal_duty_w"]
    )
    summary = {
        "inputs": data,
        "reference_ambient_c": ambient,
        "clean": asdict(clean),
        "heavy": asdict(heavy),
        "heavy_airflow_loss_percent": 100 * (1 - heavy.flow_m3_s / clean.flow_m3_s),
        "heavy_heat_loss_percent": 100 * heat_loss_fraction(model, ambient, 1),
        "maximum_pressure_balance_error_pa": max(abs(r["pressure_balance_error_pa"]) for r in rows),
        "thresholds": thresholds,
        "physical_validation_performed": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    lines = [
        "# DustGuard engineering results",
        "",
        "Computed from the complete input snapshot in `summary.json`. All scenario parameters are assumed, not measured.",
        "",
        "| Ambient (°C) | Scenario | Flow (L/s) | Core Δp (Pa) | Effective UA (W/K) | Heat at fixed hot side (W) | Required hot side for duty (°C) | Fan electrical power (W) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['ambient_c']:g} | {r['scenario']} | {r['flow_m3_s'] * 1000:.1f} | {r['core_pressure_pa']:.1f} | {r['ua_effective_w_k']:.1f} | {r['heat_rejection_w']:.0f} | {r['required_hot_side_c']:.1f} | {r['electrical_power_w']:.1f} |"
        )
    lines += [
        "",
        f"At {ambient:g} °C, heavy fouling reduces airflow by {summary['heavy_airflow_loss_percent']:.1f}% and heat rejection by {summary['heavy_heat_loss_percent']:.1f}% relative to clean at the same hot-side temperature.",
        "",
        f"Hot-side temperature for the heat comparison: {data['study']['hot_side_c']:g} °C. The separate required-temperature calculation fixes duty at {data['study']['thermal_duty_w']:g} W.",
        "",
        "## Maintenance criterion",
        "",
        f"Criterion: {100 * data['study']['maintenance_heat_loss_fraction']:g}% loss of heat rejection from clean at the same ambient and hot-side temperature.",
        "",
        "| Ambient (°C) | Nominal severity | Lowest corner threshold | Highest corner threshold | Cases not reaching criterion |",
        "|---|---|---|---|---|",
    ]
    for r in thresholds:
        values = [
            "not reached" if r[key] is None else f"{r[key]:.3f}"
            for key in ("nominal_severity", "minimum_reached_severity", "upper_severity")
        ]
        lines.append(f"| {r['ambient_c']:g} | {' | '.join(values)} | {r['unreached_cases']} |")
    lines += [
        "",
        "The envelope varies four assumptions at their endpoint combinations; it is not a statistical confidence interval. Severity has no calibrated relationship to dust mass, operating hours, or a cleaning schedule.",
        "",
        "## Interpretation and verification",
        "",
        "- `mechanisms.csv` separates pressure-only and thermal-only fouling at the moderate scenario. The combined model applies the flow correction and series thermal resistance once each.",
        "- `sensitivity.csv` varies seven inputs one at a time; the reference case is moderate fouling at the configured sensitivity ambient.",
        f"- Maximum numerical fan/system imbalance over all scenarios: {summary['maximum_pressure_balance_error_pa']:.3g} Pa.",
        "- Both pressure curves scale with inlet density, so volume flow is temperature-independent under this particular model. Mass flow, heat rejection, and power still change.",
        "- Fan electrical power increases with fouling in the chosen operating range despite declining airflow. This follows the assumed fan curve and fixed efficiency, and is not a universal fan trend.",
        "- No hardware measurements, refrigerant-cycle model, whole-system COP, dust deposition kinetics, or measured fan map are included.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    figures(data, model, rows, one_at_time, mechanisms, thresholds, output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Condenser fouling scenario and sensitivity study")
    parser.add_argument("--config", type=Path, default=Path("configs/baseline.json"))
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    result = run(args.config, args.output)
    print(
        f"Results: {args.output}; heavy airflow loss {result['heavy_airflow_loss_percent']:.1f}%, "
        f"heat rejection loss {result['heavy_heat_loss_percent']:.1f}%"
    )


if __name__ == "__main__":
    main()
