# -*- coding: utf-8 -*-
"""Position-correct fetch for ENTSO-E A24 'Aggregated Balancing Energy Bids'.

entsoe-py (<=0.8.0) parse_aggregated_bids has two bugs that shift/truncate series:
  1. it zips points onto timestamps IGNORING the <position> element — but these
     documents use curveType A03, where a point is OMITTED when its value repeats,
     so every omission slides all later values onto earlier timestamps and the
     data frontier can look hours behind reality;
  2. it reads only the first <Period> block of each TimeSeries.

This module parses positions and all periods explicitly and forward-fills omitted
positions within each period (A03 semantics: omitted = previous value repeats).
Output mimics entsoe-py: tz-aware index in the bidding-zone timezone, MultiIndex
columns (direction, mrid, unit) with unit in {Offered, Activated}.

Usage (drop-in):   raw = query_aggregated_bids_fixed(client, "GR", "A47", start, end)
where `client` is your EntsoePandasClient (only its API session/key is used).
"""
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from entsoe import EntsoeRawClient
from entsoe.mappings import lookup_area
from entsoe.parsers import _resolution_to_timedelta

_DIRECTION = {"A01": "Up", "A02": "Down"}


def query_aggregated_bids_fixed(client, country_code, process_type, start, end):
    area = lookup_area(country_code)
    xml = EntsoeRawClient.query_aggregated_bids(
        client, country_code=country_code, process_type=process_type,
        start=start, end=end)
    soup = BeautifulSoup(xml, "html.parser")

    pieces = {}  # (direction, mrid, unit) -> [Series per period]
    for ts in soup.find_all("timeseries"):
        mrid = int(ts.find("mrid").text)
        direction = _DIRECTION[ts.find("flowdirection.direction").text]
        ct = ts.find("curvetype")
        ffill = (ct is None) or (ct.text == "A03")   # omitted point = repeat
        for per in ts.find_all("period"):
            ti = per.find("timeinterval")
            p0 = pd.Timestamp(ti.find("start").text)
            p1 = pd.Timestamp(ti.find("end").text)
            freq = _resolution_to_timedelta(per.find("resolution").text)  # freq string, e.g. '15min'
            step = pd.tseries.frequencies.to_offset(freq)
            idx = pd.date_range(p0, p1, freq=freq, inclusive="left")
            off = pd.Series(np.nan, index=idx)
            act = pd.Series(np.nan, index=idx)
            for p in per.find_all("point"):
                pos = int(p.find("position").text)
                t = p0 + (pos - 1) * step
                if not (p0 <= t < p1):
                    continue
                q = p.find("quantity")
                if q is not None:
                    off[t] = float(q.text)
                sq = p.find("secondaryquantity")
                if sq is not None:
                    act[t] = float(sq.text)
            if ffill:
                off = off.ffill()
                act = act.ffill()
            pieces.setdefault((direction, mrid, "Offered"), []).append(off)
            pieces.setdefault((direction, mrid, "Activated"), []).append(act)

    if not pieces:
        return pd.DataFrame()
    cols = {}
    for key, parts in pieces.items():
        s = pd.concat(parts).sort_index()
        cols[key] = s[~s.index.duplicated(keep="last")]
    out = pd.DataFrame(cols)
    out.columns = pd.MultiIndex.from_tuples(out.columns, names=("direction", "mrid", "unit"))
    out = out.sort_index().sort_index(axis=1)
    out = out.tz_convert(area.tz)
    return out.truncate(before=start.tz_convert(area.tz), after=end.tz_convert(area.tz))


def query_cbmp_fixed(client, country_code, start, end):
    """GR aFRR CBMP (PICASSO / local aFRR prices) at 4-second resolution.

    Fetches documentType=A84 with processType=A67 — the route entsoe-py cannot
    reach (its price wrapper omits processType). Returns a DataFrame with columns
    cbmp_up / cbmp_dn on a 4-second tz-aware index (bidding-zone timezone).
    curveType A03: omitted points repeat the previous value (forward-filled)."""
    area = lookup_area(country_code)
    xml = EntsoeRawClient._base_request(
        client,
        params={"documentType": "A84", "controlArea_Domain": area.code,
                "processType": "A67"},
        start=start, end=end).text
    soup = BeautifulSoup(xml, "html.parser")
    out = {}
    for ts in soup.find_all("timeseries"):
        d = _DIRECTION[ts.find("flowdirection.direction").text]
        ct = ts.find("curvetype")
        ffill = (ct is None) or (ct.text == "A03")
        parts = []
        for per in ts.find_all("period"):
            ti = per.find("timeinterval")
            p0 = pd.Timestamp(ti.find("start").text)
            p1 = pd.Timestamp(ti.find("end").text)
            n = int((p1 - p0) / pd.Timedelta(seconds=4))
            s = pd.Series(np.nan, index=pd.date_range(p0, periods=n, freq="4s"))
            for p in per.find_all("point"):
                pos = int(p.find("position").text)
                v = p.find("activation_price.amount")
                if v is not None and 1 <= pos <= n:
                    s.iloc[pos - 1] = float(v.text)
            if ffill:
                s = s.ffill()
            parts.append(s)
        if parts:
            s = pd.concat(parts).sort_index()
            key = f"cbmp_{'up' if d == 'Up' else 'dn'}"
            out[key] = s[~s.index.duplicated(keep='last')]
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out).sort_index()
    df = df.tz_convert(area.tz)
    return df.truncate(before=start.tz_convert(area.tz), after=end.tz_convert(area.tz))


def cbmp_to_quarters(df4s, tz="CET"):
    """Aggregate a 4-second CBMP frame to 15-min quarters (naive `tz` index):
    mean/min/max per direction, overall mean, and the share of slots where the
    up and down prices coincide (proxy for PICASSO-connected single pricing)."""
    if df4s.empty:
        return pd.DataFrame()
    d = df4s.copy()
    d.index = d.index.tz_convert(tz).tz_localize(None)
    g = d.groupby(pd.Grouper(freq="15min"))
    out = pd.DataFrame({
        "cbmp_up_mean": g["cbmp_up"].mean(), "cbmp_up_min": g["cbmp_up"].min(), "cbmp_up_max": g["cbmp_up"].max(),
        "cbmp_dn_mean": g["cbmp_dn"].mean(), "cbmp_dn_min": g["cbmp_dn"].min(), "cbmp_dn_max": g["cbmp_dn"].max(),
    })
    out["cbmp_mean"] = d.mean(axis=1).groupby(pd.Grouper(freq="15min")).mean()
    eq = (d["cbmp_up"] - d["cbmp_dn"]).abs() <= 0.01
    out["connected_share"] = eq.groupby(pd.Grouper(freq="15min")).mean()
    return out.dropna(how="all")
