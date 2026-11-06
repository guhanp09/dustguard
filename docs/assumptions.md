# Engineering assumptions register

Every numerical baseline below is an illustrative input, not a fitted or measured equipment specification. The equations in [method.md](method.md) state how each is used. Changing the JSON inputs regenerates all comparisons.

| Input | Baseline | Sensitivity endpoints | Interpretation / limitation |
|---|---:|---:|---|
| Ambient pressure | 101325 Pa | Fixed | Dry ideal air; no elevation sweep |
| Air gas constant | 287.05 J/(kg·K) | Fixed | Constant composition |
| Air specific heat | 1006 J/(kg·K) | Fixed | Constant across the temperature range |
| Reference ambient | 43°C | Fixed | Defines density scaling and reference mass flow |
| Fan shutoff total pressure | 150 Pa | 135, 165 Pa | Assumed parabola; not a measured fan map |
| Fan free delivery | 0.30 m³/s | Fixed | Constant-speed assumption; no stall branch |
| Clean core resistance $K_c$ | 800 Pa/(m³/s)² | 640, 960 | Quadratic pressure loss at reference density |
| Duct resistance $K_d$ | 100 Pa/(m³/s)² | Fixed | Installation proxy; independent of fouling |
| Pressure fouling coefficient $a$ | 1.5 | 1.0, 2.0 | Heavy core resistance = 2.5 times clean at the same flow |
| Reference clean UA | 230 W/K | 184, 276 W/K | Aggregate conductance; no fin geometry correlation |
| Reference volume flow | 0.24 m³/s | Fixed | Mass-flow reference evaluated at 43°C |
| Flow exponent $n$ | 0.65 | 0.5, 0.8 | Assumed whole-UA scaling; air-side-dominated approximation |
| Heavy-fouling thermal resistance $b$ | 0.003 K/W | 0.0015, 0.0045 K/W | Lumped resistance, not m²K/W; applied linearly in scenario severity |
| Overall fan efficiency | 0.35 | 0.25, 0.45 | Constant electrical-to-air efficiency; power proxy only |
| Scenario severity | 0, 0.2, 0.5, 1.0 | Clean, mild, moderate, heavy | Dimensionless labels with no mass/time calibration |
| Ambient cases | 35, 43, 50°C | All cases | Inlet density evaluated at ambient |
| Fixed hot side for heat comparison | 60°C | Fixed | Isothermal hot side; no refrigerant zones |
| Specified duty for inverse calculation | 2500 W | Fixed | Separate calculation of required hot-side temperature |
| Maintenance criterion | 15% heat loss | Fixed | Relative to clean at the same ambient; a decision assumption |

The maintenance envelope combines endpoints of $a$, $b$, reference UA, and $n$ (16 cases per ambient). The sensitivity table varies the seven listed ranges one at a time. Neither study assigns probabilities to parameters. Thermal UA and added thermal resistance dominate the tested heat-rejection sensitivity; efficiency dominates electrical-power uncertainty in these ranges.

## Possible physical validation

Measure fan total pressure and volume flow over the operating range with calibrated instrumentation. Measure separate core and duct losses on a clean assembly, then repeat with recorded fouling conditions. Identify thermal conductance from inlet/outlet air temperatures, mass flow, and a controlled hot-side temperature. Track uncertainty in flow, temperature, pressure, and electrical power.

Record the actual dust exposure or condition rather than assigning elapsed time from the scenario index. Fit pressure and thermal effects separately and reserve other conditions for validation. A validated threshold would require representative loading, repeatability, service consequences, and measurement uncertainty. No such experiment has been performed here.
