"""问题三：连续功率可调制氨优化。

执行：
  conda run -n learn3.8 python support/code/p3_solve.py

产出：
  support/results/p3/p3_hourly_cases.csv
  support/results/p3/p3_daily_cases.csv
  support/results/p3/p3_summary.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ALK_CAPACITY_MW,
    ALK_H2_RATE_KGH,
    ALK_OPEX_YUAN_PER_KWH,
    LOAD_PEAK_MW,
    NH3_CAPACITY_MW,
    NH3_H2_KG_PER_KGNH3,
    NH3_OPEX_YUAN_PER_KWH,
    NH3_RATE_TPH,
    PEM_CAPACITY_MW,
    PEM_H2_RATE_KGH,
    PEM_OPEX_YUAN_PER_KWH,
    PV_CAPACITY_MW,
    PV_LCOE_YUAN_PER_KWH,
    SELL_PRICE_YUAN_PER_KWH,
    WIND_CAPACITY_MW,
    WIND_LCOE_YUAN_PER_KWH,
    buy_price_schedule,
)
from p2_solve import load_pv_scenarios, load_typical_load, load_wind_scenarios  # noqa: E402


HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p3"
P2_SUMMARY_PATH = HERE.parent / "results" / "p2" / "p2_summary.json"

PRODUCTION_LEVELS = [72.0, 63.0, 54.0, 45.0, 36.0]
SCENARIO_DAYS = 15
EXPANSION_FACTOR = 72.0 / 36.0

ALK_MAX_MW = ALK_CAPACITY_MW * EXPANSION_FACTOR
PEM_MAX_MW = PEM_CAPACITY_MW * EXPANSION_FACTOR
NH3_MAX_MW = NH3_CAPACITY_MW * EXPANSION_FACTOR
NH3_MAX_TPH = NH3_RATE_TPH * EXPANSION_FACTOR

MIN_LOAD_RATIO = 0.10
ALK_H2_KG_PER_MWH = ALK_H2_RATE_KGH / ALK_CAPACITY_MW
PEM_H2_KG_PER_MWH = PEM_H2_RATE_KGH / PEM_CAPACITY_MW
NH3_H2_KG_PER_T = NH3_H2_KG_PER_KGNH3 * 1000.0
NH3_MW_PER_TPH = NH3_MAX_MW / NH3_MAX_TPH
PLANT_MAX_MW = ALK_MAX_MW + PEM_MAX_MW + NH3_MAX_MW
PLANT_OPEX_YUAN_PER_KWH_AT_FULL_LOAD = (
    ALK_OPEX_YUAN_PER_KWH * ALK_MAX_MW
    + PEM_OPEX_YUAN_PER_KWH * PEM_MAX_MW
    + NH3_OPEX_YUAN_PER_KWH * NH3_MAX_MW
)

N_HOURS = 24

IDX_R = 0
IDX_BUY = 24
IDX_SELL = 48
IDX_GRID_MODE = 72
N_VARS = 96
GRID_BIG_M_MW = 200.0

HOURLY_FIELDS = [
    "scenario_id",
    "target_NH3_t_per_day",
    "hour",
    "P_load_MW",
    "P_wind_MW",
    "P_pv_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "plant_load_ratio",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "H2_prod_kg",
    "H2_cons_kg",
    "alk_load_ratio",
    "pem_load_ratio",
    "nh3_load_ratio",
    "cost_yuan",
    "sell_revenue_yuan",
    "net_cost_yuan",
]

DAILY_FIELDS = [
    "scenario_id",
    "target_NH3_t_per_day",
    "E_wind_MWh",
    "E_pv_MWh",
    "E_re_MWh",
    "E_buy_MWh",
    "E_sell_MWh",
    "E_self_MWh",
    "E_total_MWh",
    "E_use_MWh",
    "E_load_MWh",
    "E_alk_MWh",
    "E_pem_MWh",
    "E_nh3_MWh",
    "NH3_t",
    "H2_prod_kg",
    "H2_cons_kg",
    "self_use_ratio",
    "green_ratio",
    "green_internal_use_ratio",
    "sell_ratio",
    "daily_cost_yuan",
    "daily_sell_revenue_yuan",
    "daily_net_cost_yuan",
    "unit_cost_yuan_per_t",
    "alk_utilization",
    "pem_utilization",
    "nh3_utilization",
    "plant_utilization",
    "indicator_class",
]


def _round(value: float) -> float:
    return round(float(value), 6)


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _indicator_class(self_use_ratio: float, green_ratio: float, sell_ratio: float) -> str:
    passed = [
        self_use_ratio > 0.60,
        green_ratio > 0.30,
        sell_ratio < 0.20,
    ]
    if all(passed):
        return "all_satisfied"
    if any(passed):
        return "partly_satisfied"
    return "none_satisfied"


def _var(base: int, hour: int) -> int:
    return base + hour


def build_combined_scenarios() -> list[dict[str, list[float] | str]]:
    load_pu = load_typical_load()
    wind_matrix = load_wind_scenarios()
    pv_matrix = load_pv_scenarios()
    p_load = [value * LOAD_PEAK_MW for value in load_pu]
    scenarios: list[dict[str, list[float] | str]] = []
    for wind_idx in range(6):
        wind_pu = [row[wind_idx] for row in wind_matrix]
        for pv_idx in range(4):
            pv_pu = [row[pv_idx] for row in pv_matrix]
            p_wind = [value * WIND_CAPACITY_MW for value in wind_pu]
            p_pv = [value * PV_CAPACITY_MW for value in pv_pu]
            scenarios.append(
                {
                    "scenario_id": f"W{wind_idx + 1}_P{pv_idx + 1}",
                    "load_MW": p_load,
                    "wind_MW": p_wind,
                    "pv_MW": p_pv,
                    "re_MW": [wind + pv for wind, pv in zip(p_wind, p_pv)],
                }
            )
    return scenarios


def solve_case(
    scenario: dict[str, list[float] | str],
    target: float,
    buy_price: list[float],
) -> tuple[list[dict[str, float | str]], dict[str, float | str]]:
    scenario_id = str(scenario["scenario_id"])
    p_load = scenario["load_MW"]
    p_wind = scenario["wind_MW"]
    p_pv = scenario["pv_MW"]
    p_re = scenario["re_MW"]
    assert isinstance(p_load, list) and isinstance(p_wind, list) and isinstance(p_pv, list) and isinstance(p_re, list)

    c = np.zeros(N_VARS)
    lower = np.zeros(N_VARS)
    upper = np.full(N_VARS, np.inf)
    integrality = np.zeros(N_VARS)
    for hour in range(N_HOURS):
        c[_var(IDX_R, hour)] = 1000.0 * PLANT_OPEX_YUAN_PER_KWH_AT_FULL_LOAD
        c[_var(IDX_BUY, hour)] = 1000.0 * buy_price[hour]
        c[_var(IDX_SELL, hour)] = -1000.0 * SELL_PRICE_YUAN_PER_KWH
        lower[_var(IDX_R, hour)] = MIN_LOAD_RATIO
        upper[_var(IDX_R, hour)] = 1.0
        upper[_var(IDX_GRID_MODE, hour)] = 1.0
        integrality[_var(IDX_GRID_MODE, hour)] = 1.0

    a_eq: list[np.ndarray] = []
    b_eq: list[float] = []
    a_ub: list[np.ndarray] = []
    b_ub: list[float] = []
    for hour in range(N_HOURS):
        power_row = np.zeros(N_VARS)
        power_row[_var(IDX_R, hour)] = PLANT_MAX_MW
        power_row[_var(IDX_BUY, hour)] = -1.0
        power_row[_var(IDX_SELL, hour)] = 1.0
        a_eq.append(power_row)
        b_eq.append(float(p_re[hour]) - float(p_load[hour]))

        buy_mode_row = np.zeros(N_VARS)
        buy_mode_row[_var(IDX_BUY, hour)] = 1.0
        buy_mode_row[_var(IDX_GRID_MODE, hour)] = -GRID_BIG_M_MW
        a_ub.append(buy_mode_row)
        b_ub.append(0.0)

        sell_mode_row = np.zeros(N_VARS)
        sell_mode_row[_var(IDX_SELL, hour)] = 1.0
        sell_mode_row[_var(IDX_GRID_MODE, hour)] = GRID_BIG_M_MW
        a_ub.append(sell_mode_row)
        b_ub.append(GRID_BIG_M_MW)

    production_row = np.zeros(N_VARS)
    for hour in range(N_HOURS):
        production_row[_var(IDX_R, hour)] = NH3_MAX_TPH
    a_eq.append(production_row)
    b_eq.append(target)

    a_rows = a_eq + a_ub
    lb = np.concatenate([np.array(b_eq), np.full(len(a_ub), -np.inf)])
    ub = np.concatenate([np.array(b_eq), np.array(b_ub)])
    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=LinearConstraint(np.vstack(a_rows), lb, ub),
        options={"time_limit": 30.0, "mip_rel_gap": 1e-9},
    )
    if not result.success:
        raise RuntimeError(f"{scenario_id}, target={target}: {result.message}")

    x = result.x
    hourly_rows: list[dict[str, float | str]] = []
    for hour in range(N_HOURS):
        plant_load_ratio = float(x[_var(IDX_R, hour)])
        p_alk = ALK_MAX_MW * plant_load_ratio
        p_pem = PEM_MAX_MW * plant_load_ratio
        nh3_t = NH3_MAX_TPH * plant_load_ratio
        p_nh3 = NH3_MAX_MW * plant_load_ratio
        p_buy = float(x[_var(IDX_BUY, hour)])
        p_sell = float(x[_var(IDX_SELL, hour)])
        h2_prod = ALK_H2_KG_PER_MWH * p_alk + PEM_H2_KG_PER_MWH * p_pem
        h2_cons = NH3_H2_KG_PER_T * nh3_t
        cost = 1000.0 * (
            WIND_LCOE_YUAN_PER_KWH * float(p_wind[hour])
            + PV_LCOE_YUAN_PER_KWH * float(p_pv[hour])
            + ALK_OPEX_YUAN_PER_KWH * p_alk
            + PEM_OPEX_YUAN_PER_KWH * p_pem
            + NH3_OPEX_YUAN_PER_KWH * p_nh3
            + buy_price[hour] * p_buy
        )
        revenue = 1000.0 * SELL_PRICE_YUAN_PER_KWH * p_sell
        hourly_rows.append(
            {
                "scenario_id": scenario_id,
                "target_NH3_t_per_day": _round(target),
                "hour": hour,
                "P_load_MW": _round(float(p_load[hour])),
                "P_wind_MW": _round(float(p_wind[hour])),
                "P_pv_MW": _round(float(p_pv[hour])),
                "P_re_MW": _round(float(p_re[hour])),
                "P_alk_MW": _round(p_alk),
                "P_pem_MW": _round(p_pem),
                "P_nh3_MW": _round(p_nh3),
                "plant_load_ratio": _round(plant_load_ratio),
                "P_buy_MW": _round(p_buy),
                "P_sell_MW": _round(p_sell),
                "P_curtail_MW": 0.0,
                "NH3_t": _round(nh3_t),
                "H2_prod_kg": _round(h2_prod),
                "H2_cons_kg": _round(h2_cons),
                "alk_load_ratio": _round(p_alk / ALK_MAX_MW),
                "pem_load_ratio": _round(p_pem / PEM_MAX_MW),
                "nh3_load_ratio": _round(nh3_t / NH3_MAX_TPH),
                "cost_yuan": _round(cost),
                "sell_revenue_yuan": _round(revenue),
                "net_cost_yuan": _round(cost - revenue),
            }
        )

    daily_row = summarize_daily(scenario_id, target, hourly_rows)
    return hourly_rows, daily_row


def summarize_daily(
    scenario_id: str,
    target: float,
    hourly_rows: list[dict[str, float | str]],
) -> dict[str, float | str]:
    e_wind = _sum([float(row["P_wind_MW"]) for row in hourly_rows])
    e_pv = _sum([float(row["P_pv_MW"]) for row in hourly_rows])
    e_re = _sum([float(row["P_re_MW"]) for row in hourly_rows])
    e_buy = _sum([float(row["P_buy_MW"]) for row in hourly_rows])
    e_sell = _sum([float(row["P_sell_MW"]) for row in hourly_rows])
    e_self = e_re - e_sell
    e_total = e_re + e_buy
    e_load = _sum([float(row["P_load_MW"]) for row in hourly_rows])
    e_alk = _sum([float(row["P_alk_MW"]) for row in hourly_rows])
    e_pem = _sum([float(row["P_pem_MW"]) for row in hourly_rows])
    e_nh3 = _sum([float(row["P_nh3_MW"]) for row in hourly_rows])
    e_use = e_load + e_alk + e_pem + e_nh3
    nh3_t = _sum([float(row["NH3_t"]) for row in hourly_rows])
    h2_prod = _sum([float(row["H2_prod_kg"]) for row in hourly_rows])
    h2_cons = _sum([float(row["H2_cons_kg"]) for row in hourly_rows])
    daily_cost = _sum([float(row["cost_yuan"]) for row in hourly_rows])
    daily_revenue = _sum([float(row["sell_revenue_yuan"]) for row in hourly_rows])
    daily_net_cost = _sum([float(row["net_cost_yuan"]) for row in hourly_rows])
    self_use_ratio = e_self / e_re if e_re > 0 else 0.0
    green_ratio = e_self / e_total if e_total > 0 else 0.0
    green_internal_use_ratio = e_self / e_use if e_use > 0 else 0.0
    sell_ratio = e_sell / e_re if e_re > 0 else 0.0
    return {
        "scenario_id": scenario_id,
        "target_NH3_t_per_day": _round(target),
        "E_wind_MWh": _round(e_wind),
        "E_pv_MWh": _round(e_pv),
        "E_re_MWh": _round(e_re),
        "E_buy_MWh": _round(e_buy),
        "E_sell_MWh": _round(e_sell),
        "E_self_MWh": _round(e_self),
        "E_total_MWh": _round(e_total),
        "E_use_MWh": _round(e_use),
        "E_load_MWh": _round(e_load),
        "E_alk_MWh": _round(e_alk),
        "E_pem_MWh": _round(e_pem),
        "E_nh3_MWh": _round(e_nh3),
        "NH3_t": _round(nh3_t),
        "H2_prod_kg": _round(h2_prod),
        "H2_cons_kg": _round(h2_cons),
        "self_use_ratio": _round(self_use_ratio),
        "green_ratio": _round(green_ratio),
        "green_internal_use_ratio": _round(green_internal_use_ratio),
        "sell_ratio": _round(sell_ratio),
        "daily_cost_yuan": _round(daily_cost),
        "daily_sell_revenue_yuan": _round(daily_revenue),
        "daily_net_cost_yuan": _round(daily_net_cost),
        "unit_cost_yuan_per_t": _round(daily_net_cost / target),
        "alk_utilization": _round(e_alk / (ALK_MAX_MW * N_HOURS)),
        "pem_utilization": _round(e_pem / (PEM_MAX_MW * N_HOURS)),
        "nh3_utilization": _round(e_nh3 / (NH3_MAX_MW * N_HOURS)),
        "plant_utilization": _round(nh3_t / (NH3_MAX_TPH * N_HOURS)),
        "indicator_class": _indicator_class(self_use_ratio, green_ratio, sell_ratio),
    }


def _best_by_unit_cost(rows: list[dict[str, float | str]]) -> dict[str, float | str]:
    return min(rows, key=lambda row: float(row["unit_cost_yuan_per_t"]))


def _annual_block(rows: list[dict[str, float | str]], days_per_row: int = SCENARIO_DAYS) -> dict:
    def weighted_sum(key: str) -> float:
        return _sum([float(row[key]) * days_per_row for row in rows])

    e_re = weighted_sum("E_re_MWh")
    e_buy = weighted_sum("E_buy_MWh")
    e_sell = weighted_sum("E_sell_MWh")
    e_self = weighted_sum("E_self_MWh")
    e_total = weighted_sum("E_total_MWh")
    e_use = weighted_sum("E_use_MWh")
    total_production = weighted_sum("target_NH3_t_per_day")
    total_cost = weighted_sum("daily_net_cost_yuan")
    gross_cost = weighted_sum("daily_cost_yuan")
    sell_revenue = weighted_sum("daily_sell_revenue_yuan")
    class_counts = {"all_satisfied": 0, "partly_satisfied": 0, "none_satisfied": 0}
    for row in rows:
        class_counts[str(row["indicator_class"])] += days_per_row

    return {
        "days": len(rows) * days_per_row,
        "total_production_t": _round(total_production),
        "total_cost_yuan": _round(total_cost),
        "gross_cost_yuan": _round(gross_cost),
        "sell_revenue_yuan": _round(sell_revenue),
        "unit_cost_yuan_per_t": _round(total_cost / total_production if total_production > 0 else 0.0),
        "energy_MWh": {
            "renewable": _round(e_re),
            "grid_buy": _round(e_buy),
            "grid_sell": _round(e_sell),
            "self_use": _round(e_self),
            "total_wide": _round(e_total),
            "internal_use": _round(e_use),
        },
        "green_indicators": {
            "self_use_ratio": _round(e_self / e_re if e_re > 0 else 0.0),
            "green_ratio": _round(e_self / e_total if e_total > 0 else 0.0),
            "sell_ratio": _round(e_sell / e_re if e_re > 0 else 0.0),
            "green_internal_use_ratio": _round(e_self / e_use if e_use > 0 else 0.0),
        },
        "indicator_class_day_counts": class_counts,
    }


def _load_p2_summary() -> dict | None:
    if not P2_SUMMARY_PATH.exists():
        return None
    with P2_SUMMARY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _comparison_against_p2(annual_recommended: dict, annual_by_production: dict) -> dict:
    p2 = _load_p2_summary()
    if p2 is None:
        return {"available": False}

    def delta_block(p3_block: dict, p2_block: dict) -> dict:
        return {
            "unit_cost_delta_yuan_per_t": _round(p3_block["unit_cost_yuan_per_t"] - p2_block["unit_cost_yuan_per_t"]),
            "grid_buy_delta_MWh": _round(p3_block["energy_MWh"]["grid_buy"] - p2_block["energy_MWh"]["grid_buy"]),
            "grid_sell_delta_MWh": _round(p3_block["energy_MWh"]["grid_sell"] - p2_block["energy_MWh"]["grid_sell"]),
            "self_use_ratio_delta": _round(p3_block["green_indicators"]["self_use_ratio"] - p2_block["green_indicators"]["self_use_ratio"]),
            "green_ratio_delta": _round(p3_block["green_indicators"]["green_ratio"] - p2_block["green_indicators"]["green_ratio"]),
            "sell_ratio_delta": _round(p3_block["green_indicators"]["sell_ratio"] - p2_block["green_indicators"]["sell_ratio"]),
        }

    return {
        "available": True,
        "annual_recommended": delta_block(annual_recommended, p2["annual_recommended"]),
        "annual_by_production": {
            str(target): delta_block(annual_by_production[str(target)], p2["annual_by_production"][str(target)])
            for target in [36, 45, 54, 63, 72]
        },
    }


def compute() -> tuple[list[dict[str, float | str]], list[dict[str, float | str]], dict]:
    buy_price = buy_price_schedule()
    hourly_rows: list[dict[str, float | str]] = []
    daily_rows: list[dict[str, float | str]] = []
    for scenario in build_combined_scenarios():
        for target in PRODUCTION_LEVELS:
            case_hourly, case_daily = solve_case(scenario, target, buy_price)
            hourly_rows.extend(case_hourly)
            daily_rows.append(case_daily)

    annual_by_production: dict[str, dict] = {}
    for target in PRODUCTION_LEVELS:
        rows = [row for row in daily_rows if float(row["target_NH3_t_per_day"]) == target]
        annual_by_production[str(int(target))] = _annual_block(rows)

    best_rows = []
    for scenario_id in sorted({str(row["scenario_id"]) for row in daily_rows}):
        rows = [row for row in daily_rows if str(row["scenario_id"]) == scenario_id]
        best_rows.append(_best_by_unit_cost(rows))
    annual_recommended = _annual_block(best_rows)

    summary = {
        "scenario_count": 24,
        "annual_days": 360,
        "scenario_days": SCENARIO_DAYS,
        "production_levels_t_per_day": [36, 45, 54, 63, 72],
        "expanded_capacity": {
            "alk_MW": ALK_MAX_MW,
            "pem_MW": PEM_MAX_MW,
            "nh3_MW": NH3_MAX_MW,
            "nh3_tph": NH3_MAX_TPH,
            "plant_MW": PLANT_MAX_MW,
            "min_load_ratio": MIN_LOAD_RATIO,
            "dispatch_model": "synchronized_plant_load_ratio",
        },
        "annual_by_production": annual_by_production,
        "annual_recommended": annual_recommended,
        "recommended_daily_cases": {
            str(row["scenario_id"]): {
                "target_NH3_t_per_day": row["target_NH3_t_per_day"],
                "unit_cost_yuan_per_t": row["unit_cost_yuan_per_t"],
                "indicator_class": row["indicator_class"],
            }
            for row in best_rows
        },
        "p2_comparison": _comparison_against_p2(annual_recommended, annual_by_production),
        "total_production_t": annual_recommended["total_production_t"],
        "total_cost_yuan": annual_recommended["total_cost_yuan"],
        "unit_cost_yuan_per_t": annual_recommended["unit_cost_yuan_per_t"],
        "green_indicators": annual_recommended["green_indicators"],
    }
    return hourly_rows, daily_rows, summary


def _write_csv(path: Path, rows: list[dict[str, float | str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    hourly_rows: list[dict[str, float | str]],
    daily_rows: list[dict[str, float | str]],
    summary: dict,
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(RESULT_DIR / "p3_hourly_cases.csv", hourly_rows, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p3_daily_cases.csv", daily_rows, DAILY_FIELDS)
    with (RESULT_DIR / "p3_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def print_report(summary: dict) -> None:
    print("=" * 64)
    print("问题三：连续功率可调制氨优化")
    print("=" * 64)
    print(f"24场景全年推荐方案总产量: {summary['total_production_t']:.2f} t")
    print(f"24场景全年推荐方案总净成本: {summary['total_cost_yuan']:.2f} 元")
    print(f"24场景全年推荐方案吨氨成本: {summary['unit_cost_yuan_per_t']:.2f} 元/t")
    print("绿电指标:", summary["green_indicators"])
    print("与问题二推荐方案差值:", summary["p2_comparison"].get("annual_recommended"))


if __name__ == "__main__":
    outputs = compute()
    write_outputs(*outputs)
    print_report(outputs[-1])
