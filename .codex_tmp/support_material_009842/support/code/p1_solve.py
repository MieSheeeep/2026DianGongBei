"""问题一：典型风光场景下绿电直连电氢氨园区运行指标分析。

执行：
  python support/code/p1_solve.py

产出：
  support/results/p1/p1_hourly_power.csv
  support/results/p1/p1_summary.json
  figures/p1_power_curves.pdf
  figures/p1_indicator_thresholds.pdf
  figures/p1_cost_breakdown.pdf
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ALK_CAPACITY_MW,
    ALK_H2_RATE_KGH,
    ALK_OPEX_YUAN_PER_KWH,
    LOAD_PEAK_MW,
    NH3_CAPEX_YUAN_PER_KGH_H2,
    NH3_CAPACITY_MW,
    NH3_H2_KG_PER_KGNH3,
    NH3_LIFETIME_YR,
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
from loaders import load_typical_load, load_typical_wind_pv  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULT_DIR = HERE.parent / "results" / "p1"
FIG_DIR = ROOT / "figures"
ANNUAL_DAYS = 360


def _sum(values: list[float]) -> float:
    return float(sum(values))


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _tex_escape(text: str) -> str:
    return text.replace("%", r"\%").replace("_", r"\_")


def compute() -> tuple[dict, list[dict[str, float]]]:
    load_pu = load_typical_load()
    wind_pu, pv_pu = load_typical_wind_pv()
    buy_price = buy_price_schedule()

    p_load = [value * LOAD_PEAK_MW for value in load_pu]
    p_wind = [value * WIND_CAPACITY_MW for value in wind_pu]
    p_pv = [value * PV_CAPACITY_MW for value in pv_pu]
    p_re = [wind + pv for wind, pv in zip(p_wind, p_pv)]
    p_alk = [ALK_CAPACITY_MW] * 24
    p_pem = [PEM_CAPACITY_MW] * 24
    p_nh3 = [NH3_CAPACITY_MW] * 24
    p_use = [alk + pem + nh3 + load for alk, pem, nh3, load in zip(p_alk, p_pem, p_nh3, p_load)]
    p_buy = [max(use - re, 0.0) for use, re in zip(p_use, p_re)]
    p_sell = [max(re - use, 0.0) for use, re in zip(p_use, p_re)]

    e_load = _sum(p_load)
    e_wind = _sum(p_wind)
    e_pv = _sum(p_pv)
    e_re = _sum(p_re)
    e_alk = _sum(p_alk)
    e_pem = _sum(p_pem)
    e_nh3 = _sum(p_nh3)
    e_use = _sum(p_use)
    e_buy = _sum(p_buy)
    e_sell = _sum(p_sell)
    e_self = e_re - e_sell
    e_total = e_re + e_buy

    nh3_tons = NH3_RATE_TPH * 24.0
    h2_kg = (ALK_H2_RATE_KGH + PEM_H2_RATE_KGH) * 24.0

    cost_wind = e_wind * 1000.0 * WIND_LCOE_YUAN_PER_KWH
    cost_pv = e_pv * 1000.0 * PV_LCOE_YUAN_PER_KWH
    cost_opex = (
        e_alk * 1000.0 * ALK_OPEX_YUAN_PER_KWH
        + e_pem * 1000.0 * PEM_OPEX_YUAN_PER_KWH
        + e_nh3 * 1000.0 * NH3_OPEX_YUAN_PER_KWH
    )
    nh3_h2_capacity_kgh = NH3_RATE_TPH * 1000.0 * NH3_H2_KG_PER_KGNH3
    cost_nh3_capex = nh3_h2_capacity_kgh * NH3_CAPEX_YUAN_PER_KGH_H2 / (NH3_LIFETIME_YR * ANNUAL_DAYS)
    cost_grid_buy = sum(power * 1000.0 * price for power, price in zip(p_buy, buy_price))
    revenue_grid_sell = e_sell * 1000.0 * SELL_PRICE_YUAN_PER_KWH
    net_cost = cost_wind + cost_pv + cost_opex + cost_nh3_capex + cost_grid_buy - revenue_grid_sell

    hourly_rows: list[dict[str, float]] = []
    for hour in range(24):
        hourly_rows.append(
            {
                "hour": hour,
                "load_MW": p_load[hour],
                "wind_MW": p_wind[hour],
                "pv_MW": p_pv[hour],
                "renewable_MW": p_re[hour],
                "alk_MW": p_alk[hour],
                "pem_MW": p_pem[hour],
                "nh3_MW": p_nh3[hour],
                "internal_use_MW": p_use[hour],
                "grid_buy_MW": p_buy[hour],
                "grid_sell_MW": p_sell[hour],
                "buy_price_yuan_per_kwh": buy_price[hour],
            }
        )

    result = {
        "energy_MWh": {
            "wind": e_wind,
            "pv": e_pv,
            "renewable": e_re,
            "load": e_load,
            "alk": e_alk,
            "pem": e_pem,
            "nh3": e_nh3,
            "internal_use": e_use,
            "self_use": e_self,
            "grid_sell": e_sell,
            "grid_buy": e_buy,
            "total_wide": e_total,
        },
        "production": {
            "nh3_tons_per_day": nh3_tons,
            "h2_kg_per_day": h2_kg,
        },
        "indicators_pct": {
            "self_use_ratio": e_self / e_re * 100.0,
            "green_in_total_wide": e_self / e_total * 100.0,
            "green_in_internal_use_narrow": e_self / e_use * 100.0,
            "grid_sell_ratio": e_sell / e_re * 100.0,
        },
        "cost_yuan": {
            "wind_lcoe": cost_wind,
            "pv_lcoe": cost_pv,
            "device_opex": cost_opex,
            "nh3_fixed_capex": cost_nh3_capex,
            "grid_buy": cost_grid_buy,
            "grid_sell_revenue": revenue_grid_sell,
            "net_total": net_cost,
            "per_ton_nh3": net_cost / nh3_tons,
        },
    }
    return result, hourly_rows


def write_outputs(result: dict, hourly_rows: list[dict[str, float]]) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULT_DIR / "p1_hourly_power.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(hourly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(hourly_rows)
    with (RESULT_DIR / "p1_summary.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def _plot_coordinates(rows: list[dict[str, float]], field: str, x0: float, y0: float, width: float, height: float, ymax: float) -> str:
    points = []
    for row in rows:
        x = x0 + (row["hour"] + 0.5) / 24.0 * width
        y = y0 + row[field] / ymax * height
        points.append(f"({x:.3f},{y:.3f})")
    return " ".join(points)


def _latex_document(body: str, width_cm: float, height_cm: float) -> str:
    _ = (width_cm, height_cm)
    return rf"""\documentclass[tikz,border=2mm]{{standalone}}
\usepackage{{ctex}}
\usepackage{{tikz}}
\begin{{document}}
\begin{{tikzpicture}}[x=1cm,y=1cm]
{body}
\end{{tikzpicture}}
\end{{document}}
"""


def _compile_pdf(tex_source: str, output_pdf: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="p1_fig_", dir=RESULT_DIR) as tmp_name:
        tmp = Path(tmp_name)
        tex_path = tmp / "figure.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        completed = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stdout)
        shutil.copyfile(tmp / "figure.pdf", output_pdf)


def plot_power_curves(rows: list[dict[str, float]]) -> None:
    x0, y0, width, height, ymax = 1.2, 1.0, 13.2, 5.3, 70.0
    curves = [
        ("internal_use_MW", "园区用电功率", "blue!70!black", "solid"),
        ("renewable_MW", "风光发电功率", "green!55!black", "solid"),
        ("grid_buy_MW", "网购功率", "orange!80!black", "dashed"),
        ("grid_sell_MW", "上网功率", "purple!75!black", "dash dot"),
    ]
    parts = [
        r"\definecolor{gridgray}{RGB}{214,219,225}",
        rf"\draw[->,line width=0.45pt] ({x0},{y0}) -- ({x0 + width + 0.35},{y0}) node[right]{{时段/h}};",
        rf"\draw[->,line width=0.45pt] ({x0},{y0}) -- ({x0},{y0 + height + 0.35});",
        rf"\node[anchor=east] at ({x0 - 0.18:.3f},{y0 + height + 0.58:.3f}) {{功率/MW}};",
    ]
    for tick in range(0, 71, 10):
        y = y0 + tick / ymax * height
        parts.append(rf"\draw[gridgray,line width=0.25pt] ({x0},{y:.3f}) -- ({x0 + width},{y:.3f});")
        if tick % 20 == 0:
            parts.append(rf"\node[left] at ({x0 - 0.08},{y:.3f}) {{{tick}}};")
    for tick in range(0, 25, 2):
        x = x0 + tick / 24.0 * width
        parts.append(rf"\draw ({x:.3f},{y0}) -- ({x:.3f},{y0 - 0.06}) node[below]{{{tick}}};")
    for field, label, color, style in curves:
        parts.append(rf"\draw[{color},line width=0.8pt,{style}] plot coordinates {{{_plot_coordinates(rows, field, x0, y0, width, height, ymax)}}};")
    for idx, (_, label, color, style) in enumerate(curves):
        x = x0 + 1.15 + idx * 3.10
        y = y0 + height + 0.85
        parts.append(rf"\draw[{color},line width=0.8pt,{style}] ({x:.3f},{y:.3f}) -- ({x + 0.65:.3f},{y:.3f});")
        parts.append(rf"\node[right] at ({x + 0.72:.3f},{y:.3f}) {{{label}}};")
    _compile_pdf(_latex_document("\n".join(parts), 15.8, 7.6), FIG_DIR / "p1_power_curves.pdf")


def plot_indicator_thresholds(result: dict) -> None:
    values = [
        result["indicators_pct"]["self_use_ratio"],
        result["indicators_pct"]["green_in_total_wide"],
        result["indicators_pct"]["grid_sell_ratio"],
    ]
    labels = ["新能源自发\\\\自用比例", "总用电量\\\\绿电比例", "新能源上网\\\\电量比例"]
    thresholds = [60.0, 30.0, 20.0]
    directions = [">60\\%", ">30\\%", "<20\\%"]
    passed = [values[0] > 60.0, values[1] > 30.0, values[2] < 20.0]
    x0, y0, width, height, ymax = 1.0, 0.9, 10.5, 5.0, 80.0
    bar_w = 1.25
    parts = [
        r"\definecolor{passblue}{RGB}{143,169,199}",
        r"\definecolor{failred}{RGB}{217,124,116}",
        r"\definecolor{gridgray}{RGB}{214,219,225}",
        rf"\draw[->,line width=0.45pt] ({x0},{y0}) -- ({x0 + width + 0.25},{y0});",
        rf"\draw[->,line width=0.45pt] ({x0},{y0}) -- ({x0},{y0 + height + 0.35}) node[above]{{比例/\%}};",
    ]
    for tick in range(0, 81, 20):
        y = y0 + tick / ymax * height
        parts.append(rf"\draw[gridgray,line width=0.25pt] ({x0},{y:.3f}) -- ({x0 + width},{y:.3f});")
        parts.append(rf"\node[left] at ({x0 - 0.08},{y:.3f}) {{{tick}}};")
    for i, (value, label, threshold, direction, ok) in enumerate(zip(values, labels, thresholds, directions, passed)):
        cx = x0 + 1.45 + i * 3.35
        y = y0 + value / ymax * height
        ty = y0 + threshold / ymax * height
        color = "passblue" if ok else "failred"
        parts.append(rf"\filldraw[fill={color},draw=black,line width=0.35pt] ({cx - bar_w / 2:.3f},{y0}) rectangle ({cx + bar_w / 2:.3f},{y:.3f});")
        parts.append(rf"\draw[dashed,line width=0.45pt] ({cx - 0.85:.3f},{ty:.3f}) -- ({cx + 0.85:.3f},{ty:.3f});")
        parts.append(rf"\node[above] at ({cx:.3f},{y + 0.08:.3f}) {{{value:.1f}\%}};")
        parts.append(rf"\node[right] at ({cx + 0.95:.3f},{ty:.3f}) {{{direction}}};")
        parts.append(rf"\node[below,align=center] at ({cx:.3f},{y0 - 0.25:.3f}) {{{label}}};")
        parts.append(rf"\node[white] at ({cx:.3f},{max(y0 + 0.35, y - 0.35):.3f}) {{{'满足' if ok else '不满足'}}};")
    _compile_pdf(_latex_document("\n".join(parts), 12.5, 6.8), FIG_DIR / "p1_indicator_thresholds.pdf")


def plot_cost_breakdown(result: dict) -> None:
    costs = result["cost_yuan"]
    labels = ["风电度电成本", "光伏度电成本", "装备运维", "合成氨年化投资", "分时购电"]
    values = np.array([
        costs["wind_lcoe"],
        costs["pv_lcoe"],
        costs["device_opex"],
        costs["nh3_fixed_capex"],
        costs["grid_buy"],
    ])
    colors = ["#2C5C8A", "#8FA9C7", "#3B7F5C", "#D7A77A", "#A65E2E"]
    gross_cost = float(values.sum())

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "legend.fontsize": 8.0,
    }):
        fig, (ax_pie, ax_note) = plt.subplots(
            1, 2, figsize=(6.8, 3.15), gridspec_kw={"width_ratios": [1.18, 1.08]}
        )
        wedges, _ = ax_pie.pie(
            values,
            startangle=105,
            colors=colors,
            wedgeprops={"width": 0.45, "linewidth": 0.9, "edgecolor": "white"},
        )
        ax_pie.text(0, 0.08, "正成本", ha="center", va="center", fontsize=8.5, color="#5A5A5A")
        ax_pie.text(
            0,
            -0.12,
            f"{gross_cost / 10000:.2f} 万元",
            ha="center",
            va="center",
            fontsize=10.2,
            fontweight="semibold",
            color="#222222",
        )
        legend_labels = [
            f"{label}  {value / gross_cost:.1%}"
            for label, value in zip(labels, values)
        ]
        ax_pie.legend(
            wedges,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.25),
            frameon=False,
            ncol=1,
            handlelength=1.1,
            handletextpad=0.55,
        )

        ax_note.axis("off")
        note_lines = [
            ("余电上网收入抵扣", f"-{costs['grid_sell_revenue']:,.2f} 元"),
            ("典型日运行净成本", f"{costs['net_total']:,.2f} 元"),
            ("吨氨成本", f"{costs['per_ton_nh3']:,.2f} 元/t"),
        ]
        ax_note.text(0.02, 0.88, "成本结果", fontsize=9.2, fontweight="semibold", color="#222222")
        ax_note.hlines(0.82, 0.02, 0.98, color="#D9D9D9", linewidth=0.8)
        for row, (label, value) in enumerate(note_lines):
            y = 0.64 - row * 0.22
            ax_note.text(0.02, y, label, fontsize=8.2, color="#5A5A5A", va="center")
            ax_note.text(
                0.98,
                y,
                value,
                fontsize=8.9,
                color="#222222",
                va="center",
                ha="right",
                fontweight="semibold" if row == 2 else "normal",
            )
        ax_note.set_xlim(0, 1)
        ax_note.set_ylim(0, 1)
        fig.tight_layout(pad=0.85)
        fig.savefig(FIG_DIR / "p1_cost_breakdown.pdf", bbox_inches="tight")
        plt.close(fig)


def plot(result: dict, rows: list[dict[str, float]]) -> None:
    plot_power_curves(rows)
    plot_indicator_thresholds(result)
    plot_cost_breakdown(result)


def print_report(result: dict) -> None:
    print("=" * 64)
    print("问题一：典型日满负荷连续运行")
    print("=" * 64)
    for group, values in result.items():
        print(f"\n[{group}]")
        for key, value in values.items():
            print(f"  {key:32s}: {value:14.4f}")


if __name__ == "__main__":
    summary, rows = compute()
    write_outputs(summary, rows)
    plot(summary, rows)
    print_report(summary)
