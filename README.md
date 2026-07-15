# GR BMMS live — imbalance proxy, system state & mFRR prices

One-page Streamlit dashboard, three live charts (quarter cadence):
1. **mFRR prices** — activated balancing-energy prices Up/Down (actual data). Y-view fixed to
   -100...250 EUR/MWh so sparse spikes don't zoom the chart out (drag to zoom, double-click resets).
2. **mFRR net activated energy** (up - down, mFRR only, MW quarter-average) — actual data.
3. **Estimated system state** (short/long, MW quarter-average) — approximation.

Data: ENTSO-E (prices A97 near-real-time; bids A47+A67 via the position-correct parser) +
ADMIE ISP results (Energy Surplus, latest-run-wins). Cached fetches shared by all viewers
(3 ENTSO-E requests / 2 min; ISP workbooks downloaded only when newly published).

Correction artifacts (`sysdev_*.csv`) come from `sysdev_estimator.ipynb` — refresh weekly.

Run locally:  `streamlit run streamlit_app.py`
Deploy: push to GitHub, add `ENTSOE_TOKEN` to Streamlit Cloud secrets.
