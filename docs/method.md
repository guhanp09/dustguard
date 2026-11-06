# Model and numerical verification

All dimensions and calculations use SI units. `configs/baseline.json` contains the entire assumed parameter set. This is a steady, dry-air, constant-speed fan investigation of an illustrative condenser, with an isothermal hot side. There is no refrigerant-cycle solution.

## Airflow operating point

Let volume flow be $V$ (m³/s), scenario severity $s\in[0,1]$, and inlet air density $\rho=p/[R(T_a+273.15)]$. Reference density is evaluated at 43°C. The assumed total-pressure fan and system curves are

$$\Delta p_f=P_0\frac{\rho}{\rho_{ref}}\left[1-\left(\frac{V}{V_{free}}\right)^2\right],$$

$$\Delta p_c=K_c(1+as)\frac{\rho}{\rho_{ref}}V^2,\qquad
\Delta p_d=K_d\frac{\rho}{\rho_{ref}}V^2.$$

The fan curve is used only between zero flow and free delivery. Pressure loss is purely quadratic: an inertial resistance approximation. The linear multiplier in severity is a scenario definition, with no dust-mass or elapsed-time calibration. No laminar-loss term, humidity, viscosity change, flow maldistribution, recirculation, or fan stall is represented.

The numerical intersection solves $\Delta p_f-\Delta p_c-\Delta p_d=0$ with [SciPy's bracketed Brent solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html). The decreasing fan curve and increasing system curve give exactly one positive root. The independent analytical check is

$$V=\sqrt{\frac{P_0}{P_0/V_{free}^2+K_c(1+as)+K_d}}.$$

Because both curves scale identically with density, volume flow is independent of ambient temperature **under these assumptions**. Mass flow $\dot m=\rho V$, pressure, and power remain temperature-dependent. A real fan map or viscosity-dependent core model could change this conclusion.

Hydraulic power is $P_h=V\Delta p_f$. Electrical power is estimated as $P_e=P_h/\eta$, with constant assumed overall fan/motor efficiency. Changing the assumed shutoff pressure in sensitivity holds free delivery fixed; it is a fan-map perturbation, not a motor speed sweep. The model does not calculate compressor power or total appliance energy. For a specified steady duration, fan energy would be $P_e t$.

## Heat rejection

Use $C_a=\dot m c_p$ and a constant hot-side temperature $T_h$. The clean-flow conductance proxy is

$$UA_{flow}=UA_{ref}\left(\frac{\dot m}{\dot m_{ref}}\right)^n,\qquad
\dot m_{ref}=\rho_{ref}V_{ref}.$$

The exponent $n=0.65$ is an assumed aggregate scaling for an air-side-dominated exchanger, not a geometry-specific Nusselt correlation. The study varies it from 0.5 to 0.8. Scaling the entire clean UA neglects the separation of fixed wall and refrigerant-side resistances.

Add a **lumped** fouling resistance in K/W, not an area-normalized fouling factor in m²K/W:

$$R_f=b s,\qquad UA_{eff}=\left(\frac{1}{UA_{flow}}+R_f\right)^{-1}.$$

There is no second, independent heat-loss penalty. Pressure fouling first changes the airflow; thermal fouling then adds a series resistance once.

For an isothermal hot side, the hot-side capacity rate is effectively infinite and $C_r=0$. Integrating $dT_a/d(UA)=(T_h-T_a)/C_a$ gives

$$NTU=\frac{UA_{eff}}{C_a},\quad
\varepsilon=1-\exp(-NTU),\quad
G=C_a\varepsilon,\quad
\dot Q=G(T_h-T_a).$$

The same limiting effectiveness relation is documented for the mixture zone in [MathWorks' heat-exchanger formulation](https://ch.mathworks.com/help/hydro/ref/condenserevaporator2pg.html). DustGuard implements only the isothermal limit, not that product's multizone model. `expm1` preserves accuracy at small NTU.

Air outlet temperature is $T_{out}=T_a+\dot Q/C_a$. A separate duty calculation inverts the same model:

$$T_{h,required}=T_a+\dot Q_{duty}/G.$$

The heat-comparison cases fix $T_h=60$°C. Required-temperature cases fix duty at 2500 W instead. These are separate boundary conditions. Required temperature is a thermal proxy, not a predicted condensing pressure or a refrigeration-system operating point. Inputs with $T_h<T_a$ are rejected for this heat-rejection study.

## Maintenance and sensitivity

Define relative heat loss at a common ambient and common hot-side temperature:

$$L(s)=1-\frac{\dot Q(s)}{\dot Q(0)}=1-\frac{G(s)}{G(0)}.$$

The temperature difference cancels. A root search finds the first scenario severity where $L=0.15$. `None` means the criterion is not reached for $s\leq1$; it is never replaced by a fictitious crossing. There is no mapping to days, dust concentration, or a cleaning interval.

Seven assumptions are perturbed one at a time at moderate fouling and 43°C. Four assumptions are also varied jointly at their endpoints: pressure multiplier coefficient, thermal resistance coefficient, clean UA, and airflow exponent. The 16 corner cases at each of three ambients give a sampled assumption envelope. It is neither a statistical confidence interval nor a guaranteed bound over every possible parameter combination or real condenser.

`mechanisms.csv` disables each fouling mechanism in turn at the same moderate severity. This separates the flow-mediated loss from the added thermal resistance without summing nonlinear heat penalties.

## Verification and limits

The tests compare numerical operating points with the closed-form root and compare thermal outlet temperature with an independent integrated energy ODE. They also check conservation of sensible-air energy, pressure balance, effectiveness and heat bounds, zero/large conductance limits, monotonic airflow and heat-loss behavior, the inverse duty calculation, threshold residuals, efficiency isolation, and invalid physical inputs.

These checks verify equations and implementation. They are not physical validation. Measured fan curves, clean and fouled core pressure drops, UA, and fouling resistance are unavailable. The model omits refrigerant desuperheating/subcooling, radiation, condensation on the air side, detailed fin efficiency, dust deposition kinetics, spatial blockage, transient operation, variable fan efficiency, and full-system COP or ISEER.
