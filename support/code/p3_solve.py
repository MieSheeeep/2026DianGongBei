"""问题三：连续可调制氨优化。

执行：
  python support/code/p3_solve.py

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
from scipy.sparse import lil_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ALK_CAPACITY_MW,
    ALK_OPEX_YUAN_PER_KWH,
    NH3_CAPACITY_MW,
    NH3_OPEX_YUAN_PER_KWH,
    NH3_RATE_TPH,
    PEM_CAPACITY_MW,
    PEM_OPEX_YUAN_PER_KWH,
    SELL_PRICE_YUAN_PER_KWH,
    buy_price_schedule,
)
from p2_solve import (  # noqa: E402
    PRODUCTION_LEVELS,
    SCENARIO_DAYS,
    WIND_LCOE_YUAN_PER_KWH,
    PV_LCOE_YUAN_PER_KWH,
    build_combined_scenarios,
)

HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p3"
P2_RESULT_DIR = HERE.parent / "results" / "p2"

EXPANSION_FACTOR = 72.0 / 36.0
ALK_FULL_MW = ALK_CAPACITY_MW * EXPANSION_FACTOR
PEM_FULL_MW = PEM_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_MW = NH3_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_TPH = NH3_RATE_TPH * EXPANSION_FACTOR
P_FLEX_FULL_MW = ALK_FULL_MW + PEM_FULL_MW + NH3_FULL_MW
ALPHA_MIN = 0.1
ALPHA_MAX = 1.0
EPS = 1e-9

HOURLY_FIELDS = [
    "scenario_id",
    "target_NH3_t_per_day",
    "hour",
    "alpha",
    "P_load_MW",
    "P_wind_MW",
    "P_pv_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "cost_yuan",
    "sell_revenue_yuan",
    "net_cost_yuan",
]

DAILY_FIELDS = [
    "scenario_id",
    "target_NH3_t_per_day",
    "avg_alpha",
    "min_alpha",
    "max_alpha",
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
    "daily_cost_yuan",
    "daily_sell_revenue_yuan",
    "daily_net_cost_yuan",
    "unit_cost_yuan_per_t",
    "self_use_ratio",
    "green_ratio",
    "green_internal_use_ratio",
    "sell_ratio",
    "indicator_class",
]


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _round_float(value: float) -> float:
    return round(float(value), 6)


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


def _hour_costs(
    p_load: float,
    p_wind: float,
    p_pv: float,
    p_re: float,
    buy_price: float,
    alpha: float,
) -> dict[str, float]:
    p_alk = ALK_FULL_MW * alpha
    p_pem = PEM_FULL_MW * alpha
    p_nh3 = NH3_FULL_MW * alpha
    p_use = p_load + p_alk + p_pem + p_nh3
    p_buy = max(p_use - p_re, 0.0)
    p_sell = max(p_re - p_use, 0.0)
    cost = 1000.0 * (
        WIND_LCOE_YUAN_PER_KWH * p_wind
        + PV_LCOE_YUAN_PER_KWH * p_pv
        + ALK_OPEX_YUAN_PER_KWH * p_alk
        + PEM_OPEX_YUAN_PER_KWH * p_pem
        + NH3_OPEX_YUAN_PER_KWH * p_nh3
        + buy_price * p_buy
    )
    revenue = 1000.0 * SELL_PRICE_YUAN_PER_KWH * p_sell
    return {
        "P_alk_MW": p_alk,
        "P_pem_MW": p_pem,
        "P_nh3_MW": p_nh3,
        "P_buy_MW": p_buy,
        "P_sell_MW": p_sell,
        "P_curtail_MW": 0.0,
        "NH3_t": NH3_FULL_TPH * alpha,
        "cost_yuan": cost,
        "sell_revenue_yuan": revenue,
        "net_cost_yuan": cost - revenue,
    }


def _marginal_segments(
    p_load: list[float],
    p_re: list[float],
    buy_price: list[float],
) -> list[tuple[float, int, float, float]]:
    equipment_slope = (
        ALK_OPEX_YUAN_PER_KWH * ALK_FULL_MW
        + PEM_OPEX_YUAN_PER_KWH * PEM_FULL_MW
        + NH3_OPEX_YUAN_PER_KWH * NH3_FULL_MW
    )
    segments: list[tuple[float, int, float, float]] = []
    for hour in range(24):
        alpha_zero = (p_re[hour] - p_load[hour]) / P_FLEX_FULL_MW
        sell_hi = min(alpha_zero, ALPHA_MAX)
        if sell_hi > ALPHA_MIN + EPS:
            slope = 1000.0 * (equipment_slope + SELL_PRICE_YUAN_PER_KWH * P_FLEX_FULL_MW)
            segments.append((slope, hour, ALPHA_MIN, sell_hi))
        buy_lo = max(alpha_zero, ALPHA_MIN)
        if ALPHA_MAX > buy_lo + EPS:
            slope = 1000.0 * (equipment_slope + buy_price[hour] * P_FLEX_FULL_MW)
            segments.append((slope, hour, buy_lo, ALPHA_MAX))
    return sorted(segments, key=lambda item: (item[0], item[1], item[2]))


def _choose_alpha(scenario: dict[str, list[float] | str], target: float, buy_price: list[float]) -> list[float]:
    required_alpha_sum = target / NH3_FULL_TPH
    base_alpha_sum = 24.0 * ALPHA_MIN
    if required_alpha_sum < base_alpha_sum - EPS or required_alpha_sum > 24.0 * ALPHA_MAX + EPS:
        raise ValueError(f"target={target} is infeasible for alpha bounds")

    p_load = scenario["load_MW"]
    p_re = scenario["re_MW"]
    assert isinstance(p_load, list) and isinstance(p_re, list)

    # MILP is used here because buy and sell are mutually exclusive. The objective
    # is linear once each hour is assigned to buy-mode or sell-mode.
    n = 24
    alpha_idx = 0
    buy_idx = 24
    sell_idx = 48
    mode_idx = 72
    var_count = 96
    big_m = 200.0

    equipment_slope = 1000.0 * (
        ALK_OPEX_YUAN_PER_KWH * ALK_FULL_MW
        + PEM_OPEX_YUAN_PER_KWH * PEM_FULL_MW
        + NH3_OPEX_YUAN_PER_KWH * NH3_FULL_MW
    )
    c = np.zeros(var_count)
    c[alpha_idx:alpha_idx + n] = equipment_slope
    c[buy_idx:buy_idx + n] = [1000.0 * price for price in buy_price]
    c[sell_idx:sell_idx + n] = -1000.0 * SELL_PRICE_YUAN_PER_KWH

    lows = np.zeros(var_count)
    highs = np.full(var_count, np.inf)
    lows[alpha_idx:alpha_idx + n] = ALPHA_MIN
    highs[alpha_idx:alpha_idx + n] = ALPHA_MAX
    highs[buy_idx:buy_idx + n] = big_m
    highs[sell_idx:sell_idx + n] = big_m
    highs[mode_idx:mode_idx + n] = 1.0

    row_count = 1 + n + 2 * n
    a = lil_matrix((row_count, var_count))
    lb = np.full(row_count, -np.inf)
    ub = np.full(row_count, np.inf)

    row = 0
    a[row, alpha_idx:alpha_idx + n] = np.ones(n)
    lb[row] = required_alpha_sum
    ub[row] = required_alpha_sum

    for hour in range(n):
        row += 1
        a[row, alpha_idx + hour] = P_FLEX_FULL_MW
        a[row, buy_idx + hour] = -1.0
        a[row, sell_idx + hour] = 1.0
        lb[row] = p_re[hour] - p_load[hour]
        ub[row] = p_re[hour] - p_load[hour]

    for hour in range(n):
        row += 1
        a[row, buy_idx + hour] = 1.0
        a[row, mode_idx + hour] = -big_m
        ub[row] = 0.0

    for hour in range(n):
        row += 1
        a[row, sell_idx + hour] = 1.0
        a[row, mode_idx + hour] = big_m
        ub[row] = big_m

    integrality = np.zeros(var_count)
    integrality[mode_idx:mode_idx + n] = 1
    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lows, highs),
        constraints=LinearConstraint(a.tocsr(), lb, ub),
        options={"time_limit": 30.0, "mip_rel_gap": 1e-9},
    )
    if not result.success:
        raise ValueError(f"MILP failed for target={target}, scenario={scenario['scenario_id']}: {result.message}")
    return [float(value) for value in result.x[alpha_idx:alpha_idx + n]]


def solve_case(
    scenario: dict[str, list[float] | str],
    target: float,
    buy_price: list[float],
) -> tuple[list[dict[str, float | int | str]], dict[str, float | int | str]]:
    scenario_id = str(scenario["scenario_id"])
    p_load = scenario["load_MW"]
    p_wind = scenario["wind_MW"]
    p_pv = scenario["pv_MW"]
    p_re = scenario["re_MW"]
    assert isinstance(p_load, list) and isinstance(p_wind, list) and isinstance(p_pv, list) and isinstance(p_re, list)

    alpha = _choose_alpha(scenario, target, buy_price)
    hourly_rows: list[dict[str, float | int | str]] = []
    for hour, value in enumerate(alpha):
        costs = _hour_costs(p_load[hour], p_wind[hour], p_pv[hour], p_re[hour], buy_price[hour], value)
        hourly_rows.append(
            {
                "scenario_id": scenario_id,
                "target_NH3_t_per_day": _round_float(target),
                "hour": hour,
                "alpha": _round_float(value),
                "P_load_MW": _round_float(p_load[hour]),
                "P_wind_MW": _round_float(p_wind[hour]),
                "P_pv_MW": _round_float(p_pv[hour]),
                "P_re_MW": _round_float(p_re[hour]),
                **{key: _round_float(val) for key, val in costs.items()},
            }
        )

    e_wind = _sum(p_wind)
    e_pv = _sum(p_pv)
    e_re = _sum(p_re)
    e_buy = _sum([float(row["P_buy_MW"]) for row in hourly_rows])
    e_sell = _sum([float(row["P_sell_MW"]) for row in hourly_rows])
    e_self = e_re - e_sell
    e_total = e_re + e_buy
    e_use = _sum([
        float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"])
        for row in hourly_rows
    ])
    daily_cost = _sum([float(row["cost_yuan"]) for row in hourly_rows])
    daily_revenue = _sum([float(row["sell_revenue_yuan"]) for row in hourly_rows])
    daily_net_cost = _sum([float(row["net_cost_yuan"]) for row in hourly_rows])
    self_use_ratio = e_self / e_re if e_re > 0 else 0.0
    green_ratio = e_self / e_total if e_total > 0 else 0.0
    green_internal_use_ratio = e_self / e_use if e_use > 0 else 0.0
    sell_ratio = e_sell / e_re if e_re > 0 else 0.0

    daily_row: dict[str, float | int | str] = {
        "scenario_id": scenario_id,
        "target_NH3_t_per_day": _round_float(target),
        "avg_alpha": _round_float(_sum(alpha) / 24.0),
        "min_alpha": _round_float(min(alpha)),
        "max_alpha": _round_float(max(alpha)),
        "E_wind_MWh": _round_float(e_wind),
        "E_pv_MWh": _round_float(e_pv),
        "E_re_MWh": _round_float(e_re),
        "E_buy_MWh": _round_float(e_buy),
        "E_sell_MWh": _round_float(e_sell),
        "E_self_MWh": _round_float(e_self),
        "E_total_MWh": _round_float(e_total),
        "E_use_MWh": _round_float(e_use),
        "E_load_MWh": _round_float(_sum(p_load)),
        "E_alk_MWh": _round_float(_sum([float(row["P_alk_MW"]) for row in hourly_rows])),
        "E_pem_MWh": _round_float(_sum([float(row["P_pem_MW"]) for row in hourly_rows])),
        "E_nh3_MWh": _round_float(_sum([float(row["P_nh3_MW"]) for row in hourly_rows])),
        "daily_cost_yuan": _round_float(daily_cost),
        "daily_sell_revenue_yuan": _round_float(daily_revenue),
        "daily_net_cost_yuan": _round_float(daily_net_cost),
        "unit_cost_yuan_per_t": _round_float(daily_net_cost / target),
        "self_use_ratio": _round_float(self_use_ratio),
        "green_ratio": _round_float(green_ratio),
        "green_internal_use_ratio": _round_float(green_internal_use_ratio),
        "sell_ratio": _round_float(sell_ratio),
        "indicator_class": _indicator_class(self_use_ratio, green_ratio, sell_ratio),
    }
    return hourly_rows, daily_row


def _best_by_unit_cost(daily_rows: list[dict[str, float | int | str]]) -> dict[str, float | int | str]:
    return min(daily_rows, key=lambda row: float(row["unit_cost_yuan_per_t"]))


def _aggregate_energy(rows: list[dict[str, float | int | str]], days_per_row: int) -> dict[str, float]:
    keys = [
        "E_re_MWh",
        "E_buy_MWh",
        "E_sell_MWh",
        "E_self_MWh",
        "E_total_MWh",
        "E_use_MWh",
        "daily_cost_yuan",
        "daily_sell_revenue_yuan",
        "daily_net_cost_yuan",
        "target_NH3_t_per_day",
    ]
    return {key: _sum([float(row[key]) * days_per_row for row in rows]) for key in keys}


def _annual_block(rows: list[dict[str, float | int | str]], days_per_row: int = SCENARIO_DAYS) -> dict:
    agg = _aggregate_energy(rows, days_per_row)
    production = agg["target_NH3_t_per_day"]
    class_counts = {"all_satisfied": 0, "partly_satisfied": 0, "none_satisfied": 0}
    for row in rows:
        class_counts[str(row["indicator_class"])] += days_per_row
    return {
        "days": len(rows) * days_per_row,
        "total_production_t": _round_float(production),
        "total_cost_yuan": _round_float(agg["daily_net_cost_yuan"]),
        "gross_cost_yuan": _round_float(agg["daily_cost_yuan"]),
        "sell_revenue_yuan": _round_float(agg["daily_sell_revenue_yuan"]),
        "unit_cost_yuan_per_t": _round_float(agg["daily_net_cost_yuan"] / production if production > 0 else 0.0),
        "energy_MWh": {
            "renewable": _round_float(agg["E_re_MWh"]),
            "grid_buy": _round_float(agg["E_buy_MWh"]),
            "grid_sell": _round_float(agg["E_sell_MWh"]),
            "self_use": _round_float(agg["E_self_MWh"]),
            "total_wide": _round_float(agg["E_total_MWh"]),
            "internal_use": _round_float(agg["E_use_MWh"]),
        },
        "green_indicators": {
            "self_use_ratio": _round_float(agg["E_self_MWh"] / agg["E_re_MWh"] if agg["E_re_MWh"] > 0 else 0.0),
            "green_ratio": _round_float(agg["E_self_MWh"] / agg["E_total_MWh"] if agg["E_total_MWh"] > 0 else 0.0),
            "sell_ratio": _round_float(agg["E_sell_MWh"] / agg["E_re_MWh"] if agg["E_re_MWh"] > 0 else 0.0),
            "green_internal_use_ratio": _round_float(agg["E_self_MWh"] / agg["E_use_MWh"] if agg["E_use_MWh"] > 0 else 0.0),
        },
        "indicator_class_day_counts": class_counts,
    }


def _load_p2_annual_by_production() -> dict:
    path = P2_RESULT_DIR / "p2_summary.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f).get("annual_by_production", {})


def _comparison_with_p2(annual_by_production: dict) -> dict:
    p2_annual = _load_p2_annual_by_production()
    comparison = {}
    for target in PRODUCTION_LEVELS:
        key = str(int(target))
        if key not in p2_annual or key not in annual_by_production:
            continue
        p2 = p2_annual[key]
        p3 = annual_by_production[key]
        p2_g = p2["green_indicators"]
        p3_g = p3["green_indicators"]
        comparison[key] = {
            "p2_unit_cost_yuan_per_t": p2["unit_cost_yuan_per_t"],
            "p3_unit_cost_yuan_per_t": p3["unit_cost_yuan_per_t"],
            "unit_cost_delta_yuan_per_t": _round_float(p3["unit_cost_yuan_per_t"] - p2["unit_cost_yuan_per_t"]),
            "p2_grid_buy_MWh": p2["energy_MWh"]["grid_buy"],
            "p3_grid_buy_MWh": p3["energy_MWh"]["grid_buy"],
            "grid_buy_delta_MWh": _round_float(p3["energy_MWh"]["grid_buy"] - p2["energy_MWh"]["grid_buy"]),
            "p2_grid_sell_MWh": p2["energy_MWh"]["grid_sell"],
            "p3_grid_sell_MWh": p3["energy_MWh"]["grid_sell"],
            "grid_sell_delta_MWh": _round_float(p3["energy_MWh"]["grid_sell"] - p2["energy_MWh"]["grid_sell"]),
            "self_use_ratio_delta": _round_float(p3_g["self_use_ratio"] - p2_g["self_use_ratio"]),
            "green_ratio_delta": _round_float(p3_g["green_ratio"] - p2_g["green_ratio"]),
            "sell_ratio_delta": _round_float(p3_g["sell_ratio"] - p2_g["sell_ratio"]),
        }
    return comparison


def _json_daily(row: dict[str, float | int | str]) -> dict:
    return {key: row[key] for key in DAILY_FIELDS}


def compute() -> tuple[list[dict[str, float | int | str]], list[dict[str, float | int | str]], dict]:
    buy_price = buy_price_schedule()
    scenario_hourly: list[dict[str, float | int | str]] = []
    scenario_daily: list[dict[str, float | int | str]] = []
    for scenario in build_combined_scenarios():
        for target in PRODUCTION_LEVELS:
            hourly_rows, daily_row = solve_case(scenario, target, buy_price)
            scenario_hourly.extend(hourly_rows)
            scenario_daily.append(daily_row)

    annual_by_production = {}
    for target in PRODUCTION_LEVELS:
        rows = [row for row in scenario_daily if float(row["target_NH3_t_per_day"]) == target]
        annual_by_production[str(int(target))] = _annual_block(rows)

    best_rows: list[dict[str, float | int | str]] = []
    for scenario_id in sorted({str(row["scenario_id"]) for row in scenario_daily}):
        rows = [row for row in scenario_daily if str(row["scenario_id"]) == scenario_id]
        best_rows.append(_best_by_unit_cost(rows))
    annual_recommended = _annual_block(best_rows)
    summary = {
        "scenario_count": 24,
        "annual_days": 360,
        "scenario_days": SCENARIO_DAYS,
        "production_levels_t_per_day": [36, 45, 54, 63, 72],
        "alpha_bounds": {"min": ALPHA_MIN, "max": ALPHA_MAX},
        "expanded_capacity": {
            "alk_MW": ALK_FULL_MW,
            "pem_MW": PEM_FULL_MW,
            "nh3_MW": NH3_FULL_MW,
            "nh3_tph": NH3_FULL_TPH,
        },
        "scenario_best_by_production": {
            str(int(target)): _json_daily(_best_by_unit_cost([row for row in scenario_daily if float(row["target_NH3_t_per_day"]) == target]))
            for target in PRODUCTION_LEVELS
        },
        "annual_by_production": annual_by_production,
        "annual_recommended": annual_recommended,
        "comparison_with_p2": _comparison_with_p2(annual_by_production),
        "total_production_t": annual_recommended["total_production_t"],
        "total_cost_yuan": annual_recommended["total_cost_yuan"],
        "unit_cost_yuan_per_t": annual_recommended["unit_cost_yuan_per_t"],
        "green_indicators": annual_recommended["green_indicators"],
    }
    return scenario_hourly, scenario_daily, summary


def _write_csv(path: Path, rows: list[dict[str, float | int | str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    scenario_hourly: list[dict[str, float | int | str]],
    scenario_daily: list[dict[str, float | int | str]],
    summary: dict,
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(RESULT_DIR / "p3_hourly_cases.csv", scenario_hourly, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p3_daily_cases.csv", scenario_daily, DAILY_FIELDS)
    with (RESULT_DIR / "p3_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def validate_outputs(
    scenario_hourly: list[dict[str, float | int | str]],
    scenario_daily: list[dict[str, float | int | str]],
) -> None:
    if len(scenario_hourly) != 24 * 5 * 24:
        raise AssertionError(f"p3_hourly_cases expected 2880 rows, got {len(scenario_hourly)}")
    if len(scenario_daily) != 24 * 5:
        raise AssertionError(f"p3_daily_cases expected 120 rows, got {len(scenario_daily)}")
    for row in scenario_hourly:
        alpha = float(row["alpha"])
        if not (ALPHA_MIN - 1e-6 <= alpha <= ALPHA_MAX + 1e-6):
            raise AssertionError(f"alpha out of bounds: {row}")
        if float(row["P_buy_MW"]) > 1e-6 and float(row["P_sell_MW"]) > 1e-6:
            raise AssertionError(f"simultaneous buy/sell: {row}")
        p_use = float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"])
        lhs = float(row["P_re_MW"]) + float(row["P_buy_MW"])
        rhs = p_use + float(row["P_sell_MW"])
        if abs(lhs - rhs) > 1e-4:
            raise AssertionError(f"power balance failed: {row}")
    for row in scenario_daily:
        rows = [
            h for h in scenario_hourly
            if h["scenario_id"] == row["scenario_id"]
            and float(h["target_NH3_t_per_day"]) == float(row["target_NH3_t_per_day"])
        ]
        production = sum(float(h["NH3_t"]) for h in rows)
        if abs(production - float(row["target_NH3_t_per_day"])) > 1e-5:
            raise AssertionError(f"production failed: {row}")


def print_report(summary: dict) -> None:
    print("=" * 64)
    print("问题三：连续可调制氨优化")
    print("=" * 64)
    print(f"24场景全年推荐方案总产量: {summary['total_production_t']:.2f} t")
    print(f"24场景全年推荐方案总净成本: {summary['total_cost_yuan']:.2f} 元")
    print(f"24场景全年推荐方案吨氨成本: {summary['unit_cost_yuan_per_t']:.2f} 元/t")
    print("绿电指标:", summary["green_indicators"])


if __name__ == "__main__":
    outputs = compute()
    validate_outputs(outputs[0], outputs[1])
    write_outputs(*outputs)
    print_report(outputs[-1])
