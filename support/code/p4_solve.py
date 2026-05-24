"""问题四：离网无储能运行调度。

本阶段实现问题四（1）：离网、无储能、无购电、无售电，以及能源自治
所需风光装机容量估算。

执行：
  conda run -n learn3.8 python support/code/p4_solve.py

产出：
  support/results/p4/p4_offgrid_hourly_cases.csv
  support/results/p4/p4_offgrid_daily_cases.csv
  support/results/p4/p4_offgrid_summary.json
  support/results/p4/p4_capacity_fixed_ratio_search.csv
  support/results/p4/p4_capacity_grid_search.csv
  support/results/p4/p4_capacity_autonomy_summary.json
  support/results/p4/p4_summary.json
"""

from __future__ import annotations

import csv
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ALK_CAPACITY_MW,
    ALK_OPEX_YUAN_PER_KWH,
    ESS_CAPEX_YUAN_PER_KWH,
    ESS_CHARGE_EFF,
    ESS_DISCHARGE_EFF,
    ESS_LIFETIME_YR,
    ESS_OPEX_YUAN_PER_KWH,
    ESS_SELF_LOSS_RATE_PER_H,
    LOAD_PEAK_MW,
    NH3_CAPEX_YUAN_PER_KGH_H2,
    NH3_CAPACITY_MW,
    NH3_H2_KG_PER_KGNH3,
    NH3_LIFETIME_YR,
    NH3_OPEX_YUAN_PER_KWH,
    NH3_RATE_TPH,
    PEM_CAPACITY_MW,
    PEM_OPEX_YUAN_PER_KWH,
    PV_CAPACITY_MW,
    PV_LCOE_YUAN_PER_KWH,
    WIND_CAPACITY_MW,
    WIND_LCOE_YUAN_PER_KWH,
)
from p2_solve import load_pv_scenarios, load_typical_load, load_wind_scenarios  # noqa: E402


HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p4"
P3_SUMMARY_PATH = HERE.parent / "results" / "p3" / "p3_summary.json"
DATA_DIR = HERE.parent / "data"

N_HOURS = 24
SCENARIO_DAYS = 15
ANNUAL_DAYS = 360
EXPANSION_FACTOR = 72.0 / 36.0

ALK_FULL_MW = ALK_CAPACITY_MW * EXPANSION_FACTOR
PEM_FULL_MW = PEM_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_MW = NH3_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_TPH = NH3_RATE_TPH * EXPANSION_FACTOR
PLANT_FULL_MW = ALK_FULL_MW + PEM_FULL_MW + NH3_FULL_MW
NH3_FIXED_CAPEX_DAILY_YUAN = (
    NH3_FULL_TPH
    * 1000.0
    * NH3_H2_KG_PER_KGNH3
    * NH3_CAPEX_YUAN_PER_KGH_H2
    / (NH3_LIFETIME_YR * ANNUAL_DAYS)
)
MIN_RUNNING_RATIO = 0.10
DAILY_CAPACITY_T = 72.0

HOURLY_FIELDS = [
    "scenario_id",
    "wind_scenario",
    "solar_scenario",
    "hour",
    "P_wind_MW",
    "P_pv_MW",
    "P_re_MW",
    "P_load_MW",
    "P_load_served_MW",
    "P_load_shed_MW",
    "plant_load_ratio",
    "plant_on",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "P_plant_MW",
    "NH3_t",
    "P_curtail_MW",
    "P_buy_MW",
    "P_sell_MW",
    "cost_yuan",
    "unit_cost_yuan_per_t",
]

DAILY_FIELDS = [
    "scenario_id",
    "wind_scenario",
    "solar_scenario",
    "daily_wind_MWh",
    "daily_pv_MWh",
    "daily_re_MWh",
    "daily_load_MWh",
    "daily_load_served_MWh",
    "daily_load_shed_MWh",
    "daily_plant_MWh",
    "daily_NH3_t",
    "daily_curtail_MWh",
    "curtailment_ratio",
    "energy_self_sufficiency_ratio",
    "plant_utilization",
    "daily_cost_yuan",
    "daily_nh3_fixed_capex_yuan",
    "unit_cost_yuan_per_t",
    "is_max_curtailment_scenario",
]

CAPACITY_FIXED_FIELDS = [
    "target_type",
    "scale_k",
    "wind_capacity_MW",
    "pv_capacity_MW",
    "annual_NH3_t",
    "annual_load_shed_MWh",
    "annual_curtail_MWh",
    "annual_curtailment_ratio",
    "annual_unit_cost_yuan_per_t",
    "annual_plant_utilization",
    "feasible",
]

CAPACITY_GRID_FIELDS = [
    "target_type",
    "wind_capacity_MW",
    "pv_capacity_MW",
    "total_capacity_MW",
    "annual_NH3_t",
    "annual_load_shed_MWh",
    "annual_curtail_MWh",
    "annual_curtailment_ratio",
    "annual_unit_cost_yuan_per_t",
    "annual_plant_utilization",
    "feasible",
    "objective_value",
    "min_daily_NH3_t",
    "max_daily_load_shed_MWh",
]

SCENARIO_REQUIREMENT_FIELDS = [
    "scenario_id",
    "min_k_basic_autonomy",
    "min_wind_basic_MW",
    "min_pv_basic_MW",
    "min_k_daily_36t",
    "min_wind_daily_36t_MW",
    "min_pv_daily_36t_MW",
    "daily_NH3_t_at_solution",
    "daily_load_shed_MWh_at_solution",
]

AUTONOMY_LEVEL_FIELDS = [
    "autonomy_level",
    "method",
    "scale_k",
    "wind_capacity_MW",
    "pv_capacity_MW",
    "total_capacity_MW",
    "added_wind_MW",
    "added_pv_MW",
    "added_total_MW",
    "increase_ratio",
    "min_hourly_margin_MW",
    "annual_NH3_t",
    "annual_curtail_MWh",
    "annual_unit_cost_yuan_per_t",
    "feasible",
    "note",
]

LOAD_SHED_TOL_MWH = 1e-5
PRODUCTION_TARGET_T = 12960.0
FULL_PRODUCTION_TARGET_T = DAILY_CAPACITY_T * ANNUAL_DAYS
ROBUST_DAILY_PRODUCTION_T = 36.0
ORIGINAL_TOTAL_CAPACITY_MW = WIND_CAPACITY_MW + PV_CAPACITY_MW
AUTONOMY_LEVELS = {
    "regular_load_autonomy": {
        "plant_power_MW": 0.0,
        "note": "P_re >= P_load for all scenarios and hours",
    },
    "minimum_operation_autonomy": {
        "plant_power_MW": MIN_RUNNING_RATIO * PLANT_FULL_MW,
        "note": "P_re >= P_load + 0.1*41.5 for all scenarios and hours",
    },
    "full_production_autonomy": {
        "plant_power_MW": PLANT_FULL_MW,
        "note": "P_re >= P_load + 41.5 for all scenarios and hours",
    },
}
_BASE_PROFILE_CACHE: list[dict[str, Any]] | None = None

STORAGE_HOURLY_FIELDS = [
    "scenario_id",
    "hour",
    "P_wind_MW",
    "P_pv_MW",
    "P_re_MW",
    "P_load_MW",
    "P_load_served_MW",
    "P_load_shed_MW",
    "P_charge_MW",
    "P_discharge_MW",
    "SOC_MWh",
    "plant_load_ratio",
    "plant_on",
    "P_plant_MW",
    "NH3_t",
    "P_curtail_MW",
    "cost_yuan",
]

STORAGE_DAILY_FIELDS = [
    "scenario_id",
    "daily_NH3_t",
    "daily_curtail_MWh",
    "curtailment_ratio",
    "daily_load_shed_MWh",
    "daily_storage_charge_MWh",
    "daily_storage_discharge_MWh",
    "SOC_initial_MWh",
    "SOC_final_MWh",
    "daily_cost_yuan",
    "daily_nh3_fixed_capex_yuan",
    "unit_cost_yuan_per_t",
    "plant_utilization",
]

STORAGE_CANDIDATE_FIELDS = [
    "candidate_id",
    "storage_power_MW",
    "storage_energy_MWh",
    "duration_h",
    "W4_P1_NH3_t",
    "W4_P1_curtail_MWh",
    "W4_P1_load_shed_MWh",
    "W4_P1_cost_yuan",
    "W4_P1_unit_cost_yuan_per_t",
    "storage_daily_cost_yuan",
    "curtail_reduction_MWh",
    "NH3_increase_t",
    "incremental_cost_yuan",
    "recommended_flag",
    "recommendation_reason",
]


def _round(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _csv_value(value: float | int | str | None) -> float | int | str:
    if value is None:
        return ""
    if isinstance(value, float):
        return _round(value) if value == value else ""
    return value


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return index


def _read_first_sheet_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings: list[str] = []
        try:
            root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall("x:si", ns):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//x:t", ns)))
        except KeyError:
            pass

        workbook = ElementTree.fromstring(zf.read("xl/workbook.xml"))
        ns = {
            "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        first_sheet = workbook.find("x:sheets/x:sheet", ns)
        if first_sheet is None:
            raise ValueError(f"{path} has no worksheet")
        rel_id = first_sheet.attrib[f"{{{ns['r']}}}id"]
        rels = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        sheet_path = None
        for rel in rels.findall("r:Relationship", rel_ns):
            if rel.attrib["Id"] == rel_id:
                target = rel.attrib["Target"].lstrip("/")
                sheet_path = target if target.startswith("xl/") else "xl/" + target
                break
        if sheet_path is None:
            raise ValueError(f"worksheet relationship not found: {rel_id}")

        root = ElementTree.fromstring(zf.read(sheet_path))
    xns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", xns):
        values: dict[int, str] = {}
        for cell in row.findall("x:c", xns):
            value = cell.find("x:v", xns)
            text = ""
            if value is not None and value.text is not None:
                text = shared_strings[int(value.text)] if cell.attrib.get("t") == "s" else value.text
            values[_column_index(cell.attrib["r"])] = text
        if values:
            rows.append([values.get(index, "") for index in range(1, max(values) + 1)])
    return rows


def read_storage_params() -> dict[str, Any]:
    """Read storage parameters from Attachment 6 and keep assumptions explicit."""
    files = list(DATA_DIR.glob("附件6*.xlsx"))
    if not files:
        raise FileNotFoundError("附件6：储能设备和合成氨装置技术参数.xlsx")
    raw_rows = _read_first_sheet_rows(files[0])
    params = {
        "source_file": files[0].name,
        "raw_rows": raw_rows,
        "capex_yuan_per_kWh": ESS_CAPEX_YUAN_PER_KWH,
        "power_capex_yuan_per_kW": None,
        "opex_yuan_per_kWh": ESS_OPEX_YUAN_PER_KWH,
        "lifetime_years": ESS_LIFETIME_YR,
        "charge_efficiency": ESS_CHARGE_EFF,
        "discharge_efficiency": ESS_DISCHARGE_EFF,
        "self_loss_rate_per_hour": ESS_SELF_LOSS_RATE_PER_H,
        "soc_min_fraction": 0.0,
        "soc_max_fraction": 1.0,
        "notes": [
            "Attachment 6 gives storage investment as 1000 yuan/kWh; no separate power-capacity investment cost is provided.",
            "SOC bounds are not explicitly given in Attachment 6; dispatch uses 0 to 100% of selected energy capacity.",
            "Charge/discharge power limits are candidate configuration variables.",
        ],
    }
    return params


def load_p4_inputs(
    wind_capacity_mw: float = WIND_CAPACITY_MW,
    pv_capacity_mw: float = PV_CAPACITY_MW,
) -> list[dict[str, Any]]:
    """Build the 24 wind-solar scenarios used in Problem 4."""
    base_profiles = _load_base_profiles()
    return [
        _scale_base_profile(profile, wind_capacity_mw, pv_capacity_mw)
        for profile in base_profiles
    ]


def _load_base_profiles() -> list[dict[str, Any]]:
    """Load 24 scenario per-unit curves once; capacity scaling is done in memory."""
    global _BASE_PROFILE_CACHE
    if _BASE_PROFILE_CACHE is not None:
        return _BASE_PROFILE_CACHE
    load_pu = load_typical_load()
    wind_matrix = load_wind_scenarios()
    pv_matrix = load_pv_scenarios()
    p_load = [value * LOAD_PEAK_MW for value in load_pu]
    scenarios: list[dict[str, Any]] = []
    for wind_idx in range(6):
        wind_pu = [row[wind_idx] for row in wind_matrix]
        for pv_idx in range(4):
            pv_pu = [row[pv_idx] for row in pv_matrix]
            scenarios.append(
                {
                    "scenario_id": f"W{wind_idx + 1}_P{pv_idx + 1}",
                    "wind_scenario": f"W{wind_idx + 1}",
                    "solar_scenario": f"P{pv_idx + 1}",
                    "load_MW": p_load,
                    "wind_pu": wind_pu,
                    "pv_pu": pv_pu,
                }
            )
    _BASE_PROFILE_CACHE = scenarios
    return scenarios


def _scale_base_profile(profile: dict[str, Any], wind_capacity_mw: float, pv_capacity_mw: float) -> dict[str, Any]:
    return {
        "scenario_id": profile["scenario_id"],
        "wind_scenario": profile["wind_scenario"],
        "solar_scenario": profile["solar_scenario"],
        "load_MW": profile["load_MW"],
        "wind_MW": [float(value) * wind_capacity_mw for value in profile["wind_pu"]],
        "pv_MW": [float(value) * pv_capacity_mw for value in profile["pv_pu"]],
    }


def _load_p3_production_target() -> float:
    if not P3_SUMMARY_PATH.exists():
        return PRODUCTION_TARGET_T
    with P3_SUMMARY_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    try:
        return float(data["annual_recommended"]["total_production_t"])
    except KeyError:
        return PRODUCTION_TARGET_T


def _hourly_cost_yuan(p_wind: float, p_pv: float, p_alk: float, p_pem: float, p_nh3: float) -> float:
    generation_cost = 1000.0 * (
        WIND_LCOE_YUAN_PER_KWH * p_wind + PV_LCOE_YUAN_PER_KWH * p_pv
    )
    plant_opex = 1000.0 * (
        ALK_OPEX_YUAN_PER_KWH * p_alk
        + PEM_OPEX_YUAN_PER_KWH * p_pem
        + NH3_OPEX_YUAN_PER_KWH * p_nh3
    )
    return generation_cost + plant_opex


def solve_offgrid_no_storage(scenario: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Solve one off-grid no-storage scenario by the hourly greedy optimum."""
    scenario_id = str(scenario["scenario_id"])
    wind_scenario = str(scenario["wind_scenario"])
    solar_scenario = str(scenario["solar_scenario"])
    p_load = [float(value) for value in scenario["load_MW"]]
    p_wind = [float(value) for value in scenario["wind_MW"]]
    p_pv = [float(value) for value in scenario["pv_MW"]]

    hourly: list[dict[str, Any]] = []
    for hour in range(N_HOURS):
        wind = p_wind[hour]
        pv = p_pv[hour]
        p_re = wind + pv
        load = p_load[hour]

        load_served = min(p_re, load)
        load_shed = max(load - p_re, 0.0)
        surplus = max(p_re - load, 0.0)

        raw_ratio = surplus / PLANT_FULL_MW if PLANT_FULL_MW > 0 else 0.0
        if raw_ratio < MIN_RUNNING_RATIO:
            ratio = 0.0
            plant_on = 0
        else:
            ratio = min(raw_ratio, 1.0)
            plant_on = 1

        p_alk = ALK_FULL_MW * ratio
        p_pem = PEM_FULL_MW * ratio
        p_nh3 = NH3_FULL_MW * ratio
        p_plant = PLANT_FULL_MW * ratio
        nh3_t = NH3_FULL_TPH * ratio
        p_curtail = max(surplus - p_plant, 0.0)
        cost_yuan = _hourly_cost_yuan(wind, pv, p_alk, p_pem, p_nh3)
        unit_cost = cost_yuan / nh3_t if nh3_t > 1e-9 else None

        hourly.append(
            {
                "scenario_id": scenario_id,
                "wind_scenario": wind_scenario,
                "solar_scenario": solar_scenario,
                "hour": hour,
                "P_wind_MW": wind,
                "P_pv_MW": pv,
                "P_re_MW": p_re,
                "P_load_MW": load,
                "P_load_served_MW": load_served,
                "P_load_shed_MW": load_shed,
                "plant_load_ratio": ratio,
                "plant_on": plant_on,
                "P_alk_MW": p_alk,
                "P_pem_MW": p_pem,
                "P_nh3_MW": p_nh3,
                "P_plant_MW": p_plant,
                "NH3_t": nh3_t,
                "P_curtail_MW": p_curtail,
                "P_buy_MW": 0.0,
                "P_sell_MW": 0.0,
                "cost_yuan": cost_yuan,
                "unit_cost_yuan_per_t": unit_cost,
            }
        )

    daily = summarize_offgrid_no_storage(hourly)
    return hourly, daily


def summarize_offgrid_no_storage(hourly: list[dict[str, Any]]) -> dict[str, Any]:
    daily_wind = sum(float(row["P_wind_MW"]) for row in hourly)
    daily_pv = sum(float(row["P_pv_MW"]) for row in hourly)
    daily_re = sum(float(row["P_re_MW"]) for row in hourly)
    daily_load = sum(float(row["P_load_MW"]) for row in hourly)
    daily_load_served = sum(float(row["P_load_served_MW"]) for row in hourly)
    daily_load_shed = sum(float(row["P_load_shed_MW"]) for row in hourly)
    daily_plant = sum(float(row["P_plant_MW"]) for row in hourly)
    daily_nh3 = sum(float(row["NH3_t"]) for row in hourly)
    daily_curtail = sum(float(row["P_curtail_MW"]) for row in hourly)
    daily_cost = sum(float(row["cost_yuan"]) for row in hourly) + NH3_FIXED_CAPEX_DAILY_YUAN

    return {
        "scenario_id": hourly[0]["scenario_id"],
        "wind_scenario": hourly[0]["wind_scenario"],
        "solar_scenario": hourly[0]["solar_scenario"],
        "daily_wind_MWh": daily_wind,
        "daily_pv_MWh": daily_pv,
        "daily_re_MWh": daily_re,
        "daily_load_MWh": daily_load,
        "daily_load_served_MWh": daily_load_served,
        "daily_load_shed_MWh": daily_load_shed,
        "daily_plant_MWh": daily_plant,
        "daily_NH3_t": daily_nh3,
        "daily_curtail_MWh": daily_curtail,
        "curtailment_ratio": daily_curtail / daily_re if daily_re > 1e-9 else 0.0,
        "energy_self_sufficiency_ratio": daily_load_served / daily_load if daily_load > 1e-9 else 1.0,
        "plant_utilization": daily_nh3 / DAILY_CAPACITY_T,
        "daily_cost_yuan": daily_cost,
        "daily_nh3_fixed_capex_yuan": NH3_FIXED_CAPEX_DAILY_YUAN,
        "unit_cost_yuan_per_t": daily_cost / daily_nh3 if daily_nh3 > 1e-9 else None,
        "is_max_curtailment_scenario": 0,
    }


def _annual_summary(daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    max_daily = max(daily_rows, key=lambda row: float(row["daily_curtail_MWh"]))
    for row in daily_rows:
        row["is_max_curtailment_scenario"] = 1 if row["scenario_id"] == max_daily["scenario_id"] else 0

    annual_re = sum(float(row["daily_re_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_load = sum(float(row["daily_load_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_load_served = sum(float(row["daily_load_served_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_load_shed = sum(float(row["daily_load_shed_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_curtail = sum(float(row["daily_curtail_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_nh3 = sum(float(row["daily_NH3_t"]) * SCENARIO_DAYS for row in daily_rows)
    annual_cost = sum(float(row["daily_cost_yuan"]) * SCENARIO_DAYS for row in daily_rows)

    return {
        "scenario_count": len(daily_rows),
        "days_per_scenario": SCENARIO_DAYS,
        "annual_days": ANNUAL_DAYS,
        "annual_total_NH3_t": _round(annual_nh3),
        "annual_total_cost_yuan": _round(annual_cost),
        "annual_unit_cost_yuan_per_t": _round(annual_cost / annual_nh3 if annual_nh3 > 1e-9 else None),
        "annual_load_shed_MWh": _round(annual_load_shed),
        "annual_curtail_MWh": _round(annual_curtail),
        "annual_curtailment_ratio": _round(annual_curtail / annual_re if annual_re > 1e-9 else 0.0),
        "annual_energy_self_sufficiency_ratio": _round(
            annual_load_served / annual_load if annual_load > 1e-9 else 1.0
        ),
        "annual_load_self_sufficiency_ratio": _round(
            annual_load_served / annual_load if annual_load > 1e-9 else 1.0
        ),
        "annual_plant_utilization": _round(annual_nh3 / (DAILY_CAPACITY_T * ANNUAL_DAYS)),
        "max_curtailment_scenario_id": max_daily["scenario_id"],
        "max_curtailment_MWh": _round(float(max_daily["daily_curtail_MWh"])),
        "note": "no storage, no grid purchase, no grid sale",
    }


def dispatch_offgrid_no_storage_for_capacity(
    wind_capacity_mw: float,
    pv_capacity_mw: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Run the B1 dispatch model for a candidate wind/PV capacity pair."""
    scenarios = load_p4_inputs(wind_capacity_mw, pv_capacity_mw)
    hourly_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        hourly, daily = solve_offgrid_no_storage(scenario)
        hourly_rows.extend(hourly)
        daily_rows.append(daily)
    summary = _annual_summary(daily_rows)
    return hourly_rows, daily_rows, summary


def _target_feasible(summary: dict[str, Any], target_type: str, production_target_t: float) -> bool:
    shed = float(summary["annual_load_shed_MWh"])
    nh3 = float(summary["annual_total_NH3_t"])
    if shed > LOAD_SHED_TOL_MWH:
        return False
    if target_type == "basic_autonomy":
        return True
    if target_type == "production_autonomy":
        return nh3 + 1e-5 >= production_target_t
    if target_type == "full_production_autonomy":
        return nh3 + 1e-5 >= FULL_PRODUCTION_TARGET_T
    raise ValueError(f"unknown target_type: {target_type}")


def _robust_feasible(daily_rows: list[dict[str, Any]]) -> bool:
    return all(
        float(row["daily_load_shed_MWh"]) <= LOAD_SHED_TOL_MWH
        and float(row["daily_NH3_t"]) + 1e-5 >= ROBUST_DAILY_PRODUCTION_T
        for row in daily_rows
    )


def _basic_daily_feasible(daily: dict[str, Any]) -> bool:
    return float(daily["daily_load_shed_MWh"]) <= LOAD_SHED_TOL_MWH


def _daily_36t_feasible(daily: dict[str, Any]) -> bool:
    return _basic_daily_feasible(daily) and float(daily["daily_NH3_t"]) + 1e-5 >= ROBUST_DAILY_PRODUCTION_T


def _solve_one_profile_at_scale(profile: dict[str, Any], k: float) -> dict[str, Any]:
    scenario = _scale_base_profile(profile, WIND_CAPACITY_MW * k, PV_CAPACITY_MW * k)
    _, daily = solve_offgrid_no_storage(scenario)
    return daily


def _find_min_k_for_scenario(profile: dict[str, Any], predicate: Any, max_k: float = 80.0) -> tuple[float, dict[str, Any]]:
    low = 0.5
    high = 1.0
    high_daily = _solve_one_profile_at_scale(profile, high)
    while not predicate(high_daily):
        low = high
        high *= 1.5
        if high > max_k:
            high = max_k
            high_daily = _solve_one_profile_at_scale(profile, high)
            if not predicate(high_daily):
                raise RuntimeError(f"scenario {profile['scenario_id']} not feasible by k={max_k}")
            break
        high_daily = _solve_one_profile_at_scale(profile, high)

    for _ in range(28):
        mid = (low + high) / 2.0
        mid_daily = _solve_one_profile_at_scale(profile, mid)
        if predicate(mid_daily):
            high = mid
            high_daily = mid_daily
        else:
            low = mid
    return high, high_daily


def search_capacity_scenario_requirements() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Find fixed-ratio per-scenario capacity requirements for robust interpretation."""
    rows: list[dict[str, Any]] = []
    for profile in _load_base_profiles():
        k_basic, basic_daily = _find_min_k_for_scenario(profile, _basic_daily_feasible, max_k=20.0)
        k_36, daily_36 = _find_min_k_for_scenario(profile, _daily_36t_feasible, max_k=80.0)
        rows.append(
            {
                "scenario_id": profile["scenario_id"],
                "min_k_basic_autonomy": _round(k_basic),
                "min_wind_basic_MW": _round(WIND_CAPACITY_MW * k_basic),
                "min_pv_basic_MW": _round(PV_CAPACITY_MW * k_basic),
                "min_k_daily_36t": _round(k_36),
                "min_wind_daily_36t_MW": _round(WIND_CAPACITY_MW * k_36),
                "min_pv_daily_36t_MW": _round(PV_CAPACITY_MW * k_36),
                "daily_NH3_t_at_solution": daily_36["daily_NH3_t"],
                "daily_load_shed_MWh_at_solution": daily_36["daily_load_shed_MWh"],
            }
        )

    worst_basic = max(rows, key=lambda row: float(row["min_k_basic_autonomy"]))
    worst_daily_36 = max(rows, key=lambda row: float(row["min_k_daily_36t"]))
    return rows, {
        "fixed_ratio_basic_autonomy": {
            "scenario_id": worst_basic["scenario_id"],
            "scale_k": worst_basic["min_k_basic_autonomy"],
            "wind_capacity_MW": worst_basic["min_wind_basic_MW"],
            "pv_capacity_MW": worst_basic["min_pv_basic_MW"],
        },
        "fixed_ratio_daily_36t": {
            "scenario_id": worst_daily_36["scenario_id"],
            "scale_k": worst_daily_36["min_k_daily_36t"],
            "wind_capacity_MW": worst_daily_36["min_wind_daily_36t_MW"],
            "pv_capacity_MW": worst_daily_36["min_pv_daily_36t_MW"],
            "daily_NH3_t": worst_daily_36["daily_NH3_t_at_solution"],
            "daily_load_shed_MWh": worst_daily_36["daily_load_shed_MWh_at_solution"],
        },
        "worst_case_scenario": {
            "basic_autonomy": worst_basic["scenario_id"],
            "daily_36t": worst_daily_36["scenario_id"],
        },
    }


def _capacity_result_row(
    target_type: str,
    wind_capacity_mw: float,
    pv_capacity_mw: float,
    summary: dict[str, Any],
    feasible: bool,
    scale_k: float | None = None,
    objective_value: float | None = None,
) -> dict[str, Any]:
    row = {
        "target_type": target_type,
        "wind_capacity_MW": _round(wind_capacity_mw),
        "pv_capacity_MW": _round(pv_capacity_mw),
        "annual_NH3_t": summary["annual_total_NH3_t"],
        "annual_load_shed_MWh": summary["annual_load_shed_MWh"],
        "annual_curtail_MWh": summary["annual_curtail_MWh"],
        "annual_curtailment_ratio": summary["annual_curtailment_ratio"],
        "annual_unit_cost_yuan_per_t": summary["annual_unit_cost_yuan_per_t"],
        "annual_plant_utilization": summary["annual_plant_utilization"],
        "feasible": 1 if feasible else 0,
    }
    if scale_k is not None:
        row["scale_k"] = _round(scale_k)
    if objective_value is not None:
        row["total_capacity_MW"] = _round(wind_capacity_mw + pv_capacity_mw)
        row["objective_value"] = _round(objective_value)
    return row


def search_capacity_fixed_ratio(production_target_t: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search the smallest fixed wind/PV scale k for each autonomy definition."""
    target_types = ["basic_autonomy", "production_autonomy", "full_production_autonomy"]
    max_k_by_target = {
        "basic_autonomy": 5.0,
        "production_autonomy": 8.0,
        "full_production_autonomy": 80.0,
    }
    rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}

    for target_type in target_types:
        previous_k = 0.5
        previous_summary: dict[str, Any] | None = None
        bracket_low: tuple[float, dict[str, Any]] | None = None
        bracket_high: tuple[float, dict[str, Any]] | None = None

        max_k = max_k_by_target[target_type]
        coarse_step = 0.02
        steps = int((max_k - 0.5) / coarse_step) + 1
        for index in range(steps + 1):
            k = round(0.5 + index * coarse_step, 6)
            if k > max_k + 1e-9:
                break
            _, _, summary = dispatch_offgrid_no_storage_for_capacity(
                WIND_CAPACITY_MW * k,
                PV_CAPACITY_MW * k,
            )
            feasible = _target_feasible(summary, target_type, production_target_t)
            rows.append(
                _capacity_result_row(
                    target_type,
                    WIND_CAPACITY_MW * k,
                    PV_CAPACITY_MW * k,
                    summary,
                    feasible,
                    scale_k=k,
                )
            )
            if feasible:
                bracket_low = (previous_k, previous_summary or summary)
                bracket_high = (k, summary)
                break
            previous_k = k
            previous_summary = summary

        if bracket_high is None:
            results[target_type] = {
                "status": "not_found",
                "max_scale_k": max_k,
                "note": "target not feasible within fixed-ratio search range",
            }
            continue

        low_k = bracket_low[0] if bracket_low else 0.5
        high_k = bracket_high[0]
        high_summary = bracket_high[1]
        for _ in range(28):
            mid_k = (low_k + high_k) / 2.0
            _, _, mid_summary = dispatch_offgrid_no_storage_for_capacity(
                WIND_CAPACITY_MW * mid_k,
                PV_CAPACITY_MW * mid_k,
            )
            if _target_feasible(mid_summary, target_type, production_target_t):
                high_k = mid_k
                high_summary = mid_summary
            else:
                low_k = mid_k

        final_row = _capacity_result_row(
            target_type,
            WIND_CAPACITY_MW * high_k,
            PV_CAPACITY_MW * high_k,
            high_summary,
            True,
            scale_k=high_k,
        )
        rows.append(final_row)
        results[target_type] = final_row

    return rows, results


def _range_values(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    value = start
    while value <= stop + 1e-9:
        values.append(round(value, 6))
        value += step
    return values


def _select_best(
    candidates: list[dict[str, Any]],
    target_type: str,
    objective: str,
) -> dict[str, Any] | None:
    feasible = [row for row in candidates if row["target_type"] == target_type and int(row["feasible"]) == 1]
    if not feasible:
        return None
    if objective == "min_capacity":
        return min(
            feasible,
            key=lambda row: (
                float(row["total_capacity_MW"]),
                float(row["annual_unit_cost_yuan_per_t"]),
                float(row["wind_capacity_MW"]),
                float(row["pv_capacity_MW"]),
            ),
        )
    if objective == "min_cost":
        return min(
            feasible,
            key=lambda row: (
                float(row["annual_unit_cost_yuan_per_t"]),
                float(row["total_capacity_MW"]),
            ),
        )
    raise ValueError(f"unknown objective: {objective}")


def search_capacity_grid(production_target_t: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search wind/PV capacity pairs and report minimum-capacity and minimum-cost choices."""
    target_types = ["basic_autonomy", "production_autonomy", "full_production_autonomy"]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()

    def evaluate_grid(wind_values: list[float], pv_values: list[float]) -> None:
        for wind_capacity in wind_values:
            for pv_capacity in pv_values:
                key = (round(wind_capacity, 6), round(pv_capacity, 6))
                if key in seen:
                    continue
                seen.add(key)
                _, _, summary = dispatch_offgrid_no_storage_for_capacity(wind_capacity, pv_capacity)
                for target_type in target_types:
                    feasible = _target_feasible(summary, target_type, production_target_t)
                    rows.append(
                        _capacity_result_row(
                            target_type,
                            wind_capacity,
                            pv_capacity,
                            summary,
                            feasible,
                            objective_value=wind_capacity + pv_capacity,
                        )
                    )

    coarse_wind = _range_values(WIND_CAPACITY_MW, 240.0, 5.0)
    coarse_pv = _range_values(PV_CAPACITY_MW, 360.0, 5.0)
    evaluate_grid(coarse_wind, coarse_pv)

    coarse_best = {
        "basic_autonomy_min_capacity": _select_best(rows, "basic_autonomy", "min_capacity"),
        "production_autonomy_min_capacity": _select_best(rows, "production_autonomy", "min_capacity"),
        "production_autonomy_min_cost": _select_best(rows, "production_autonomy", "min_cost"),
        "optional_full_production_autonomy": _select_best(rows, "full_production_autonomy", "min_capacity"),
    }

    for best in coarse_best.values():
        if best is None:
            continue
        wind = float(best["wind_capacity_MW"])
        pv = float(best["pv_capacity_MW"])
        refine_wind = _range_values(max(WIND_CAPACITY_MW, wind - 5.0), min(260.0, wind + 5.0), 1.0)
        refine_pv = _range_values(max(PV_CAPACITY_MW, pv - 5.0), min(380.0, pv + 5.0), 1.0)
        evaluate_grid(refine_wind, refine_pv)

    results = {
        "basic_autonomy_min_capacity": _select_best(rows, "basic_autonomy", "min_capacity"),
        "production_autonomy_min_capacity": _select_best(rows, "production_autonomy", "min_capacity"),
        "production_autonomy_min_cost": _select_best(rows, "production_autonomy", "min_cost"),
        "optional_full_production_autonomy": _select_best(rows, "full_production_autonomy", "min_capacity"),
        "search_range": {
            "coarse_wind_MW": [WIND_CAPACITY_MW, 240.0, 5.0],
            "coarse_pv_MW": [PV_CAPACITY_MW, 360.0, 5.0],
            "refine_step_MW": 1.0,
        },
    }
    return rows, results


def _robust_grid_row(
    wind_capacity: float,
    pv_capacity: float,
    summary: dict[str, Any],
    feasible: bool,
    daily_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "target_type": "robust_daily_36t",
        "wind_capacity_MW": _round(wind_capacity),
        "pv_capacity_MW": _round(pv_capacity),
        "total_capacity_MW": _round(wind_capacity + pv_capacity),
        "annual_NH3_t": summary["annual_total_NH3_t"],
        "annual_load_shed_MWh": summary["annual_load_shed_MWh"],
        "annual_curtail_MWh": summary["annual_curtail_MWh"],
        "annual_curtailment_ratio": summary["annual_curtailment_ratio"],
        "annual_unit_cost_yuan_per_t": summary["annual_unit_cost_yuan_per_t"],
        "annual_plant_utilization": summary["annual_plant_utilization"],
        "feasible": 1 if feasible else 0,
        "objective_value": _round(wind_capacity + pv_capacity),
        "min_daily_NH3_t": _round(min(float(row["daily_NH3_t"]) for row in daily_rows)),
        "max_daily_load_shed_MWh": _round(max(float(row["daily_load_shed_MWh"]) for row in daily_rows)),
    }


def _select_best_robust(rows: list[dict[str, Any]], objective: str) -> dict[str, Any] | None:
    feasible = [row for row in rows if int(row["feasible"]) == 1]
    if not feasible:
        return None
    if objective == "min_capacity":
        return min(
            feasible,
            key=lambda row: (
                float(row["total_capacity_MW"]),
                float(row["annual_unit_cost_yuan_per_t"]),
                float(row["wind_capacity_MW"]),
                float(row["pv_capacity_MW"]),
            ),
        )
    if objective == "min_cost":
        return min(
            feasible,
            key=lambda row: (
                float(row["annual_unit_cost_yuan_per_t"]),
                float(row["total_capacity_MW"]),
            ),
        )
    raise ValueError(f"unknown robust objective: {objective}")


def search_capacity_grid_robust() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Grid-search a single capacity pair that satisfies all 24 scenarios daily."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()

    def evaluate_grid(wind_values: list[float], pv_values: list[float]) -> None:
        for wind_capacity in wind_values:
            for pv_capacity in pv_values:
                key = (round(wind_capacity, 6), round(pv_capacity, 6))
                if key in seen:
                    continue
                seen.add(key)
                _, daily_rows, summary = dispatch_offgrid_no_storage_for_capacity(wind_capacity, pv_capacity)
                rows.append(_robust_grid_row(wind_capacity, pv_capacity, summary, _robust_feasible(daily_rows), daily_rows))

    coarse_wind = _range_values(WIND_CAPACITY_MW, 240.0, 5.0)
    coarse_pv = _range_values(PV_CAPACITY_MW, 360.0, 5.0)
    evaluate_grid(coarse_wind, coarse_pv)

    coarse_best = {
        "robust_daily_36t_min_capacity": _select_best_robust(rows, "min_capacity"),
        "robust_daily_36t_min_cost": _select_best_robust(rows, "min_cost"),
    }
    for best in coarse_best.values():
        if best is None:
            continue
        wind = float(best["wind_capacity_MW"])
        pv = float(best["pv_capacity_MW"])
        refine_wind = _range_values(max(WIND_CAPACITY_MW, wind - 5.0), min(260.0, wind + 5.0), 1.0)
        refine_pv = _range_values(max(PV_CAPACITY_MW, pv - 5.0), min(380.0, pv + 5.0), 1.0)
        evaluate_grid(refine_wind, refine_pv)

    return rows, {
        "robust_daily_36t_min_capacity": _select_best_robust(rows, "min_capacity"),
        "robust_daily_36t_min_cost": _select_best_robust(rows, "min_cost"),
        "criterion": "all 24 scenarios: daily_load_shed_MWh <= 1e-5 and daily_NH3_t >= 36",
    }


def _autonomy_constraints(required_plant_power_mw: float) -> list[tuple[float, float, float, str, int]]:
    constraints: list[tuple[float, float, float, str, int]] = []
    for profile in _load_base_profiles():
        for hour, (wind_pu, pv_pu, load) in enumerate(
            zip(profile["wind_pu"], profile["pv_pu"], profile["load_MW"])
        ):
            constraints.append(
                (
                    float(wind_pu),
                    float(pv_pu),
                    float(load) + required_plant_power_mw,
                    str(profile["scenario_id"]),
                    hour,
                )
            )
    return constraints


def _min_margin_for_capacity(wind_capacity_mw: float, pv_capacity_mw: float, constraints: list[tuple[float, float, float, str, int]]) -> float:
    return min(
        wind_capacity_mw * wind_pu + pv_capacity_mw * pv_pu - demand
        for wind_pu, pv_pu, demand, _, _ in constraints
    )


def _fixed_ratio_capacity_for_constraints(constraints: list[tuple[float, float, float, str, int]]) -> tuple[float, float]:
    required_k = 0.0
    for wind_pu, pv_pu, demand, scenario_id, hour in constraints:
        available_per_k = WIND_CAPACITY_MW * wind_pu + PV_CAPACITY_MW * pv_pu
        if available_per_k <= 1e-12:
            if demand > 1e-9:
                raise RuntimeError(f"fixed-ratio autonomy infeasible at {scenario_id} hour {hour}: no wind/PV output")
            continue
        required_k = max(required_k, demand / available_per_k)
    return max(required_k, 1.0), required_k


def _grid_capacity_for_constraints(
    constraints: list[tuple[float, float, float, str, int]],
    wind_step_mw: float = 0.1,
) -> tuple[float, float]:
    min_wind_required = WIND_CAPACITY_MW
    for wind_pu, pv_pu, demand, scenario_id, hour in constraints:
        if pv_pu <= 1e-12:
            if wind_pu <= 1e-12:
                if demand > 1e-9:
                    raise RuntimeError(f"grid autonomy infeasible at {scenario_id} hour {hour}: no wind/PV output")
                continue
            min_wind_required = max(min_wind_required, demand / wind_pu)

    wind_max = max(min_wind_required + 10.0, WIND_CAPACITY_MW + 10.0)
    best: tuple[float, float, float] | None = None
    steps = int((wind_max - WIND_CAPACITY_MW) / wind_step_mw) + 2
    for index in range(steps):
        wind_capacity = WIND_CAPACITY_MW + index * wind_step_mw
        if wind_capacity + 1e-9 < min_wind_required:
            continue
        pv_required = PV_CAPACITY_MW
        feasible = True
        for wind_pu, pv_pu, demand, _, _ in constraints:
            remaining = demand - wind_capacity * wind_pu
            if remaining <= 0:
                continue
            if pv_pu <= 1e-12:
                feasible = False
                break
            pv_required = max(pv_required, remaining / pv_pu)
        if not feasible:
            continue
        pv_capacity = max(PV_CAPACITY_MW, pv_required)
        total_capacity = wind_capacity + pv_capacity
        if best is None or total_capacity < best[0] - 1e-9:
            best = (total_capacity, wind_capacity, pv_capacity)

    if best is None:
        raise RuntimeError("grid autonomy search did not find a feasible capacity pair")
    return best[1], best[2]


def _autonomy_level_row(
    autonomy_level: str,
    method: str,
    wind_capacity_mw: float,
    pv_capacity_mw: float,
    constraints: list[tuple[float, float, float, str, int]],
    note: str,
) -> dict[str, Any]:
    _, _, summary = dispatch_offgrid_no_storage_for_capacity(wind_capacity_mw, pv_capacity_mw)
    total_capacity = wind_capacity_mw + pv_capacity_mw
    scale_k = wind_capacity_mw / WIND_CAPACITY_MW if method == "fixed_ratio" else None
    return {
        "autonomy_level": autonomy_level,
        "method": method,
        "scale_k": _round(scale_k),
        "wind_capacity_MW": _round(wind_capacity_mw),
        "pv_capacity_MW": _round(pv_capacity_mw),
        "total_capacity_MW": _round(total_capacity),
        "added_wind_MW": _round(wind_capacity_mw - WIND_CAPACITY_MW),
        "added_pv_MW": _round(pv_capacity_mw - PV_CAPACITY_MW),
        "added_total_MW": _round(total_capacity - ORIGINAL_TOTAL_CAPACITY_MW),
        "increase_ratio": _round(total_capacity / ORIGINAL_TOTAL_CAPACITY_MW),
        "min_hourly_margin_MW": _round(_min_margin_for_capacity(wind_capacity_mw, pv_capacity_mw, constraints)),
        "annual_NH3_t": summary["annual_total_NH3_t"],
        "annual_curtail_MWh": summary["annual_curtail_MWh"],
        "annual_unit_cost_yuan_per_t": summary["annual_unit_cost_yuan_per_t"],
        "feasible": 1,
        "note": note,
    }


def estimate_autonomy_levels_from_original_capacity() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "baseline_capacity": {
            "wind_capacity_MW": WIND_CAPACITY_MW,
            "pv_capacity_MW": PV_CAPACITY_MW,
            "total_capacity_MW": ORIGINAL_TOTAL_CAPACITY_MW,
        }
    }
    for level, info in AUTONOMY_LEVELS.items():
        constraints = _autonomy_constraints(float(info["plant_power_MW"]))

        k, _ = _fixed_ratio_capacity_for_constraints(constraints)
        fixed_wind = WIND_CAPACITY_MW * k
        fixed_pv = PV_CAPACITY_MW * k
        fixed_row = _autonomy_level_row(
            level,
            "fixed_ratio",
            fixed_wind,
            fixed_pv,
            constraints,
            str(info["note"]),
        )

        grid_wind, grid_pv = _grid_capacity_for_constraints(constraints)
        grid_row = _autonomy_level_row(
            level,
            "min_added_capacity_grid",
            grid_wind,
            grid_pv,
            constraints,
            str(info["note"]),
        )

        rows.extend([fixed_row, grid_row])
        summary[level] = {
            "fixed_ratio": fixed_row,
            "min_added_capacity_grid": grid_row,
        }
    return rows, summary


def _storage_var(base: int, hour: int) -> int:
    return base + hour


def simulate_offgrid_with_storage_for_candidate(
    scenario: dict[str, Any],
    storage_power_mw: float,
    storage_energy_mwh: float,
    storage_params: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """MILP dispatch for one scenario with fixed storage power and energy."""
    if storage_power_mw <= 1e-9 or storage_energy_mwh <= 1e-9:
        hourly, daily = solve_offgrid_no_storage(scenario)
        storage_hourly = []
        for row in hourly:
            storage_hourly.append(
                {
                    "scenario_id": row["scenario_id"],
                    "hour": row["hour"],
                    "P_wind_MW": row["P_wind_MW"],
                    "P_pv_MW": row["P_pv_MW"],
                    "P_re_MW": row["P_re_MW"],
                    "P_load_MW": row["P_load_MW"],
                    "P_load_served_MW": row["P_load_served_MW"],
                    "P_load_shed_MW": row["P_load_shed_MW"],
                    "P_charge_MW": 0.0,
                    "P_discharge_MW": 0.0,
                    "SOC_MWh": 0.0,
                    "plant_load_ratio": row["plant_load_ratio"],
                    "plant_on": row["plant_on"],
                    "P_plant_MW": row["P_plant_MW"],
                    "NH3_t": row["NH3_t"],
                    "P_curtail_MW": row["P_curtail_MW"],
                    "cost_yuan": row["cost_yuan"],
                }
            )
        storage_daily = _summarize_storage_daily(storage_hourly)
        storage_daily["SOC_initial_MWh"] = 0.0
        storage_daily["SOC_final_MWh"] = 0.0
        return storage_hourly, storage_daily

    scenario_id = str(scenario["scenario_id"])
    p_load = [float(value) for value in scenario["load_MW"]]
    p_wind = [float(value) for value in scenario["wind_MW"]]
    p_pv = [float(value) for value in scenario["pv_MW"]]
    p_re = [wind + pv for wind, pv in zip(p_wind, p_pv)]

    idx_r = 0
    idx_on = 24
    idx_charge = 48
    idx_discharge = 72
    idx_soc = 96
    idx_curtail = 121
    idx_shed = 145
    idx_charge_mode = 169
    n_vars = 193

    c = np.zeros(n_vars)
    lower = np.zeros(n_vars)
    upper = np.full(n_vars, np.inf)
    integrality = np.zeros(n_vars)
    for hour in range(N_HOURS):
        c[_storage_var(idx_r, hour)] = -300000.0
        c[_storage_var(idx_curtail, hour)] = 1000.0
        c[_storage_var(idx_shed, hour)] = 10000000.0
        c[_storage_var(idx_discharge, hour)] = 1000.0 * float(storage_params["opex_yuan_per_kWh"])
        upper[_storage_var(idx_r, hour)] = 1.0
        upper[_storage_var(idx_on, hour)] = 1.0
        integrality[_storage_var(idx_on, hour)] = 1.0
        upper[_storage_var(idx_charge, hour)] = storage_power_mw
        upper[_storage_var(idx_discharge, hour)] = storage_power_mw
        upper[_storage_var(idx_curtail, hour)] = max(p_re[hour] + storage_power_mw, 0.0)
        upper[_storage_var(idx_shed, hour)] = p_load[hour]
        upper[_storage_var(idx_charge_mode, hour)] = 1.0
        integrality[_storage_var(idx_charge_mode, hour)] = 1.0
    for hour in range(N_HOURS + 1):
        upper[_storage_var(idx_soc, hour)] = storage_energy_mwh

    a_eq: list[np.ndarray] = []
    b_eq: list[float] = []
    a_ub: list[np.ndarray] = []
    b_ub: list[float] = []
    eta_ch = float(storage_params["charge_efficiency"])
    eta_dis = float(storage_params["discharge_efficiency"])
    loss = float(storage_params["self_loss_rate_per_hour"])
    initial_soc = 0.5 * storage_energy_mwh

    row = np.zeros(n_vars)
    row[_storage_var(idx_soc, 0)] = 1.0
    a_eq.append(row)
    b_eq.append(initial_soc)
    row = np.zeros(n_vars)
    row[_storage_var(idx_soc, N_HOURS)] = 1.0
    a_eq.append(row)
    b_eq.append(initial_soc)

    for hour in range(N_HOURS):
        balance = np.zeros(n_vars)
        balance[_storage_var(idx_r, hour)] = PLANT_FULL_MW
        balance[_storage_var(idx_charge, hour)] = 1.0
        balance[_storage_var(idx_discharge, hour)] = -1.0
        balance[_storage_var(idx_curtail, hour)] = 1.0
        balance[_storage_var(idx_shed, hour)] = -1.0
        a_eq.append(balance)
        b_eq.append(p_re[hour] - p_load[hour])

        soc = np.zeros(n_vars)
        soc[_storage_var(idx_soc, hour + 1)] = 1.0
        soc[_storage_var(idx_soc, hour)] = -(1.0 - loss)
        soc[_storage_var(idx_charge, hour)] = -eta_ch
        soc[_storage_var(idx_discharge, hour)] = 1.0 / eta_dis
        a_eq.append(soc)
        b_eq.append(0.0)

        on_upper = np.zeros(n_vars)
        on_upper[_storage_var(idx_r, hour)] = 1.0
        on_upper[_storage_var(idx_on, hour)] = -1.0
        a_ub.append(on_upper)
        b_ub.append(0.0)

        on_lower = np.zeros(n_vars)
        on_lower[_storage_var(idx_r, hour)] = -1.0
        on_lower[_storage_var(idx_on, hour)] = MIN_RUNNING_RATIO
        a_ub.append(on_lower)
        b_ub.append(0.0)

        charge_limit = np.zeros(n_vars)
        charge_limit[_storage_var(idx_charge, hour)] = 1.0
        charge_limit[_storage_var(idx_charge_mode, hour)] = -storage_power_mw
        a_ub.append(charge_limit)
        b_ub.append(0.0)

        discharge_limit = np.zeros(n_vars)
        discharge_limit[_storage_var(idx_discharge, hour)] = 1.0
        discharge_limit[_storage_var(idx_charge_mode, hour)] = storage_power_mw
        a_ub.append(discharge_limit)
        b_ub.append(storage_power_mw)

    constraints = []
    if a_eq:
        constraints.append(LinearConstraint(np.vstack(a_eq), np.array(b_eq), np.array(b_eq)))
    if a_ub:
        constraints.append(LinearConstraint(np.vstack(a_ub), -np.inf, np.array(b_ub)))

    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=constraints,
        options={"time_limit": 20.0, "mip_rel_gap": 1e-6},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"storage MILP failed for {scenario_id}: {result.message}")

    x = result.x
    hourly: list[dict[str, Any]] = []
    for hour in range(N_HOURS):
        ratio = max(float(x[_storage_var(idx_r, hour)]), 0.0)
        plant_on = int(round(float(x[_storage_var(idx_on, hour)])))
        p_charge = max(float(x[_storage_var(idx_charge, hour)]), 0.0)
        p_discharge = max(float(x[_storage_var(idx_discharge, hour)]), 0.0)
        p_curtail = max(float(x[_storage_var(idx_curtail, hour)]), 0.0)
        p_shed = max(float(x[_storage_var(idx_shed, hour)]), 0.0)
        p_plant = PLANT_FULL_MW * ratio
        p_load_served = p_load[hour] - p_shed
        p_alk = ALK_FULL_MW * ratio
        p_pem = PEM_FULL_MW * ratio
        p_nh3 = NH3_FULL_MW * ratio
        nh3_t = NH3_FULL_TPH * ratio
        cost = _hourly_cost_yuan(p_wind[hour], p_pv[hour], p_alk, p_pem, p_nh3)
        cost += 1000.0 * float(storage_params["opex_yuan_per_kWh"]) * p_discharge
        hourly.append(
            {
                "scenario_id": scenario_id,
                "hour": hour,
                "P_wind_MW": p_wind[hour],
                "P_pv_MW": p_pv[hour],
                "P_re_MW": p_re[hour],
                "P_load_MW": p_load[hour],
                "P_load_served_MW": p_load_served,
                "P_load_shed_MW": p_shed,
                "P_charge_MW": p_charge,
                "P_discharge_MW": p_discharge,
                "SOC_MWh": max(float(x[_storage_var(idx_soc, hour)]), 0.0),
                "plant_load_ratio": ratio,
                "plant_on": plant_on,
                "P_plant_MW": p_plant,
                "NH3_t": nh3_t,
                "P_curtail_MW": p_curtail,
                "cost_yuan": cost,
            }
        )
    daily = _summarize_storage_daily(hourly)
    daily["SOC_initial_MWh"] = max(float(x[_storage_var(idx_soc, 0)]), 0.0)
    daily["SOC_final_MWh"] = max(float(x[_storage_var(idx_soc, N_HOURS)]), 0.0)
    return hourly, daily


def _summarize_storage_daily(hourly: list[dict[str, Any]]) -> dict[str, Any]:
    daily_re = sum(float(row["P_re_MW"]) for row in hourly)
    daily_curtail = sum(float(row["P_curtail_MW"]) for row in hourly)
    daily_nh3 = sum(float(row["NH3_t"]) for row in hourly)
    daily_shed = sum(float(row["P_load_shed_MW"]) for row in hourly)
    daily_charge = sum(float(row["P_charge_MW"]) for row in hourly)
    daily_discharge = sum(float(row["P_discharge_MW"]) for row in hourly)
    daily_cost = sum(float(row["cost_yuan"]) for row in hourly) + NH3_FIXED_CAPEX_DAILY_YUAN
    return {
        "scenario_id": hourly[0]["scenario_id"],
        "daily_re_MWh": daily_re,
        "daily_NH3_t": daily_nh3,
        "daily_curtail_MWh": daily_curtail,
        "curtailment_ratio": daily_curtail / daily_re if daily_re > 1e-9 else 0.0,
        "daily_load_shed_MWh": daily_shed,
        "daily_storage_charge_MWh": daily_charge,
        "daily_storage_discharge_MWh": daily_discharge,
        "SOC_initial_MWh": None,
        "SOC_final_MWh": None,
        "daily_cost_yuan": daily_cost,
        "daily_nh3_fixed_capex_yuan": NH3_FIXED_CAPEX_DAILY_YUAN,
        "unit_cost_yuan_per_t": daily_cost / daily_nh3 if daily_nh3 > 1e-9 else None,
        "plant_utilization": daily_nh3 / DAILY_CAPACITY_T,
    }


def _storage_daily_capex_yuan(storage_energy_mwh: float, storage_params: dict[str, Any]) -> float:
    return (
        storage_energy_mwh
        * 1000.0
        * float(storage_params["capex_yuan_per_kWh"])
        / (float(storage_params["lifetime_years"]) * ANNUAL_DAYS)
    )


def search_storage_config_for_max_curtailment_scene(
    storage_params: dict[str, Any],
    offgrid_daily_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_daily = {row["scenario_id"]: row for row in offgrid_daily_rows}["W4_P1"]
    max_curtail = float(base_daily["daily_curtail_MWh"])
    power_values = [0.0] + [float(v) for v in range(5, 55, 5)]
    durations = [1.0, 2.0, 4.0, 6.0]
    candidates: list[dict[str, Any]] = []
    scenario = [s for s in load_p4_inputs() if s["scenario_id"] == "W4_P1"][0]
    candidate_id = 0
    for power in power_values:
        energy_values = [0.0] if power <= 1e-9 else [power * duration for duration in durations if power * duration <= max_curtail * 1.25]
        for energy in energy_values:
            candidate_id += 1
            hourly, daily = simulate_offgrid_with_storage_for_candidate(scenario, power, energy, storage_params)
            storage_daily_cost = _storage_daily_capex_yuan(energy, storage_params)
            storage_daily_cost += 1000.0 * float(storage_params["opex_yuan_per_kWh"]) * float(daily["daily_storage_discharge_MWh"])
            total_cost = float(daily["daily_cost_yuan"]) + _storage_daily_capex_yuan(energy, storage_params)
            nh3 = float(daily["daily_NH3_t"])
            curtail_reduction = float(base_daily["daily_curtail_MWh"]) - float(daily["daily_curtail_MWh"])
            nh3_increase = nh3 - float(base_daily["daily_NH3_t"])
            incremental_cost = total_cost - float(base_daily["daily_cost_yuan"])
            candidates.append(
                {
                    "candidate_id": f"S{candidate_id:03d}",
                    "storage_power_MW": power,
                    "storage_energy_MWh": energy,
                    "duration_h": energy / power if power > 1e-9 else 0.0,
                    "W4_P1_NH3_t": nh3,
                    "W4_P1_curtail_MWh": daily["daily_curtail_MWh"],
                    "W4_P1_load_shed_MWh": daily["daily_load_shed_MWh"],
                    "W4_P1_cost_yuan": total_cost,
                    "W4_P1_unit_cost_yuan_per_t": total_cost / nh3 if nh3 > 1e-9 else None,
                    "storage_daily_cost_yuan": storage_daily_cost,
                    "curtail_reduction_MWh": curtail_reduction,
                    "NH3_increase_t": nh3_increase,
                    "incremental_cost_yuan": incremental_cost,
                    "recommended_flag": 0,
                    "recommendation_reason": "",
                }
            )

    nonzero = [row for row in candidates if float(row["storage_energy_MWh"]) > 1e-9 and float(row["NH3_increase_t"]) > 1e-6]
    min_unit = min(candidates, key=lambda row: float(row["W4_P1_unit_cost_yuan_per_t"] or 1e18))
    max_curtail_row = max(candidates, key=lambda row: (float(row["curtail_reduction_MWh"]), float(row["NH3_increase_t"])))
    efficient = min(
        nonzero,
        key=lambda row: (
            max(float(row["incremental_cost_yuan"]), 0.0) / max(float(row["NH3_increase_t"]), 1e-9),
            -float(row["curtail_reduction_MWh"]),
        ),
    ) if nonzero else min_unit

    # Keep a dual-scheme interpretation: economic compromise vs absorption-oriented.
    economic_recommended = efficient if float(efficient["storage_energy_MWh"]) > 1e-9 else min_unit
    absorption_recommended = max_curtail_row
    for row in candidates:
        reasons = []
        if row["candidate_id"] == min_unit["candidate_id"]:
            reasons.append("minimum_unit_cost")
        if row["candidate_id"] == max_curtail_row["candidate_id"]:
            reasons.append("maximum_curtailment_reduction")
            reasons.append("absorption_oriented_solution")
        if row["candidate_id"] == efficient["candidate_id"]:
            reasons.append("best_incremental_cost_per_added_NH3")
        if row["candidate_id"] == economic_recommended["candidate_id"]:
            row["recommended_flag"] = 1
            reasons.append("economic_compromise_solution")
        row["recommendation_reason"] = ";".join(reasons)

    def scheme(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "candidate_id": row["candidate_id"],
            "storage_power_MW": row["storage_power_MW"],
            "storage_energy_MWh": row["storage_energy_MWh"],
            "duration_h": row["duration_h"],
            "W4_P1_after": {
                "daily_NH3_t": row["W4_P1_NH3_t"],
                "daily_curtail_MWh": row["W4_P1_curtail_MWh"],
                "daily_load_shed_MWh": row["W4_P1_load_shed_MWh"],
                "daily_cost_yuan": row["W4_P1_cost_yuan"],
                "unit_cost_yuan_per_t": row["W4_P1_unit_cost_yuan_per_t"],
            },
            "curtail_reduction_MWh": row["curtail_reduction_MWh"],
            "NH3_increase_t": row["NH3_increase_t"],
            "cost_change_yuan": row["incremental_cost_yuan"],
            "unit_cost_change_yuan_per_t": (row["W4_P1_unit_cost_yuan_per_t"] or 0.0) - float(base_daily["unit_cost_yuan_per_t"]),
        }

    best_config = {
        "selected_storage_power_MW": economic_recommended["storage_power_MW"],
        "selected_storage_energy_MWh": economic_recommended["storage_energy_MWh"],
        "duration_h": economic_recommended["duration_h"],
        "selected_scheme": "economic_compromise",
        "selection_rule": "dual scheme: economic_compromise minimizes unit/incremental production cost; absorption_oriented maximizes W4_P1 curtailment reduction",
        "W4_P1_before": {
            "daily_NH3_t": base_daily["daily_NH3_t"],
            "daily_curtail_MWh": base_daily["daily_curtail_MWh"],
            "daily_load_shed_MWh": base_daily["daily_load_shed_MWh"],
            "daily_cost_yuan": base_daily["daily_cost_yuan"],
            "unit_cost_yuan_per_t": base_daily["unit_cost_yuan_per_t"],
        },
        "W4_P1_after": {
            "daily_NH3_t": economic_recommended["W4_P1_NH3_t"],
            "daily_curtail_MWh": economic_recommended["W4_P1_curtail_MWh"],
            "daily_load_shed_MWh": economic_recommended["W4_P1_load_shed_MWh"],
            "daily_cost_yuan": economic_recommended["W4_P1_cost_yuan"],
            "unit_cost_yuan_per_t": economic_recommended["W4_P1_unit_cost_yuan_per_t"],
        },
        "curtail_reduction_MWh": economic_recommended["curtail_reduction_MWh"],
        "NH3_increase_t": economic_recommended["NH3_increase_t"],
        "cost_change_yuan": economic_recommended["incremental_cost_yuan"],
        "unit_cost_change_yuan_per_t": (economic_recommended["W4_P1_unit_cost_yuan_per_t"] or 0.0) - float(base_daily["unit_cost_yuan_per_t"]),
        "economic_compromise_config": scheme(economic_recommended),
        "absorption_oriented_config": scheme(absorption_recommended),
        "storage_cost_assumptions": storage_params,
        "candidate_benchmarks": {
            "minimum_unit_cost": min_unit["candidate_id"],
            "maximum_curtailment_reduction": max_curtail_row["candidate_id"],
            "best_incremental_cost_per_added_NH3": efficient["candidate_id"],
        },
    }
    return candidates, best_config


def dispatch_all_scenarios_with_storage(
    storage_power_mw: float,
    storage_energy_mwh: float,
    storage_params: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    hourly_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for scenario in load_p4_inputs():
        hourly, daily = simulate_offgrid_with_storage_for_candidate(
            scenario,
            storage_power_mw,
            storage_energy_mwh,
            storage_params,
        )
        hourly_rows.extend(hourly)
        daily_rows.append(daily)
    summary = summarize_storage_results(daily_rows, storage_power_mw, storage_energy_mwh, storage_params)
    return hourly_rows, daily_rows, summary


def summarize_storage_results(
    daily_rows: list[dict[str, Any]],
    storage_power_mw: float,
    storage_energy_mwh: float,
    storage_params: dict[str, Any],
) -> dict[str, Any]:
    annual_re = sum(float(row["daily_re_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_nh3 = sum(float(row["daily_NH3_t"]) * SCENARIO_DAYS for row in daily_rows)
    annual_curtail = sum(float(row["daily_curtail_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_shed = sum(float(row["daily_load_shed_MWh"]) * SCENARIO_DAYS for row in daily_rows)
    annual_dispatch_cost = sum(float(row["daily_cost_yuan"]) * SCENARIO_DAYS for row in daily_rows)
    annual_storage_capex = storage_energy_mwh * 1000.0 * float(storage_params["capex_yuan_per_kWh"]) / float(storage_params["lifetime_years"])
    annual_total_cost = annual_dispatch_cost + annual_storage_capex
    no_storage = json.loads((RESULT_DIR / "p4_offgrid_summary.json").read_text(encoding="utf-8"))
    return {
        "selected_storage_config": {
            "storage_power_MW": _round(storage_power_mw),
            "storage_energy_MWh": _round(storage_energy_mwh),
            "duration_h": _round(storage_energy_mwh / storage_power_mw if storage_power_mw > 1e-9 else 0.0),
        },
        "annual_total_NH3_t": _round(annual_nh3),
        "annual_dispatch_cost_yuan": _round(annual_dispatch_cost),
        "annual_storage_capex_yuan": _round(annual_storage_capex),
        "annual_total_cost_yuan": _round(annual_total_cost),
        "annual_unit_cost_yuan_per_t": _round(annual_total_cost / annual_nh3 if annual_nh3 > 1e-9 else None),
        "annual_plant_utilization": _round(annual_nh3 / (DAILY_CAPACITY_T * ANNUAL_DAYS)),
        "annual_curtail_MWh": _round(annual_curtail),
        "annual_curtailment_ratio": _round(annual_curtail / annual_re if annual_re > 1e-9 else 0.0),
        "annual_load_shed_MWh": _round(annual_shed),
        "improvement_vs_no_storage": {
            "annual_NH3_increase_t": _round(annual_nh3 - float(no_storage["annual_total_NH3_t"])),
            "annual_curtail_reduction_MWh": _round(float(no_storage["annual_curtail_MWh"]) - annual_curtail),
            "annual_load_shed_reduction_MWh": _round(float(no_storage["annual_load_shed_MWh"]) - annual_shed),
            "unit_cost_change_yuan_per_t": _round((annual_total_cost / annual_nh3) - float(no_storage["annual_unit_cost_yuan_per_t"]) if annual_nh3 > 1e-9 else None),
        },
        "days_per_scenario": SCENARIO_DAYS,
        "annual_days": ANNUAL_DAYS,
    }


def write_storage_results(
    candidates: list[dict[str, Any]],
    best_config: dict[str, Any],
    hourly_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    storage_summary: dict[str, Any],
) -> None:
    with (RESULT_DIR / "p4_storage_config_candidates.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STORAGE_CANDIDATE_FIELDS)
        writer.writeheader()
        for row in candidates:
            writer.writerow({field: _csv_value(row.get(field)) for field in STORAGE_CANDIDATE_FIELDS})

    with (RESULT_DIR / "p4_storage_best_config.json").open("w", encoding="utf-8") as f:
        json.dump(best_config, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with (RESULT_DIR / "p4_storage_hourly_cases.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STORAGE_HOURLY_FIELDS)
        writer.writeheader()
        for row in hourly_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STORAGE_HOURLY_FIELDS})

    with (RESULT_DIR / "p4_storage_daily_cases.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STORAGE_DAILY_FIELDS)
        writer.writeheader()
        for row in daily_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STORAGE_DAILY_FIELDS})

    with (RESULT_DIR / "p4_storage_summary.json").open("w", encoding="utf-8") as f:
        json.dump(storage_summary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def summarize_capacity_search(
    base_summary: dict[str, Any],
    fixed_results: dict[str, Any],
    grid_results: dict[str, Any],
    scenario_requirement_results: dict[str, Any],
    robust_grid_results: dict[str, Any],
    autonomy_level_results: dict[str, Any],
    production_target_t: float,
) -> dict[str, Any]:
    annual_results = {
        "fixed_ratio_results": {
            "basic_autonomy": fixed_results.get("basic_autonomy"),
            "production_autonomy": fixed_results.get("production_autonomy"),
            "optional_full_production_autonomy": fixed_results.get("full_production_autonomy"),
        },
        "grid_search_results": grid_results,
    }
    robust_results = {
        "scenario_fixed_ratio_requirements": {
            "basic_autonomy": scenario_requirement_results["fixed_ratio_basic_autonomy"],
            "daily_36t": scenario_requirement_results["fixed_ratio_daily_36t"],
        },
        "grid_search_results": robust_grid_results,
    }
    return {
        "base_case_capacity": {
            "wind_capacity_MW": WIND_CAPACITY_MW,
            "pv_capacity_MW": PV_CAPACITY_MW,
            "annual_total_NH3_t": base_summary["annual_total_NH3_t"],
            "annual_load_shed_MWh": base_summary["annual_load_shed_MWh"],
            "annual_curtail_MWh": base_summary["annual_curtail_MWh"],
            "annual_unit_cost_yuan_per_t": base_summary["annual_unit_cost_yuan_per_t"],
            "annual_plant_utilization": base_summary["annual_plant_utilization"],
        },
        "autonomy_by_original_capacity_baseline": autonomy_level_results,
        "regular_load_autonomy": autonomy_level_results["regular_load_autonomy"],
        "minimum_operation_autonomy": autonomy_level_results["minimum_operation_autonomy"],
        "full_production_autonomy": autonomy_level_results["full_production_autonomy"],
        "comparison_to_original_capacity": {
            "original_wind_capacity_MW": WIND_CAPACITY_MW,
            "original_pv_capacity_MW": PV_CAPACITY_MW,
            "original_total_capacity_MW": ORIGINAL_TOTAL_CAPACITY_MW,
            "note": "added capacity is measured relative to the original 40 MW wind and 64 MW PV capacities",
        },
        "same_annual_production_as_p3": {
            "status": "supplementary_for_problem4_3",
            "target_annual_NH3_t": production_target_t,
            "annual_criterion_results": annual_results,
            "robust_daily_36t_results": robust_results,
            "note": "This is retained only for comparison with Problem 3 and is not the main criterion for Problem 4(1).",
        },
        "annual_criterion_results": annual_results,
        "robust_scenario_criterion_results": robust_results,
        "fixed_ratio_results": annual_results["fixed_ratio_results"],
        "grid_search_results": grid_results,
        "worst_case_scenario": scenario_requirement_results["worst_case_scenario"],
        "definition_notes": {
            "regular_load_autonomy": "all 24 scenarios and all hours satisfy P_re >= P_load",
            "minimum_operation_autonomy": "all 24 scenarios and all hours satisfy P_re >= P_load + 0.1*41.5",
            "full_production_autonomy": "all 24 scenarios and all hours satisfy P_re >= P_load + 41.5",
            "annual_basic_autonomy": "annual_load_shed_MWh <= 1e-5 after aggregating 24 scenarios, each representing 15 days",
            "annual_production_autonomy": f"annual basic autonomy plus annual_total_NH3_t >= {production_target_t}",
            "robust_basic_autonomy": "same fixed capacity pair must make every scenario daily_load_shed_MWh <= 1e-5",
            "robust_production_autonomy": f"robust basic autonomy plus every scenario daily_NH3_t >= {ROBUST_DAILY_PRODUCTION_T}",
            "optional_full_production_autonomy": f"annual basic autonomy plus annual_total_NH3_t >= {FULL_PRODUCTION_TARGET_T}",
            "dispatch_model": "off-grid, no storage, no purchase, no sale, 0.1 z_t <= r_t <= z_t",
        },
        "explanation": (
            "The main Problem 4(1) autonomy estimate is now based on the original 40 MW wind and 64 MW PV "
            "capacity baseline and checks all 24 scenarios and all hours. The old 12960 t annual production "
            "criterion is retained only as a comparison with Problem 3 because it aggregates scenarios over "
            "a 360-day year and does not directly express hourly energy autonomy."
        ),
        "recommendation": {
            "main_text": "For Problem 4(1), report regular_load_autonomy as the basic energy self-sufficiency capacity and full_production_autonomy as the upper-bound capacity required to fully support 72 t/d production. Keep the 12960 t result for Problem 4(3) economic comparison only.",
            "reason": "regular-load autonomy answers how much extra capacity is needed for basic park electricity self-sufficiency, while full-production autonomy shows that relying only on wind/PV expansion to guarantee 72 t/d production is extremely expensive.",
        },
    }


def write_capacity_results(
    fixed_rows: list[dict[str, Any]],
    grid_rows: list[dict[str, Any]],
    scenario_requirement_rows: list[dict[str, Any]],
    autonomy_level_rows: list[dict[str, Any]],
    capacity_summary: dict[str, Any],
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULT_DIR / "p4_capacity_fixed_ratio_search.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAPACITY_FIXED_FIELDS)
        writer.writeheader()
        for row in fixed_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CAPACITY_FIXED_FIELDS})

    with (RESULT_DIR / "p4_capacity_grid_search.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAPACITY_GRID_FIELDS)
        writer.writeheader()
        for row in grid_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CAPACITY_GRID_FIELDS})

    with (RESULT_DIR / "p4_capacity_scenario_requirements.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SCENARIO_REQUIREMENT_FIELDS)
        writer.writeheader()
        for row in scenario_requirement_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in SCENARIO_REQUIREMENT_FIELDS})

    with (RESULT_DIR / "p4_capacity_autonomy_levels.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=AUTONOMY_LEVEL_FIELDS)
        writer.writeheader()
        for row in autonomy_level_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in AUTONOMY_LEVEL_FIELDS})

    with (RESULT_DIR / "p4_capacity_autonomy_summary.json").open("w", encoding="utf-8") as f:
        json.dump(capacity_summary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_offgrid_results(
    hourly_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    with (RESULT_DIR / "p4_offgrid_hourly_cases.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HOURLY_FIELDS)
        writer.writeheader()
        for row in hourly_rows:
            writer.writerow({field: _csv_value(row[field]) for field in HOURLY_FIELDS})

    with (RESULT_DIR / "p4_offgrid_daily_cases.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DAILY_FIELDS)
        writer.writeheader()
        for row in daily_rows:
            writer.writerow({field: _csv_value(row[field]) for field in DAILY_FIELDS})

    with (RESULT_DIR / "p4_offgrid_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")

    write_p4_summary(summary)


def write_p4_summary(
    offgrid_summary: dict[str, Any],
    capacity_summary: dict[str, Any] | None = None,
    storage_summary: dict[str, Any] | None = None,
) -> None:
    p4_summary: dict[str, Any] = {
        "offgrid_no_storage": offgrid_summary,
        "storage": {"status": "pending", "note": "not implemented in stages B1/B1b"},
        "grid_offgrid_comparison": {"status": "pending", "note": "not implemented in stages B1/B1b"},
    }
    if capacity_summary is not None:
        p4_summary["capacity_autonomy_estimation"] = capacity_summary
    if storage_summary is not None:
        p4_summary["storage"] = {"status": "completed", "summary": storage_summary}
        p4_summary["storage_configuration"] = storage_summary
    with (RESULT_DIR / "p4_summary.json").open("w", encoding="utf-8") as f:
        json.dump(p4_summary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    production_target_t = _load_p3_production_target()
    hourly_rows, daily_rows, summary = dispatch_offgrid_no_storage_for_capacity(
        WIND_CAPACITY_MW,
        PV_CAPACITY_MW,
    )
    write_offgrid_results(hourly_rows, daily_rows, summary)

    fixed_rows, fixed_results = search_capacity_fixed_ratio(production_target_t)
    grid_rows, grid_results = search_capacity_grid(production_target_t)
    scenario_requirement_rows, scenario_requirement_results = search_capacity_scenario_requirements()
    robust_grid_rows, robust_grid_results = search_capacity_grid_robust()
    autonomy_level_rows, autonomy_level_results = estimate_autonomy_levels_from_original_capacity()
    combined_grid_rows = grid_rows + robust_grid_rows
    capacity_summary = summarize_capacity_search(
        summary,
        fixed_results,
        grid_results,
        scenario_requirement_results,
        robust_grid_results,
        autonomy_level_results,
        production_target_t,
    )
    write_capacity_results(fixed_rows, combined_grid_rows, scenario_requirement_rows, autonomy_level_rows, capacity_summary)
    storage_params = read_storage_params()
    candidates, best_config = search_storage_config_for_max_curtailment_scene(storage_params, daily_rows)
    selected = best_config["selected_storage_power_MW"], best_config["selected_storage_energy_MWh"]
    storage_hourly, storage_daily, storage_summary = dispatch_all_scenarios_with_storage(
        float(selected[0]),
        float(selected[1]),
        storage_params,
    )
    write_storage_results(candidates, best_config, storage_hourly, storage_daily, storage_summary)
    write_p4_summary(summary, capacity_summary, storage_summary)

    print("问题四离网无储能调度完成")
    print(f"年制氨总量: {summary['annual_total_NH3_t']} t")
    print(f"年吨氨成本: {summary['annual_unit_cost_yuan_per_t']} 元/t")
    print(f"最大弃电场景: {summary['max_curtailment_scenario_id']}")
    print("能源自治容量估算完成")


if __name__ == "__main__":
    main()
