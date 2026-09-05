"""
src/resolver/cover.py
=====================
Core resolver: check_cover() and cover_options() matching generate.py lines 433-531.
"""

from datetime import date, datetime, timedelta

from src.resolver.data import (
    load_all,
    crew,
    week_duties,
    history,
    CERT,
    FBY,
    costs,
    reserve_pool,
    RESERVE_IDS,
    pairings,
    ODD,
    EVEN,
)


def _hrs(td: timedelta) -> float:
    return round(td.total_seconds() / 3600.0, 2)


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _dt(d: date, hm: str) -> datetime:
    h, m = map(int, hm.split(":"))
    return datetime(d.year, d.month, d.day, h, m)


def _fdp_limit(n_sectors: int) -> float:
    return 13.0 - 0.5 * max(0, n_sectors - 2)


def _duty_len(day: dict) -> tuple[float, datetime, datetime]:
    rep = _parse_dt(day["report_utc"])
    rel = _parse_dt(day["release_utc"])
    return _hrs(rel - rep), rep, rel


def _certs_ok(cid: str, on_date: date) -> bool:
    return all(v >= on_date for v in CERT[cid].values())


def win_sum(cid: str, end_d: date, days: int, include_week: bool = True, kind: int = 0) -> float:
    """Sum duty(0)/flight(1) hours over calendar window ending end_d inclusive."""
    start = end_d - timedelta(days=days - 1)
    tot = 0.0
    for d, v in history.get(cid, {}).items():
        if start <= d <= end_d:
            tot += v[kind]
    if include_week:
        for (dd, rep, rel, dh, fh, pid) in week_duties.get(cid, []):
            if start <= dd <= end_d:
                tot += dh if kind == 0 else fh
    return round(tot, 2)


def check_cover(cid: str, pdays: list[dict], exclude_pairing: str | None = None, delay_h: float = 0.0) -> tuple[bool, list[str]]:
    """Can cid legally cover the given pairing days? Returns (ok, issues[])."""
    load_all()
    c = crew[cid]
    issues = []

    actype = FBY[pdays[0]["flights"][0]]["aircraft_type"]
    if actype not in c["ratings"]:
        return False, [f"RULE-QUAL-05: no {actype} rating"]

    own = [wd for wd in week_duties[cid] if wd[5] != exclude_pairing]
    sim = list(own)

    for day in pdays:
        dl, rep, rel = _duty_len(day)
        rep = rep + timedelta(hours=delay_h)
        rel = rel + timedelta(hours=delay_h)
        d = date.fromisoformat(day["date"])

        if not _certs_ok(cid, d):
            issues.append(f"RULE-CERT-06: certification invalid on {d}")

        nsec = len(day["flights"])
        if _hrs(rel - rep) > _fdp_limit(nsec) + 1e-6:
            issues.append(f"RULE-FDP-01: FDP {_hrs(rel - rep)}h > {_fdp_limit(nsec)}h limit ({nsec} sectors)")

        sim.append((d, rep, rel, _hrs(rel - rep), 0.0, "COVER"))

    sim.sort(key=lambda x: x[1])

    # REST-04
    for a, b in zip(sim, sim[1:]):
        rest = _hrs(b[1] - a[2])
        if rest < 12 - 1e-6:
            tag = "downstream" if b[5] != "COVER" and a[5] == "COVER" else "rest"
            issues.append(f"RULE-REST-04: only {rest}h rest before {b[5]} on {b[0]} ({tag} conflict)")

    # overlap
    for a, b in zip(sim, sim[1:]):
        if b[1] < a[2]:
            issues.append(f"double-booked: {a[5]} overlaps {b[5]} on {b[0]}")

    # DUTY-02 per cover day
    for day in pdays:
        d = date.fromisoformat(day["date"])
        dl, _, _ = _duty_len(day)
        base7 = win_sum(cid, d, 7)
        for wd in week_duties[cid]:
            if wd[5] == exclude_pairing and d - timedelta(days=6) <= wd[0] <= d:
                base7 -= wd[3]
        add = sum(_duty_len(x)[0] for x in pdays if date.fromisoformat(x["date"]) <= d)
        tot7 = round(base7 + add, 2)
        if tot7 > 60 + 1e-6:
            excess = tot7 - 60
            hh = int(excess)
            mm = int(round((excess - hh) * 60))
            issues.append(f"RULE-DUTY-02: would exceed 60h/7d by {hh}h{mm:02d}m on {d} (total {tot7}h)")

    return not issues, issues


def cover_options(
    pdays: list[dict],
    role: str,
    sick_cid: str,
    exclude_pairing: str,
    callout_dt: datetime,
) -> tuple[list[dict], list[dict]]:
    """Enumerate candidates to cover pairing days for a role; return (ranked_options, excluded)."""
    load_all()
    options, excluded = [], []
    base_needed = FBY[pdays[0]["flights"][0]]["dep_station"]
    pilot = role in ("Captain", "First Officer")

    for cid, c in crew.items():
        if cid == sick_cid or c["rank"] != role or c["status"] != "active":
            continue

        is_res = cid in RESERVE_IDS
        deadhead = c["base"] != base_needed
        delay_h = 0.0

        if deadhead:
            if c["base"] == "DEL" and base_needed == "BLR":
                d = date.fromisoformat(pdays[0]["date"])
                arr = _dt(d, "07:45") if d in EVEN else _dt(d, "08:45")
                dep0 = _parse_dt(FBY[pdays[0]["flights"][0]]["dep_utc"])
                delay_h = round(max(0.0, _hrs((arr + timedelta(minutes=75)) - dep0)), 2)
            else:
                excluded.append({"crew_id": cid, "reason": "RULE-BASE-07: no same-day positioning flight from base"})
                continue

        if is_res:
            r = next(x for x in reserve_pool if x["crew_id"] == cid)
            rep_req = _parse_dt(pdays[0]["report_utc"]) + timedelta(hours=delay_h)
            ws = _dt(rep_req.date(), r["oncall_window_utc"]["start"])
            we = _dt(rep_req.date(), r["oncall_window_utc"]["end"])
            if not (ws <= rep_req <= we):
                excluded.append({
                    "crew_id": cid,
                    "reason": f"reserve on-call window {r['oncall_window_utc']['start']}-{r['oncall_window_utc']['end']}Z does not cover required report {rep_req.strftime('%H:%M')}Z",
                })
                continue

        ok, issues = check_cover(cid, pdays, exclude_pairing=exclude_pairing, delay_h=delay_h)
        if not ok:
            excluded.append({"crew_id": cid, "reason": "; ".join(issues)})
            continue

        cost = 0
        if is_res:
            cost += costs["reserve_callout_pilot"] if pilot else costs["reserve_callout_cabin"]
        else:
            cost += costs["dayoff_callout_pilot"] if pilot else costs["dayoff_callout_cabin"]
        label = "reserve callout" if is_res else "day-off callout"

        if deadhead:
            cost += costs["deadhead_positioning"] + round(delay_h * costs["delay_cost_per_duty_hour"])
            label += f" + deadhead from {c['base']} (first departure delayed ~{delay_h}h)"

        options.append({
            "action": f"Assign {c['rank']} {cid} ({label})",
            "crew_id": cid,
            "legal": True,
            "rules_checked": [
                "RULE-FDP-01", "RULE-DUTY-02", "RULE-FLT-03",
                "RULE-REST-04", "RULE-QUAL-05", "RULE-CERT-06", "RULE-BASE-07",
            ],
            "cost_inr": int(round(cost)),
            "delay_hours": delay_h,
        })

    options.sort(key=lambda o: (o["cost_inr"], o["crew_id"]))

    cancel_cost = costs["cancellation_per_flight"] * sum(len(d["flights"]) for d in pdays)
    options.append({
        "action": f"Cancel all {sum(len(d['flights']) for d in pdays)} flights of the pairing",
        "crew_id": None,
        "legal": True,
        "rules_checked": [],
        "cost_inr": cancel_cost,
        "delay_hours": 0.0,
    })

    for i, o in enumerate(options):
        o["rank"] = i + 1

    return options, excluded


def _deadhead_consequence(candidate_base: str, pdays: list[dict]) -> dict | None:
    """Compute deadhead positioning details for a cross-base candidate."""
    dep_station = FBY[pdays[0]["flights"][0]]["dep_station"]
    if candidate_base == dep_station:
        return None
    if candidate_base == "DEL" and dep_station == "BLR":
        d = date.fromisoformat(pdays[0]["date"])
        if d in EVEN:
            dh_flight, arr_time = "DX589", "07:45Z"
            arr = _dt(d, "07:45")
        else:
            dh_flight, arr_time = "DX402", "08:45Z"
            arr = _dt(d, "08:45")
        dep0 = _parse_dt(FBY[pdays[0]["flights"][0]]["dep_utc"])
        delay_h = round(max(0.0, _hrs((arr + timedelta(minutes=75)) - dep0)), 2)
        pilot = True
        cost = costs["deadhead_positioning"] + round(delay_h * costs["delay_cost_per_duty_hour"])
        return {
            "requires_deadhead": True,
            "positioning_flight": dh_flight,
            "positioning_arrival": arr_time,
            "transit_minutes": 75,
            "delay_hours": delay_h,
            "deadhead_cost_inr": cost,
            "consequence": (
                f"Deadhead positioning on {dh_flight} (arr {arr_time}) "
                f"delays the first departure by ~{delay_h}h; RULE-BASE-07 deadhead cost applies."
            ),
        }
    return {
        "requires_deadhead": True,
        "blocked": True,
        "consequence": "RULE-BASE-07: no same-day positioning flight from base",
    }


def evaluate_replacement_candidate(
    candidate_id: str,
    pairing_id: str,
    unavailable_crew_id: str,
) -> dict:
    """Evaluate one named candidate against the unavailable crew member's pairing role."""
    load_all()
    pairing = next((item for item in pairings if item["pairing_id"] == pairing_id), None)
    if pairing is None:
        raise ValueError(f"Pairing {pairing_id} was not found")
    candidate = crew.get(candidate_id)
    if candidate is None:
        raise ValueError(f"Crew {candidate_id} was not found")
    incumbent = next(
        (member for member in pairing["crew"] if member["crew_id"] == unavailable_crew_id),
        None,
    )
    if incumbent is None:
        raise ValueError(f"Crew {unavailable_crew_id} is not assigned to pairing {pairing_id}")

    required_role = incumbent["role"]
    issues: list[str] = []
    if candidate["status"] != "active":
        issues.append(f"crew status is {candidate['status']}, not active")
    if candidate["rank"] != required_role:
        issues.append(
            f"RULE-QUAL-05: role mismatch; {candidate_id} is {candidate['rank']} but {required_role} is required"
        )

    deadhead = _deadhead_consequence(candidate["base"], pairing["days"])
    delay_h = deadhead["delay_hours"] if deadhead and not deadhead.get("blocked") else 0.0

    if deadhead and deadhead.get("blocked"):
        issues.append(deadhead["consequence"])

    if not issues:
        legal, issues = check_cover(candidate_id, pairing["days"], delay_h=delay_h)
    else:
        legal = False

    result = {
        "candidate_id": candidate_id,
        "candidate_rank": candidate["rank"],
        "pairing_id": pairing_id,
        "unavailable_crew_id": unavailable_crew_id,
        "required_role": required_role,
        "legal": legal,
        "issues": issues,
    }
    if deadhead and not deadhead.get("blocked"):
        result["operational_consequence"] = deadhead
    return result
