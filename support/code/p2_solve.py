"""问题二：离散开停机制氨优化。

执行：
  python support/code/p2_solve.py

产出：
  support/results/p2/p2_typical_hourly.csv
  support/results/p2/p2_typical_daily.csv
  support/results/p2/p2_hourly_cases.csv
  support/results/p2/p2_daily_cases.csv
  support/results/p2/p2_summary.json
"""

from __future__ import annotations

import csv
import json
import sys
import zipfile
from xml.etree import ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ALK_CAPACITY_MW,
    ALK_OPEX_YUAN_PER_KWH,
    LOAD_PEAK_MW,
    NH3_CAPACITY_MW,
    NH3_OPEX_YUAN_PER_KWH,
    NH3_RATE_TPH,
    PEM_CAPACITY_MW,
    PEM_OPEX_YUAN_PER_KWH,
    PV_CAPACITY_MW,
    PV_LCOE_YUAN_PER_KWH,
    SELL_PRICE_YUAN_PER_KWH,
    WIND_CAPACITY_MW,
    WIND_LCOE_YUAN_PER_KWH,
    buy_price_schedule,
)
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
RESULT_DIR = HERE.parent / "results" / "p2"

FN_LOAD = "附件1：园区典型日常规电负荷标幺功率曲线.xlsx"
FN_TYPICAL = "附件2：典型日风电、光伏标幺功率表.xlsx"
FN_WIND_SCN = "附件3：园区6种场景的风电标幺功率表.xlsx"
FN_PV_SCN = "附件4：园区4种场景的光伏标幺功率表.xlsx"

PRODUCTION_LEVELS = [72.0, 63.0, 54.0, 45.0, 36.0]
SCENARIO_DAYS = 15
EXPANSION_FACTOR = 72.0 / 36.0
ALK_FULL_MW = ALK_CAPACITY_MW * EXPANSION_FACTOR
PEM_FULL_MW = PEM_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_MW = NH3_CAPACITY_MW * EXPANSION_FACTOR
NH3_FULL_TPH = NH3_RATE_TPH * EXPANSION_FACTOR

HOURLY_FIELDS = [
    "scenario_id",
    "target_NH3_t_per_day",
    "hour",
    "u_on",
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
    "on_hours",
    "on_hour_list",
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
    "self_use_ratio",
    "green_ratio",
    "green_internal_use_ratio",
    "sell_ratio",
    "daily_cost_yuan",
    "daily_sell_revenue_yuan",
    "daily_net_cost_yuan",
    "unit_cost_yuan_per_t",
    "device_utilization",
    "indicator_class",
]


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return index


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(data)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall("x:si", ns):
        text_parts = [node.text or "" for node in item.findall(".//x:t", ns)]
        strings.append("".join(text_parts))
    return strings


def _sheet_path(zf: zipfile.ZipFile) -> str:
    workbook = ElementTree.fromstring(zf.read("xl/workbook.xml"))
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    first_sheet = workbook.find("x:sheets/x:sheet", ns)
    if first_sheet is None:
        raise ValueError("workbook has no sheet")
    rel_id = first_sheet.attrib[f"{{{ns['r']}}}id"]
    rels = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    for rel in rels.findall("r:Relationship", rel_ns):
        if rel.attrib["Id"] == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            return target
    raise ValueError(f"sheet relationship not found: {rel_id}")


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> float | str | None:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    value = cell.find("x:v", ns)
    if value is None or value.text is None:
        inline = cell.find("x:is/x:t", ns)
        return inline.text if inline is not None else None
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text)]
    return float(value.text)


def _read_24h_matrix(fname: str, ncols: int) -> list[list[float]]:
    """Read the first worksheet from an xlsx file without external dependencies."""
    path = DATA_DIR / fname
    if not path.exists():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as zf:
        shared_strings = _load_shared_strings(zf)
        root = ElementTree.fromstring(zf.read(_sheet_path(zf)))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    matrix: list[list[float]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        row_index = int(row.attrib["r"])
        if row_index < 2 or row_index > 25:
            continue
        values: dict[int, float | str | None] = {}
        for cell in row.findall("x:c", ns):
            values[_column_index(cell.attrib["r"])] = _cell_value(cell, shared_strings)
        matrix.append([float(values[col]) for col in range(2, 2 + ncols)])
    if len(matrix) != 24 or any(len(row) != ncols for row in matrix):
        raise ValueError(f"{fname}: expected (24, {ncols}), got ({len(matrix)}, {len(matrix[0]) if matrix else 0})")
    return matrix


def load_typical_load() -> list[float]:
    return [row[0] for row in _read_24h_matrix(FN_LOAD, 1)]


def load_typical_wind_pv() -> tuple[list[float], list[float]]:
    arr = _read_24h_matrix(FN_TYPICAL, 2)
    return [row[0] for row in arr], [row[1] for row in arr]


def load_wind_scenarios() -> list[list[float]]:
    return _read_24h_matrix(FN_WIND_SCN, 6)


def load_pv_scenarios() -> list[list[float]]:
    return _read_24h_matrix(FN_PV_SCN, 4)


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


def _scenario_curves(
    scenario_id: str,
    wind_pu: list[float],
    pv_pu: list[float],
    load_pu: list[float],
) -> dict[str, list[float] | str]:
    p_load = [value * LOAD_PEAK_MW for value in load_pu]
    p_wind = [value * WIND_CAPACITY_MW for value in wind_pu]
    p_pv = [value * PV_CAPACITY_MW for value in pv_pu]
    p_re = [wind + pv for wind, pv in zip(p_wind, p_pv)]
    return {
        "scenario_id": scenario_id,
        "load_MW": p_load,
        "wind_MW": p_wind,
        "pv_MW": p_pv,
        "re_MW": p_re,
    }


def build_typical_scenario() -> dict[str, list[float] | str]:
    load_pu = load_typical_load()
    wind_pu, pv_pu = load_typical_wind_pv()
    return _scenario_curves("typical", wind_pu, pv_pu, load_pu)


def build_combined_scenarios() -> list[dict[str, list[float] | str]]:
    load_pu = load_typical_load()
    wind_matrix = load_wind_scenarios()
    pv_matrix = load_pv_scenarios()
    scenarios: list[dict[str, list[float] | str]] = []
    for wind_idx in range(6):
        wind_pu = [row[wind_idx] for row in wind_matrix]
        for pv_idx in range(4):
            pv_pu = [row[pv_idx] for row in pv_matrix]
            scenarios.append(_scenario_curves(f"W{wind_idx + 1}_P{pv_idx + 1}", wind_pu, pv_pu, load_pu))
    return scenarios


def _hour_costs(
    p_load: float,
    p_wind: float,
    p_pv: float,
    p_re: float,
    buy_price: float,
    u_on: int,
) -> dict[str, float]:
    p_alk = ALK_FULL_MW * u_on
    p_pem = PEM_FULL_MW * u_on
    p_nh3 = NH3_FULL_MW * u_on
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
        "NH3_t": NH3_FULL_TPH * u_on,
        "cost_yuan": cost,
        "sell_revenue_yuan": revenue,
        "net_cost_yuan": cost - revenue,
    }


def _choose_on_hours(scenario: dict[str, list[float] | str], target: float, buy_price: list[float]) -> set[int]:
    on_hours = int(round(target / NH3_FULL_TPH))
    if on_hours < 0 or on_hours > 24:
        raise ValueError(f"invalid on_hours={on_hours} for target={target}")
    p_load = scenario["load_MW"]
    p_wind = scenario["wind_MW"]
    p_pv = scenario["pv_MW"]
    p_re = scenario["re_MW"]
    assert isinstance(p_load, list) and isinstance(p_wind, list) and isinstance(p_pv, list) and isinstance(p_re, list)
    increments: list[tuple[float, int]] = []
    for hour in range(24):
        off = _hour_costs(p_load[hour], p_wind[hour], p_pv[hour], p_re[hour], buy_price[hour], 0)
        on = _hour_costs(p_load[hour], p_wind[hour], p_pv[hour], p_re[hour], buy_price[hour], 1)
        increments.append((on["net_cost_yuan"] - off["net_cost_yuan"], hour))
    return {hour for _, hour in sorted(increments)[:on_hours]}


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

    on_set = _choose_on_hours(scenario, target, buy_price)
    hourly_rows: list[dict[str, float | int | str]] = []
    for hour in range(24):
        u_on = 1 if hour in on_set else 0
        costs = _hour_costs(p_load[hour], p_wind[hour], p_pv[hour], p_re[hour], buy_price[hour], u_on)
        hourly_rows.append(
            {
                "scenario_id": scenario_id,
                "target_NH3_t_per_day": _round_float(target),
                "hour": hour,
                "u_on": u_on,
                "P_load_MW": _round_float(p_load[hour]),
                "P_wind_MW": _round_float(p_wind[hour]),
                "P_pv_MW": _round_float(p_pv[hour]),
                "P_re_MW": _round_float(p_re[hour]),
                **{key: _round_float(value) for key, value in costs.items()},
            }
        )

    e_wind = _sum(p_wind)
    e_pv = _sum(p_pv)
    e_re = _sum(p_re)
    e_buy = _sum([float(row["P_buy_MW"]) for row in hourly_rows])
    e_sell = _sum([float(row["P_sell_MW"]) for row in hourly_rows])
    e_self = e_re - e_sell
    e_total = e_re + e_buy
    e_use = _sum([float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"]) for row in hourly_rows])
    self_use_ratio = e_self / e_re if e_re > 0 else 0.0
    green_ratio = e_self / e_total if e_total > 0 else 0.0
    green_internal_use_ratio = e_self / e_use if e_use > 0 else 0.0
    sell_ratio = e_sell / e_re if e_re > 0 else 0.0
    daily_cost = _sum([float(row["cost_yuan"]) for row in hourly_rows])
    daily_revenue = _sum([float(row["sell_revenue_yuan"]) for row in hourly_rows])
    daily_net_cost = _sum([float(row["net_cost_yuan"]) for row in hourly_rows])
    on_hours = int(sum(int(row["u_on"]) for row in hourly_rows))

    daily_row: dict[str, float | int | str] = {
        "scenario_id": scenario_id,
        "target_NH3_t_per_day": _round_float(target),
        "on_hours": on_hours,
        "on_hour_list": " ".join(str(hour) for hour in sorted(on_set)),
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
        "self_use_ratio": _round_float(self_use_ratio),
        "green_ratio": _round_float(green_ratio),
        "green_internal_use_ratio": _round_float(green_internal_use_ratio),
        "sell_ratio": _round_float(sell_ratio),
        "daily_cost_yuan": _round_float(daily_cost),
        "daily_sell_revenue_yuan": _round_float(daily_revenue),
        "daily_net_cost_yuan": _round_float(daily_net_cost),
        "unit_cost_yuan_per_t": _round_float(daily_net_cost / target),
        "device_utilization": _round_float(on_hours / 24.0),
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
    self_ratio = agg["E_self_MWh"] / agg["E_re_MWh"] if agg["E_re_MWh"] > 0 else 0.0
    green_ratio = agg["E_self_MWh"] / agg["E_total_MWh"] if agg["E_total_MWh"] > 0 else 0.0
    sell_ratio = agg["E_sell_MWh"] / agg["E_re_MWh"] if agg["E_re_MWh"] > 0 else 0.0
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
            "self_use_ratio": _round_float(self_ratio),
            "green_ratio": _round_float(green_ratio),
            "sell_ratio": _round_float(sell_ratio),
            "green_internal_use_ratio": _round_float(agg["E_self_MWh"] / agg["E_use_MWh"] if agg["E_use_MWh"] > 0 else 0.0),
        },
        "indicator_class_day_counts": class_counts,
    }


def compute() -> tuple[
    list[dict[str, float | int | str]],
    list[dict[str, float | int | str]],
    list[dict[str, float | int | str]],
    list[dict[str, float | int | str]],
    dict,
]:
    buy_price = buy_price_schedule()

    typical_hourly: list[dict[str, float | int | str]] = []
    typical_daily: list[dict[str, float | int | str]] = []
    typical = build_typical_scenario()
    for target in PRODUCTION_LEVELS:
        hourly_rows, daily_row = solve_case(typical, target, buy_price)
        typical_hourly.extend(hourly_rows)
        typical_daily.append(daily_row)

    scenario_hourly: list[dict[str, float | int | str]] = []
    scenario_daily: list[dict[str, float | int | str]] = []
    for scenario in build_combined_scenarios():
        for target in PRODUCTION_LEVELS:
            hourly_rows, daily_row = solve_case(scenario, target, buy_price)
            scenario_hourly.extend(hourly_rows)
            scenario_daily.append(daily_row)

    typical_best = _best_by_unit_cost(typical_daily)
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
        "expanded_capacity": {
            "alk_MW": ALK_FULL_MW,
            "pem_MW": PEM_FULL_MW,
            "nh3_MW": NH3_FULL_MW,
            "nh3_tph": NH3_FULL_TPH,
        },
        "typical_best": _json_daily(typical_best),
        "typical_by_production": {str(int(row["target_NH3_t_per_day"])): _json_daily(row) for row in typical_daily},
        "scenario_best_by_production": {
            str(int(target)): _json_daily(_best_by_unit_cost([row for row in scenario_daily if float(row["target_NH3_t_per_day"]) == target]))
            for target in PRODUCTION_LEVELS
        },
        "annual_by_production": annual_by_production,
        "annual_recommended": annual_recommended,
        "total_production_t": annual_recommended["total_production_t"],
        "total_cost_yuan": annual_recommended["total_cost_yuan"],
        "unit_cost_yuan_per_t": annual_recommended["unit_cost_yuan_per_t"],
        "green_indicators": annual_recommended["green_indicators"],
    }
    return typical_hourly, typical_daily, scenario_hourly, scenario_daily, summary


def _json_daily(row: dict[str, float | int | str]) -> dict:
    return {key: row[key] for key in DAILY_FIELDS}


def _write_csv(path: Path, rows: list[dict[str, float | int | str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    typical_hourly: list[dict[str, float | int | str]],
    typical_daily: list[dict[str, float | int | str]],
    scenario_hourly: list[dict[str, float | int | str]],
    scenario_daily: list[dict[str, float | int | str]],
    summary: dict,
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(RESULT_DIR / "p2_typical_hourly.csv", typical_hourly, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p2_typical_daily.csv", typical_daily, DAILY_FIELDS)
    _write_csv(RESULT_DIR / "p2_hourly_cases.csv", scenario_hourly, HOURLY_FIELDS)
    _write_csv(RESULT_DIR / "p2_daily_cases.csv", scenario_daily, DAILY_FIELDS)
    with (RESULT_DIR / "p2_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def print_report(summary: dict) -> None:
    print("=" * 64)
    print("问题二：离散开停机制氨优化")
    print("=" * 64)
    print(f"24场景全年推荐方案总产量: {summary['total_production_t']:.2f} t")
    print(f"24场景全年推荐方案总净成本: {summary['total_cost_yuan']:.2f} 元")
    print(f"24场景全年推荐方案吨氨成本: {summary['unit_cost_yuan_per_t']:.2f} 元/t")
    print("绿电指标:", summary["green_indicators"])


if __name__ == "__main__":
    outputs = compute()
    write_outputs(*outputs)
    print_report(outputs[-1])
