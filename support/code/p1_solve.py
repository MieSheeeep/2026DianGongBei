"""问题一：典型风光场景下绿电直连电氢氨园区运行指标分析。

题设：电解槽与合成氨装置每日满负荷连续运行，不计园区功率损耗。

执行：python support/code/p1_solve.py
产出：
  support/results/p1/p1_hourly_power.csv     每小时功率序列
  support/results/p1/p1_summary.json         电量/指标/成本汇总
  support/results/p1/p1_power_curves.png     4 条功率曲线（PNG）
  figures/p1_power_curves.pdf                同图矢量版（论文用）
  figures/p1_indicator_thresholds.pdf        绿电指标与阈值对比图
  figures/p1_cost_breakdown.pdf              典型日成本构成图
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    WIND_CAPACITY_MW, PV_CAPACITY_MW, LOAD_PEAK_MW,
    ALK_CAPACITY_MW, PEM_CAPACITY_MW, NH3_CAPACITY_MW,
    NH3_RATE_TPH, ALK_H2_RATE_KGH, PEM_H2_RATE_KGH,
    ALK_OPEX_YUAN_PER_KWH, PEM_OPEX_YUAN_PER_KWH, NH3_OPEX_YUAN_PER_KWH,
    WIND_LCOE_YUAN_PER_KWH, PV_LCOE_YUAN_PER_KWH,
    SELL_PRICE_YUAN_PER_KWH, buy_price_schedule,
)
from loaders import load_typical_load, load_typical_wind_pv

# ---- 路径 ----
HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p1"
RESULT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR = HERE.parent.parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ---- matplotlib 中文 ----
rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False
rcParams["pdf.fonttype"] = 42
rcParams["ps.fonttype"] = 42
rcParams["axes.titleweight"] = "semibold"
rcParams["axes.titlesize"] = 10
rcParams["axes.labelsize"] = 9
rcParams["xtick.labelsize"] = 8
rcParams["ytick.labelsize"] = 8
rcParams["legend.fontsize"] = 8


def compute() -> dict:
    # ---- 输入：标幺曲线 ----
    load_pu = load_typical_load()
    wind_pu, pv_pu = load_typical_wind_pv()

    # ---- 功率序列（MW，长度 24） ----
    p_load = load_pu * LOAD_PEAK_MW
    p_wind = wind_pu * WIND_CAPACITY_MW
    p_pv = pv_pu * PV_CAPACITY_MW
    p_re = p_wind + p_pv

    p_alk = np.full(24, ALK_CAPACITY_MW)
    p_pem = np.full(24, PEM_CAPACITY_MW)
    p_nh3 = np.full(24, NH3_CAPACITY_MW)
    p_h2nh3 = p_alk + p_pem + p_nh3
    p_use = p_h2nh3 + p_load                            # 园区内部用电

    delta = p_re - p_use
    p_sell = np.maximum(delta, 0.0)
    p_buy = -np.minimum(delta, 0.0)

    # ---- 电量（MWh，dt = 1 h） ----
    e_load = float(p_load.sum())
    e_wind = float(p_wind.sum())
    e_pv = float(p_pv.sum())
    e_re = float(p_re.sum())
    e_alk = float(p_alk.sum())
    e_pem = float(p_pem.sum())
    e_nh3 = float(p_nh3.sum())
    e_use = float(p_use.sum())                          # 园区内部用电
    e_sell = float(p_sell.sum())
    e_buy = float(p_buy.sum())
    e_self = e_re - e_sell                              # 自发自用

    # ---- 绿电直连三项指标 ----
    # 我们对"总用电量"采用"宽口径"：自用 + 网购 + 上网 = 风光 + 网购
    # 这样指标 1 化简为 自用/风光；并与官方公式逐字对应。
    e_total_wide = e_self + e_buy + e_sell              # = e_re + e_buy
    ratio_self_use = e_self / e_re                      # >60%
    ratio_green_wide = e_self / e_total_wide            # 宽口径 >30%
    ratio_green_narrow = e_self / e_use                 # 窄口径（=自用/园区用电）
    ratio_grid_sell = e_sell / e_re                     # <20%

    # ---- 吨氨成本 ----
    nh3_tons = NH3_RATE_TPH * 24.0
    h2_kg = (ALK_H2_RATE_KGH + PEM_H2_RATE_KGH) * 24.0

    buy_price = np.asarray(buy_price_schedule())        # 元/kWh
    # 注意：功率单位 MW，dt 1 h => kWh = MW × 1000
    cost_grid_buy = float((p_buy * 1000.0 * buy_price).sum())
    revenue_grid_sell = float((p_sell * 1000.0 * SELL_PRICE_YUAN_PER_KWH).sum())

    cost_opex = (
        e_alk * 1000.0 * ALK_OPEX_YUAN_PER_KWH
        + e_pem * 1000.0 * PEM_OPEX_YUAN_PER_KWH
        + e_nh3 * 1000.0 * NH3_OPEX_YUAN_PER_KWH
    )
    cost_wind = e_wind * 1000.0 * WIND_LCOE_YUAN_PER_KWH
    cost_pv = e_pv * 1000.0 * PV_LCOE_YUAN_PER_KWH

    net_cost = cost_wind + cost_pv + cost_opex + cost_grid_buy - revenue_grid_sell
    cost_per_ton_nh3 = net_cost / nh3_tons

    result = {
        "energy_MWh": {
            "wind": e_wind, "pv": e_pv, "renewable": e_re,
            "load": e_load, "alk": e_alk, "pem": e_pem, "nh3": e_nh3,
            "internal_use": e_use, "self_use": e_self,
            "grid_sell": e_sell, "grid_buy": e_buy,
            "total_wide": e_total_wide,
        },
        "production": {
            "nh3_tons_per_day": nh3_tons,
            "h2_kg_per_day": h2_kg,
        },
        "indicators_pct": {
            "self_use_ratio": ratio_self_use * 100,            # >60
            "green_in_total_wide": ratio_green_wide * 100,     # >30 (宽)
            "green_in_internal_use_narrow": ratio_green_narrow * 100,  # >30 (窄，参考)
            "grid_sell_ratio": ratio_grid_sell * 100,          # <20
        },
        "cost_yuan": {
            "wind_lcoe": cost_wind,
            "pv_lcoe": cost_pv,
            "device_opex": cost_opex,
            "grid_buy": cost_grid_buy,
            "grid_sell_revenue": revenue_grid_sell,
            "net_total": net_cost,
            "per_ton_nh3": cost_per_ton_nh3,
        },
    }

    df = pd.DataFrame({
        "hour": np.arange(24),
        "load_MW": p_load,
        "wind_MW": p_wind,
        "pv_MW": p_pv,
        "renewable_MW": p_re,
        "alk_MW": p_alk,
        "pem_MW": p_pem,
        "nh3_MW": p_nh3,
        "internal_use_MW": p_use,
        "grid_buy_MW": p_buy,
        "grid_sell_MW": p_sell,
        "buy_price_yuan_per_kwh": buy_price,
    })
    df.to_csv(RESULT_DIR / "p1_hourly_power.csv", index=False)

    with open(RESULT_DIR / "p1_summary.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def _style_axes(ax: plt.Axes, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(colors="#222222", width=0.7, length=3)
    ax.grid(True, axis=grid_axis, color="#D9DDE3", linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)


def plot_power_curves() -> None:
    df = pd.read_csv(RESULT_DIR / "p1_hourly_power.csv")
    h_mid = df["hour"].to_numpy() + 0.5

    # 论文风格：局部设置，不影响其他图
    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.8,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
        "xtick.minor.size": 2.0,
        "ytick.minor.size": 2.0,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(6.6, 3.6))

        # 低饱和、色盲友好配色 + 黑白打印可区分线型
        curve_styles = [
            {
                "col": "internal_use_MW",
                "label": "园区用电功率",
                "color": "#2C5C8A",
                "linestyle": "-",
                "linewidth": 2.2,
                "marker": "o",
            },
            {
                "col": "renewable_MW",
                "label": "风光发电功率",
                "color": "#3B7F5C",
                "linestyle": "-",
                "linewidth": 2.2,
                "marker": "s",
            },
            {
                "col": "grid_buy_MW",
                "label": "网购功率",
                "color": "#A65E2E",
                "linestyle": "--",
                "linewidth": 1.8,
                "marker": "^",
            },
            {
                "col": "grid_sell_MW",
                "label": "上网功率",
                "color": "#6F5B9A",
                "linestyle": "-.",
                "linewidth": 1.8,
                "marker": "D",
            },
        ]

        for style in curve_styles:
            ax.plot(
                h_mid,
                df[style["col"]],
                label=style["label"],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                marker=style["marker"],
                markersize=3.2,
                markerfacecolor="white",
                markeredgewidth=0.8,
                markevery=2,
                solid_capstyle="round",
                zorder=3,
            )

        ax.set_xlabel("时段 / h")
        ax.set_ylabel("功率 / MW")
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlim(0, 24)
        ax.set_ylim(bottom=0)

        _style_axes(ax)
        ax.grid(True, which="major", axis="both", linewidth=0.45, alpha=0.28)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(
            loc="lower center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=4,
            frameon=False,
            handlelength=2.4,
            columnspacing=1.2,
            borderaxespad=0.0,
        )

        fig.tight_layout(rect=[0, 0, 1, 0.93])
        fig.savefig(RESULT_DIR / "p1_power_curves.png", dpi=300, bbox_inches="tight")
        fig.savefig(FIG_DIR / "p1_power_curves.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_indicator_thresholds(result: dict) -> None:
    labels = ["新能源自发\n自用比例", "总用电\n绿电比例", "新能源\n上网比例"]
    values = np.array([
        result["indicators_pct"]["self_use_ratio"],
        result["indicators_pct"]["green_in_total_wide"],
        result["indicators_pct"]["grid_sell_ratio"],
    ])
    thresholds = np.array([60.0, 30.0, 20.0])
    threshold_notes = ["> 60%", "> 30%", "< 20%"]
    passed = np.array([
        values[0] > thresholds[0],
        values[1] > thresholds[1],
        values[2] < thresholds[2],
    ])

    x = np.arange(len(labels))
    width = 0.50

    pass_fill = "#8FA9C7"
    fail_fill = "#D97C74"
    edge = "#2B2B2B"
    threshold_color = "#3A3A3A"
    text_main = "#222222"
    text_sub = "#5A5A5A"
    grid_color = "#D9D9D9"
    fills = [pass_fill if ok else fail_fill for ok in passed]

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 0.0,
        "ytick.major.size": 3.2,
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "hatch.linewidth": 0.8,
    }):
        fig, ax = plt.subplots(figsize=(5.8, 3.25))
        bars = ax.bar(
            x,
            values,
            width=width,
            color=fills,
            edgecolor=edge,
            linewidth=0.9,
            zorder=3,
        )
        for idx, bar in enumerate(bars):
            if not passed[idx]:
                bar.set_hatch("//")

        for idx, (value, threshold, note, ok) in enumerate(zip(values, thresholds, threshold_notes, passed)):
            ax.hlines(
                y=threshold,
                xmin=idx - width * 0.55,
                xmax=idx + width * 0.55,
                colors=threshold_color,
                linewidth=1.0,
                linestyles=(0, (4, 2)),
                zorder=4,
            )
            ax.plot(
                idx + width * 0.62,
                threshold,
                marker="o",
                markersize=4.2,
                markerfacecolor="white",
                markeredgecolor=threshold_color,
                markeredgewidth=0.95,
                zorder=5,
            )
            ax.text(
                idx,
                value + 2.0,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10.0,
                color=text_main,
                fontweight="semibold",
            )
            ax.text(
                idx + width * 0.72,
                threshold + 0.1,
                note,
                ha="left",
                va="bottom",
                fontsize=8.2,
                color=text_sub,
            )
            ax.text(
                idx,
                max(value - 5.0, 4.0),
                "满足" if ok else "不满足",
                ha="center",
                va="top",
                fontsize=8.2,
                color="white",
                fontweight="semibold",
                bbox={
                    "boxstyle": "round,pad=0.18",
                    "facecolor": "#5F7896" if ok else "#B9655E",
                    "edgecolor": "none",
                    "alpha": 0.98,
                },
                zorder=6,
            )

        ax.set_ylabel("比例 / %")
        ax.set_xticks(x, labels)
        ax.set_ylim(0, 80)
        ax.set_yticks(np.arange(0, 81, 20))
        ax.grid(True, axis="y", linewidth=0.55, color=grid_color, alpha=0.85, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_linewidth(0.85)
        ax.spines["bottom"].set_linewidth(0.85)
        ax.text(
            0.985,
            0.965,
            "○ 阈值要求",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8.0,
            color=text_sub,
        )
        ax.margins(x=0.06)
        fig.tight_layout(pad=0.85)
        fig.savefig(FIG_DIR / "p1_indicator_thresholds.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_cost_breakdown(result: dict) -> None:
    costs = result["cost_yuan"]
    labels = ["风电度电成本", "光伏度电成本", "装备运维", "分时购电"]
    values = np.array([costs["wind_lcoe"], costs["pv_lcoe"], costs["device_opex"], costs["grid_buy"]])
    colors = ["#2C5C8A", "#8FA9C7", "#3B7F5C", "#A65E2E"]
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
            1, 2, figsize=(6.6, 3.1), gridspec_kw={"width_ratios": [1.12, 1.0]}
        )
        wedges, _ = ax_pie.pie(
            values,
            startangle=102,
            colors=colors,
            wedgeprops={"width": 0.46, "linewidth": 0.9, "edgecolor": "white"},
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
        shares = [f"{label}  {value / gross_cost:.1%}" for label, value in zip(labels, values)]
        ax_pie.legend(
            wedges,
            shares,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.20),
            frameon=False,
            ncol=1,
            handlelength=1.15,
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
        fig.tight_layout(pad=0.9)
        fig.savefig(FIG_DIR / "p1_cost_breakdown.pdf", bbox_inches="tight")
        plt.close(fig)


def plot(result: dict) -> None:
    plot_power_curves()
    plot_indicator_thresholds(result)
    plot_cost_breakdown(result)


def print_report(result: dict) -> None:
    print("=" * 64)
    print("问题一：典型日满负荷连续运行")
    print("=" * 64)
    print("\n[产量]")
    for k, v in result["production"].items():
        print(f"  {k:32s}: {v:12.3f}")
    print("\n[电量 / MWh]")
    for k, v in result["energy_MWh"].items():
        print(f"  {k:32s}: {v:12.3f}")
    print("\n[绿电指标 / %]")
    for k, v in result["indicators_pct"].items():
        print(f"  {k:32s}: {v:12.3f}")
    print("\n[成本 / 元]")
    for k, v in result["cost_yuan"].items():
        print(f"  {k:32s}: {v:14.2f}")


if __name__ == "__main__":
    r = compute()
    plot(r)
    print_report(r)
