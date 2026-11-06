# DustGuard engineering results

Computed from the complete input snapshot in `summary.json`. All scenario parameters are assumed, not measured.

| Ambient (°C) | Scenario | Flow (L/s) | Core Δp (Pa) | Effective UA (W/K) | Heat at fixed hot side (W) | Required hot side for duty (°C) | Fan electrical power (W) |
|---|---|---|---|---|---|---|---|
| 35 | clean | 241.7 | 48.0 | 235.0 | 3968 | 50.8 | 37.3 |
| 35 | mild | 231.2 | 57.0 | 200.7 | 3525 | 52.7 | 41.3 |
| 35 | moderate | 217.6 | 68.0 | 165.1 | 3024 | 55.7 | 45.3 |
| 35 | heavy | 199.6 | 81.7 | 127.9 | 2452 | 60.5 | 48.9 |
| 43 | clean | 241.7 | 46.8 | 231.1 | 2645 | 59.1 | 36.3 |
| 43 | mild | 231.2 | 55.6 | 197.8 | 2354 | 61.1 | 40.2 |
| 43 | moderate | 217.6 | 66.3 | 163.0 | 2023 | 64.0 | 44.2 |
| 43 | heavy | 199.6 | 79.6 | 126.6 | 1644 | 68.9 | 47.7 |
| 50 | clean | 241.7 | 45.7 | 227.8 | 1530 | 66.3 | 35.5 |
| 50 | mild | 231.2 | 54.4 | 195.4 | 1363 | 68.3 | 39.4 |
| 50 | moderate | 217.6 | 64.9 | 161.3 | 1173 | 71.3 | 43.2 |
| 50 | heavy | 199.6 | 77.9 | 125.4 | 955 | 76.2 | 46.6 |

At 43 °C, heavy fouling reduces airflow by 17.5% and heat rejection by 37.9% relative to clean at the same hot-side temperature.

Hot-side temperature for the heat comparison: 60 °C. The separate required-temperature calculation fixes duty at 2500 W.

## Maintenance criterion

Criterion: 15% loss of heat rejection from clean at the same ambient and hot-side temperature.

| Ambient (°C) | Nominal severity | Lowest corner threshold | Highest corner threshold | Cases not reaching criterion |
|---|---|---|---|---|
| 35 | 0.281 | 0.174 | 0.602 | 0 |
| 43 | 0.286 | 0.177 | 0.609 | 0 |
| 50 | 0.289 | 0.180 | 0.615 | 0 |

The envelope varies four assumptions at their endpoint combinations; it is not a statistical confidence interval. Severity has no calibrated relationship to dust mass, operating hours, or a cleaning schedule.

## Interpretation and verification

- `mechanisms.csv` separates pressure-only and thermal-only fouling at the moderate scenario. The combined model applies the flow correction and series thermal resistance once each.
- `sensitivity.csv` varies seven inputs one at a time; the reference case is moderate fouling at the configured sensitivity ambient.
- Maximum numerical fan/system imbalance over all scenarios: 2.01e-12 Pa.
- Both pressure curves scale with inlet density, so volume flow is temperature-independent under this particular model. Mass flow, heat rejection, and power still change.
- Fan electrical power increases with fouling in the chosen operating range despite declining airflow. This follows the assumed fan curve and fixed efficiency, and is not a universal fan trend.
- No hardware measurements, refrigerant-cycle model, whole-system COP, dust deposition kinetics, or measured fan map are included.
