"""
src/resolver/disruption.py
==========================
Disruption expansion functions for Tier 2/3 scenarios.
"""

from datetime import date, datetime, timedelta

from src.resolver.data import (
    load_all,
    FBY,
    flights_list,
    pairings,
    costs,
)


def _hrs(td: timedelta) -> float:
    return round(td.total_seconds() / 3600.0, 2)


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _fdp_limit(n_sectors: int) -> float:
    return 13.0 - 0.5 * max(0, n_sectors - 2)


def _duty_len(day: dict) -> tuple[float, datetime, datetime]:
    rep = _parse_dt(day["report_utc"])
    rel = _parse_dt(day["release_utc"])
    return _hrs(rel - rep), rep, rel


def expand_sick_call(sick_cid: str, pairing_id: str) -> dict:
    """Expand a sick-call event: uncovered flights, pax at risk, pairing details."""
    load_all()
    p = next(p for p in pairings if p["pairing_id"] == pairing_id)
    day1_flights = p["days"][0]["flights"]
    pax = sum(FBY[fid]["seats"] for fid in day1_flights)

    result = {
        "pairing_id": pairing_id,
        "sick_crew_id": sick_cid,
        "uncovered_flights_day1": day1_flights,
        "passengers_at_risk_day1": pax,
    }
    if len(p["days"]) > 1:
        result["uncovered_flights_day2"] = p["days"][1]["flights"]

    return result


def expand_station_closure(
    station: str,
    date_str: str,
    window_start_utc: str,
    window_end_utc: str,
) -> dict:
    """Identify affected flights and per-flight delay/FDP assessment for a station closure."""
    load_all()
    w_start = _parse_dt(window_start_utc)
    w_end = _parse_dt(window_end_utc)

    affected = []
    for f in flights_list:
        if f["date"] != date_str:
            continue
        depd = _parse_dt(f["dep_utc"])
        arrd = _parse_dt(f["arr_utc"])
        hit = (f["dep_station"] == station and w_start <= depd < w_end) or \
              (f["arr_station"] == station and w_start <= arrd < w_end)
        if hit:
            affected.append(f["flight_id"])

    per_flight = []
    for fid in affected:
        f = FBY[fid]
        p = next(p for p in pairings for day in p["days"] if fid in day["flights"])
        day = next(day for day in p["days"] if fid in day["flights"])
        dl, rep, rel = _duty_len(day)

        depd = _parse_dt(f["dep_utc"])
        arrd = _parse_dt(f["arr_utc"])
        anchor = depd if (f["dep_station"] == station and w_start <= depd < w_end) else arrd
        shift = _hrs((w_end + timedelta(minutes=30)) - anchor)
        new_rel = rel + timedelta(hours=shift)
        new_fdp = _hrs(new_rel - rep)
        lim = _fdp_limit(len(day["flights"]))
        feasible = new_fdp <= lim

        per_flight.append({
            "flight_id": fid,
            "pairing_id": p["pairing_id"],
            "min_delay_hours": round(shift, 2),
            "crew_fdp_after_delay": round(new_fdp, 2),
            "fdp_limit": lim,
            "action": "delay (crew legal)" if feasible else "delay exceeds crew FDP — re-crew tail legs from reserves or cancel",
        })

    return {
        "affected_flights": affected,
        "per_flight_assessment": per_flight,
    }


def expand_delay(aircraft: str, date_str: str, delay_hours: float) -> dict:
    """Analyze FDP breach from a tech delay cascading through all legs."""
    load_all()
    p = next(
        p for p in pairings
        if p["aircraft"] == aircraft and p["days"][0]["date"] == date_str
    )
    day = p["days"][0]
    dl, rep, rel = _duty_len(day)
    new_fdp = round(dl + delay_hours, 2)
    n_sectors = len(day["flights"])
    lim = _fdp_limit(n_sectors)
    breach = new_fdp > lim

    result = {
        "pairing_id": p["pairing_id"],
        "original_fdp": dl,
        "fdp_after_delay": new_fdp,
        "fdp_limit": lim,
        "sectors": n_sectors,
        "breach": breach,
    }
    if breach:
        result["breach_detail"] = (
            f"RULE-FDP-01: delayed duty runs {new_fdp}h vs {lim}h limit "
            f"({n_sectors} sectors) — the rostered crew cannot legally complete the last leg."
        )
    return result
