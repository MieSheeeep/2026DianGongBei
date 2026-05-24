"""问题四：离网运行与储能配置。

执行：
  python support/code/p4_solve.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

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
    NH3_CAPACITY_MW,
    NH3_OPEX_YUAN_PER_KWH,
    NH3_RATE_TPH,
    PEM_CAPACITY_MW,
    PEM_OPEX_YUAN_PER_KWH,
)
from p2_solve import (  # noqa: E402
    PRODUCTION_LEVELS,
    PV_CAPACITY_MW,
    PV_LCOE_YUAN_PER_KWH,
    SCENARIO_DAYS,
    WIND_CAPACITY_MW,
    WIND_LCOE_YUAN_PER_KWH,
    build_combined_scenarios,
)

HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p4"
P3_RESULT_DIR = HERE.parent / "results" / "p3"

EXPANSION_FACTOR = 72.0 / 36.0
ALK_FULL_MW = ALK_CAPACITY_MW * EXPANSION_FACTOR
PEM_FULL_MW = PEM_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_MW = NH3_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_TPH = NH3_RATE_TPH * EXPANSION_FACTOR
P_FLEX_FULL_MW = ALK_FULL_MW + PEM_FULL_MW + NH3_FULL_MW
ALPHA_MIN = 0.1
ALPHA_MAX = 1.0
EPS = 1e-7
BIG_M = 300.0

HOURLY_FIELDS = [
    "scenario_id",
    "hour",
    "alpha",
    "run_status",
    "P_load_MW",
    "P_wind_MW",
    "P_pv_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "P_charge_MW",
    "P_discharge_MW",
    "E_storage_MWh",
    "P_curtail_MW",
    "P_unserved_MW",
    "NH3_t",
    "cost_yuan",
]

DAILY_FIELDS = [
    "scenario_id",
    "NH3_t_per_day",
    "run_hours",
    "avg_alpha",
    "E_wind_MWh",
    "E_pv_MWh",
    "E_re_MWh",
    "E_use_MWh",
    "E_load_MWh",
    "E_charge_MWh",
    "E_discharge_MWh",
    "E_curtail_MWh",
    "E_unserved_MWh",
    "storage_capacity_MWh",
    "daily_cost_yuan",
    "unit_cost_yuan_per_t",
    "capacity_utilization",
    "renewable_utilization",
]


def _round(value: float) -> float:
    return round(float(value), 6)


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _equipment_cost(alpha: float) -> float:
    return 1000.0 * (
        ALK_OPEX_YUAN_PER_KWH * ALK_FULL_MW
        + PEM_OPEX_YUAN_PER_KWH * PEM_FULL_MW
        + NH3_OPEX_YUAN_PER_KWH * NH3_FULL_MW
    ) * alpha


def _generation_cost(p_wind: float, p_pv: float) -> float:
    return 1000.0 * (WIND_LCOE_YUAN_PER_KWH * p_wind + PV_LCOE_YUAN_PER_KWH * p_pv)


def _no_storage_hour(scenario_id: str, hour: int, p_load: float, p_wind: float, p_pv: float, p_re: float) -> dict:
    surplus = p_re - p_load
    if surplus >= ALPHA_MIN * P_FLEX_FULL_MW:
        alpha = min(ALPHA_MAX, surplus / P_FLEX_FULL_MW)
        run_status = 1
    else:
        alpha = 0.0
        run_status = 0
    p_alk = ALK_FULL_MW * alpha
    p_pem = PEM_FULL_MW * alpha
    p_nh3 = NH3_FULL_MW * alpha
    p_use = p_load + p_alk + p_pem + p_nh3
    p_unserved = max(p_load - p_re, 0.0)
    p_curtail = max(p_re - p_use, 0.0)
    return {
        "scenario_id": scenario_id,
        "hour": hour,
        "alpha": _round(alpha),
        "run_status": run_status,
        "P_load_MW": _round(p_load),
        "P_wind_MW": _round(p_wind),
        "P_pv_MW": _round(p_pv),
        "P_re_MW": _round(p_re),
        "P_alk_MW": _round(p_alk),
        "P_pem_MW": _round(p_pem),
        "P_nh3_MW": _round(p_nh3),
        "P_charge_MW": 0.0,
        "P_discharge_MW": 0.0,
        "E_storage_MWh": 0.0,
        "P_curtail_MW": _round(p_curtail),
        "P_unserved_MW": _round(p_unserved),
        "NH3_t": _round(NH3_FULL_TPH * alpha),
        "cost_yuan": _round(_generation_cost(p_wind, p_pv) + _equipment_cost(alpha)),
    }


def _daily_from_hourly(rows: list[dict], storage_capacity_mwh: float) -> dict:
    e_wind = _sum([float(row["P_wind_MW"]) for row in rows])
    e_pv = _sum([float(row["P_pv_MW"]) for row in rows])
    e_re = e_wind + e_pv
    e_load = _sum([float(row["P_load_MW"]) for row in rows])
    e_use = _sum([
        float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"])
        for row in rows
    ])
    e_charge = _sum([float(row["P_charge_MW"]) for row in rows])
    e_discharge = _sum([float(row["P_discharge_MW"]) for row in rows])
    e_curtail = _sum([float(row["P_curtail_MW"]) for row in rows])
    e_unserved = _sum([float(row["P_unserved_MW"]) for row in rows])
    production = _sum([float(row["NH3_t"]) for row in rows])
    capex_day = storage_capacity_mwh * 1000.0 * ESS_CAPEX_YUAN_PER_KWH / (ESS_LIFETIME_YR * 365.0)
    storage_opex = 1000.0 * ESS_OPEX_YUAN_PER_KWH * e_discharge
    daily_cost = _sum([float(row["cost_yuan"]) for row in rows]) + capex_day + storage_opex
    return {
        "scenario_id": rows[0]["scenario_id"],
        "NH3_t_per_day": _round(production),
        "run_hours": int(sum(int(row["run_status"]) for row in rows)),
        "avg_alpha": _round(_sum([float(row["alpha"]) for row in rows]) / 24.0),
        "E_wind_MWh": _round(e_wind),
        "E_pv_MWh": _round(e_pv),
        "E_re_MWh": _round(e_re),
        "E_use_MWh": _round(e_use),
        "E_load_MWh": _round(e_load),
        "E_charge_MWh": _round(e_charge),
        "E_discharge_MWh": _round(e_discharge),
        "E_curtail_MWh": _round(e_curtail),
        "E_unserved_MWh": _round(e_unserved),
        "storage_capacity_MWh": _round(storage_capacity_mwh),
        "daily_cost_yuan": _round(daily_cost),
        "unit_cost_yuan_per_t": _round(daily_cost / production if production > EPS else 0.0),
        "capacity_utilization": _round(production / 72.0),
        "renewable_utilization": _round((e_re - e_curtail) / e_re if e_re > EPS else 0.0),
    }


def solve_no_storage() -> tuple[list[dict], list[dict]]:
    hourly: list[dict] = []
    daily: list[dict] = []
    for scenario in build_combined_scenarios():
        scenario_id = str(scenario["scenario_id"])
        rows = []
        for hour in range(24):
            row = _no_storage_hour(
                scenario_id,
                hour,
                scenario["load_MW"][hour],
                scenario["wind_MW"][hour],
                scenario["pv_MW"][hour],
                scenario["re_MW"][hour],
            )
            rows.append(row)
        hourly.extend(rows)
        daily.append(_daily_from_hourly(rows, 0.0))
    return hourly, daily


def _solve_storage_milp(
    scenario: dict[str, list[float] | str],
    storage_capacity_mwh: float | None,
    min_production_t: float | None = None,
    objective: str = "max_production",
) -> tuple[list[float], list[int], list[float], list[float], list[float], list[float], list[float], float]:
    n = 24
    alpha_i, y_i, ch_i, dis_i, soc_i, curt_i, shed_i = 0, 24, 48, 72, 96, 120, 144
    cap_i = 168
    var_count = 169 if storage_capacity_mwh is None else 168

    c = np.zeros(var_count)
    if objective == "max_production":
        c[alpha_i:alpha_i + n] = -1.0
        c[shed_i:shed_i + n] = 1000.0
    elif objective == "min_capacity":
        c[cap_i] = 1.0
        c[shed_i:shed_i + n] = 1000.0
        c[curt_i:curt_i + n] = 1e-4
        c[ch_i:ch_i + n] = 1e-5
        c[dis_i:dis_i + n] = 1e-5
    elif objective == "min_curtail":
        c[curt_i:curt_i + n] = 1.0
        c[shed_i:shed_i + n] = 1000.0
        c[ch_i:ch_i + n] = 1e-4
        c[dis_i:dis_i + n] = 1e-4
    else:
        raise ValueError(objective)

    lows = np.zeros(var_count)
    highs = np.full(var_count, np.inf)
    highs[alpha_i:alpha_i + n] = ALPHA_MAX
    highs[y_i:y_i + n] = 1.0
    highs[ch_i:ch_i + n] = BIG_M
    highs[dis_i:dis_i + n] = BIG_M
    highs[curt_i:curt_i + n] = BIG_M
    highs[shed_i:shed_i + n] = BIG_M
    if storage_capacity_mwh is None:
        highs[soc_i:soc_i + n] = BIG_M * n
        highs[cap_i] = BIG_M * n
    else:
        highs[soc_i:soc_i + n] = storage_capacity_mwh

    row_count = 24 + 24 + 24 + 24 + (1 if min_production_t is not None else 0)
    a = lil_matrix((row_count, var_count))
    lb = np.full(row_count, -np.inf)
    ub = np.full(row_count, np.inf)
    row = -1

    p_load = scenario["load_MW"]
    p_re = scenario["re_MW"]
    assert isinstance(p_load, list) and isinstance(p_re, list)

    for h in range(n):
        row += 1
        a[row, alpha_i + h] = P_FLEX_FULL_MW
        a[row, ch_i + h] = 1.0
        a[row, curt_i + h] = 1.0
        a[row, dis_i + h] = -1.0
        a[row, shed_i + h] = -1.0
        lb[row] = p_re[h] - p_load[h]
        ub[row] = p_re[h] - p_load[h]

    for h in range(n):
        row += 1
        nxt = (h + 1) % n
        a[row, soc_i + nxt] = 1.0
        a[row, soc_i + h] = -(1.0 - ESS_SELF_LOSS_RATE_PER_H)
        a[row, ch_i + h] = -ESS_CHARGE_EFF
        a[row, dis_i + h] = 1.0 / ESS_DISCHARGE_EFF
        lb[row] = 0.0
        ub[row] = 0.0

    for h in range(n):
        row += 1
        a[row, alpha_i + h] = 1.0
        a[row, y_i + h] = -1.0
        ub[row] = 0.0

    for h in range(n):
        row += 1
        a[row, alpha_i + h] = 1.0
        a[row, y_i + h] = -ALPHA_MIN
        lb[row] = 0.0

    if min_production_t is not None:
        row += 1
        a[row, alpha_i:alpha_i + n] = np.ones(n)
        lb[row] = min_production_t / NH3_FULL_TPH

    constraints = [LinearConstraint(a.tocsr(), lb, ub)]
    if storage_capacity_mwh is None:
        a2 = lil_matrix((n, var_count))
        lb2 = np.full(n, -np.inf)
        ub2 = np.zeros(n)
        for h in range(n):
            a2[h, soc_i + h] = 1.0
            a2[h, cap_i] = -1.0
        constraints.append(LinearConstraint(a2.tocsr(), lb2, ub2))

    integrality = np.zeros(var_count)
    integrality[y_i:y_i + n] = 1
    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lows, highs),
        constraints=constraints,
        options={"time_limit": 60.0, "mip_rel_gap": 1e-8},
    )
    if not result.success:
        raise RuntimeError(f"storage MILP failed for {scenario['scenario_id']}: {result.message}")
    x = result.x
    cap = float(x[cap_i]) if storage_capacity_mwh is None else storage_capacity_mwh
    return (
        [float(v) for v in x[alpha_i:alpha_i + n]],
        [int(round(v)) for v in x[y_i:y_i + n]],
        [float(v) for v in x[ch_i:ch_i + n]],
        [float(v) for v in x[dis_i:dis_i + n]],
        [float(v) for v in x[soc_i:soc_i + n]],
        [float(v) for v in x[curt_i:curt_i + n]],
        [float(v) for v in x[shed_i:shed_i + n]],
        cap,
    )


def _storage_rows(scenario: dict[str, list[float] | str], solution: tuple) -> tuple[list[dict], dict]:
    alpha, y, ch, dis, soc, curt, shed, cap = solution
    scenario_id = str(scenario["scenario_id"])
    rows = []
    for h in range(24):
        p_wind = float(scenario["wind_MW"][h])
        p_pv = float(scenario["pv_MW"][h])
        p_load = float(scenario["load_MW"][h])
        p_re = float(scenario["re_MW"][h])
        p_alk = ALK_FULL_MW * alpha[h]
        p_pem = PEM_FULL_MW * alpha[h]
        p_nh3 = NH3_FULL_MW * alpha[h]
        row = {
            "scenario_id": scenario_id,
            "hour": h,
            "alpha": _round(alpha[h]),
            "run_status": y[h],
            "P_load_MW": _round(p_load),
            "P_wind_MW": _round(p_wind),
            "P_pv_MW": _round(p_pv),
            "P_re_MW": _round(p_re),
            "P_alk_MW": _round(p_alk),
            "P_pem_MW": _round(p_pem),
            "P_nh3_MW": _round(p_nh3),
            "P_charge_MW": _round(ch[h]),
            "P_discharge_MW": _round(dis[h]),
            "E_storage_MWh": _round(soc[h]),
            "P_curtail_MW": _round(curt[h]),
            "P_unserved_MW": _round(shed[h]),
            "NH3_t": _round(NH3_FULL_TPH * alpha[h]),
            "cost_yuan": _round(_generation_cost(p_wind, p_pv) + _equipment_cost(alpha[h])),
        }
        rows.append(row)
    return rows, _daily_from_hourly(rows, cap)


def solve_storage(no_storage_daily: list[dict]) -> tuple[list[dict], list[dict], dict]:
    scenarios = build_combined_scenarios()
    max_curtail_id = max(no_storage_daily, key=lambda row: float(row["E_curtail_MWh"]))["scenario_id"]
    sizing_scenario = next(s for s in scenarios if str(s["scenario_id"]) == max_curtail_id)
    stage1 = _solve_storage_milp(sizing_scenario, None, None, "max_production")
    max_prod = sum(stage1[0]) * NH3_FULL_TPH
    stage2 = _solve_storage_milp(sizing_scenario, None, max_prod - 1e-5, "min_capacity")
    storage_capacity = stage2[-1]

    hourly: list[dict] = []
    daily: list[dict] = []
    for scenario in scenarios:
        s1 = _solve_storage_milp(scenario, storage_capacity, None, "max_production")
        prod = sum(s1[0]) * NH3_FULL_TPH
        s2 = _solve_storage_milp(scenario, storage_capacity, prod - 1e-5, "min_curtail")
        rows, day = _storage_rows(scenario, s2)
        hourly.extend(rows)
        daily.append(day)
    sizing_rows, sizing_day = _storage_rows(sizing_scenario, stage2)
    sizing = {
        "scenario_id": max_curtail_id,
        "max_production_t": _round(max_prod),
        "storage_capacity_MWh": _round(storage_capacity),
        "daily": sizing_day,
    }
    return hourly, daily, sizing


def _annual_block(rows: list[dict]) -> dict:
    production = _sum([float(row["NH3_t_per_day"]) * SCENARIO_DAYS for row in rows])
    cost = _sum([float(row["daily_cost_yuan"]) * SCENARIO_DAYS for row in rows])
    curtail = _sum([float(row["E_curtail_MWh"]) * SCENARIO_DAYS for row in rows])
    unserved = _sum([float(row["E_unserved_MWh"]) * SCENARIO_DAYS for row in rows])
    re = _sum([float(row["E_re_MWh"]) * SCENARIO_DAYS for row in rows])
    return {
        "days": len(rows) * SCENARIO_DAYS,
        "total_production_t": _round(production),
        "total_cost_yuan": _round(cost),
        "unit_cost_yuan_per_t": _round(cost / production if production > EPS else 0.0),
        "curtail_MWh": _round(curtail),
        "unserved_load_MWh": _round(unserved),
        "capacity_utilization": _round(production / (72.0 * len(rows) * SCENARIO_DAYS)),
        "renewable_utilization": _round((re - curtail) / re if re > EPS else 0.0),
    }


def _load_p3_reference() -> dict:
    path = P3_RESULT_DIR / "p3_summary.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f).get("annual_by_production", {}).get("36", {})


def _autonomy_capacity() -> dict:
    ratios = []
    for scenario in build_combined_scenarios():
        for load, p_re in zip(scenario["load_MW"], scenario["re_MW"]):
            ratios.append(float(load) / float(p_re) if float(p_re) > EPS else float("inf"))
    k = max(ratios)
    return {
        "criterion": "cover_regular_load_only",
        "scale_factor": _round(k),
        "wind_capacity_MW": _round(WIND_CAPACITY_MW * k),
        "pv_capacity_MW": _round(PV_CAPACITY_MW * k),
    }


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compute() -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    no_hourly, no_daily = solve_no_storage()
    st_hourly, st_daily, sizing = solve_storage(no_daily)
    summary = {
        "scenario_count": 24,
        "annual_days": 360,
        "alpha_rule": "alpha=0 or 0.1<=alpha<=1",
        "autonomy_capacity": _autonomy_capacity(),
        "storage_sizing": sizing,
        "no_storage_annual": _annual_block(no_daily),
        "with_storage_annual": _annual_block(st_daily),
        "grid_connected_reference_p3_36": _load_p3_reference(),
    }
    return no_hourly, no_daily, st_hourly, st_daily, summary


def write_outputs(no_hourly: list[dict], no_daily: list[dict], st_hourly: list[dict], st_daily: list[dict], summary: dict) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(RESULT_DIR / "p4_offgrid_no_storage_hourly.csv", no_hourly, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p4_offgrid_no_storage_daily.csv", no_daily, DAILY_FIELDS)
    _write_csv(RESULT_DIR / "p4_storage_hourly.csv", st_hourly, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p4_storage_daily.csv", st_daily, DAILY_FIELDS)
    with (RESULT_DIR / "p4_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def print_report(summary: dict) -> None:
    print("=" * 64)
    print("问题四：离网运行与储能配置")
    print("=" * 64)
    print("常规负荷自治等比例扩容倍数:", summary["autonomy_capacity"]["scale_factor"])
    print("储能配置场景:", summary["storage_sizing"]["scenario_id"])
    print("最优储能容量 MWh:", summary["storage_sizing"]["storage_capacity_MWh"])
    print("无储能全年产量 t:", summary["no_storage_annual"]["total_production_t"])
    print("有储能全年产量 t:", summary["with_storage_annual"]["total_production_t"])


if __name__ == "__main__":
    outputs = compute()
    write_outputs(*outputs)
    print_report(outputs[-1])
