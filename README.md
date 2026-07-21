# GR BMMS live — imbalance proxy, system state & mFRR prices

One-page Streamlit dashboard, four live charts (quarter cadence):
1. **mFRR prices** — activated balancing-energy prices Up/Down (actual data). Y-view fixed to
   -100...250 EUR/MWh so sparse spikes don't zoom the chart out (drag to zoom, double-click resets).
2. **mFRR net activated energy** (up - down, mFRR only, MWh per 15-min quarter) — actual data.
3. **mFRR + aFRR net activated energy** (up - down, MWh per 15-min quarter) — actual data; the
   full ENTSO-E activation net that feeds the estimate.
4. **Estimated system state** (short/long, MWh per 15-min quarter) — approximation, standalone.

Energy units: charts 2-4 are **MWh per 15-min quarter** (energy delivered in the settlement
period), directly comparable to the ADMIE IMBABE `Total Activated Balancing Energy UP/Down (MWh)`
columns. Internally the raw ENTSO-E A24 activations and the ISP Energy Surplus arrive as MW
(quarter-average) and are divided by 4 (`QPH`) to MWh/quarter; both components of the system-state
estimate (activated-energy net + energy surplus) are in MWh/quarter.

Data: ENTSO-E (prices A97 near-real-time; bids A47+A67 via the position-correct parser) +
ADMIE ISP results (Energy Surplus, latest-run-wins). Cached fetches shared by all viewers
(3 ENTSO-E requests / 2 min; ISP workbooks downloaded only when newly published).

Correction artifacts (`sysdev_*.csv`) come from `sysdev_estimator.ipynb` — refresh weekly.

Run locally:  `streamlit run streamlit_app.py`
Deploy: push to GitHub, add `ENTSOE_TOKEN` to Streamlit Cloud secrets.
