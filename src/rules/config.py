"""
src/rules/config.py
===================
Dynamic configuration loader for CAR legality rules from data/rules.json.
Zero hardcoding of regulatory thresholds.
"""

import json
from pathlib import Path

_RULES_PATH = Path(__file__).parent.parent.parent / "data" / "rules.json"
_RULES_RAW = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
_RULE_PARAMS = {r["rule_id"]: r.get("params", {}) for r in _RULES_RAW["rules"]}

# RULE-FDP-01 parameters
FDP_BASE_HOURS: float = float(_RULE_PARAMS["RULE-FDP-01"]["base_fdp_hours"])  # 13.0
FDP_REDUCTION_PER_EXTRA_SECTOR: float = float(
    _RULE_PARAMS["RULE-FDP-01"]["reduction_per_extra_sector_hours"]
)  # 0.5
FDP_FREE_SECTORS: int = int(_RULE_PARAMS["RULE-FDP-01"]["free_sectors"])  # 2

# RULE-DUTY-02 parameters
DUTY_MAX_HOURS: float = float(_RULE_PARAMS["RULE-DUTY-02"]["max_duty_hours"])  # 60.0
DUTY_WINDOW_DAYS: int = int(_RULE_PARAMS["RULE-DUTY-02"]["window_days"])  # 7

# RULE-FLT-03 parameters
FLT_MAX_HOURS: float = float(_RULE_PARAMS["RULE-FLT-03"]["max_flight_hours"])  # 100.0
FLT_WINDOW_DAYS: int = int(_RULE_PARAMS["RULE-FLT-03"]["window_days"])  # 28

# RULE-REST-04 parameters
REST_MIN_HOURS: float = float(_RULE_PARAMS["RULE-REST-04"]["min_rest_hours"])  # 12.0

# General definitions from rules.json
DEFINITIONS = _RULES_RAW.get("definitions", {})
TIME_CONVENTION = _RULES_RAW.get("time_convention", "")
