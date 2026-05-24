"""Generate paper figures for problem two."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p2"
FIG_DIR = HERE.parents[1] / "figures"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (RESULT_DIR / name).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(True, axis="y", linewidth=0.45, color="#D9D9D9", alpha=0.85)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.85)
    ax.spines["bottom"].set_linewidth(0.85)


def plot_typical_schedule() -> None:
    daily = _read_csv("p2_typical_daily.csv")
    hourly = _read_csv("p2_typical_hourly.csv")
    best = min(daily, key=lambda row: float(row["unit_cost_yuan_per_t"]))
    target = float(best["target_NH3_t_per_day"])
    rows = [row for row in hourly if float(row["target_NH3_t_per_day"]) == target]

    hour_mid = np.array([float(row["hour"]) + 0.5 for row in rows])
    p_re = np.array([float(row["P_re_MW"]) for row in rows])
    p_use = np.array([
        float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"])
        for row in rows
    ])
    p_buy = np.array([float(row["P_buy_MW"]) for row in rows])
    p_sell = np.array([float(row["P_sell_MW"]) for row in rows])
    u_on = np.array([int(float(row["u_on"])) for row in rows])

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.8,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(6.6, 3.6))
        for h, on in enumerate(u_on):
            if on:
                ax.axvspan(h, h + 1, color="#E8EEF5", alpha=0.65, zorder=0)

        ax.plot(hour_mid, p_use, label="园区用电功率", color="#2C5C8A", linewidth=2.2, marker="o", markersize=3.2, markerfacecolor="white", markevery=2)
        ax.plot(hour_mid, p_re, label="风光发电功率", color="#3B7F5C", linewidth=2.2, marker="s", markersize=3.2, markerfacecolor="white", markevery=2)
        ax.plot(hour_mid, p_buy, label="网购功率", color="#A65E2E", linewidth=1.8, linestyle="--", marker="^", markersize=3.0, markerfacecolor="white", markevery=2)
        ax.plot(hour_mid, p_sell, label="上网功率", color="#6F5B9A", linewidth=1.8, linestyle="-.", marker="D", markersize=2.9, markerfacecolor="white", markevery=2)

        ax.set_xlabel("时段 / h")
        ax.set_ylabel("功率 / MW")
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlim(0, 24)
        ax.set_ylim(bottom=0)
        _style_axes(ax)
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, handlelength=2.4, columnspacing=1.2)
        ax.text(0.02, 0.93, "浅蓝背景为开机时段", transform=ax.transAxes, ha="left", va="top", fontsize=8.2, color="#5A5A5A")
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        fig.savefig(FIG_DIR / "p2_typical_schedule.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_cost_by_production() -> None:
    typical = sorted(_read_csv("p2_typical_daily.csv"), key=lambda row: float(row["target_NH3_t_per_day"]))
    with (RESULT_DIR / "p2_summary.json").open("r", encoding="utf-8") as f:
        summary = json.load(f)
    q = np.array([float(row["target_NH3_t_per_day"]) for row in typical])
    typical_cost = np.array([float(row["unit_cost_yuan_per_t"]) for row in typical])
    annual_cost = np.array([summary["annual_by_production"][str(int(value))]["unit_cost_yuan_per_t"] for value in q])

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(6.2, 3.45))
        ax.plot(q, typical_cost, label="典型场景", color="#2C5C8A", linewidth=2.1, marker="o", markersize=4.2, markerfacecolor="white")
        ax.plot(q, annual_cost, label="24 场景全年折算", color="#A65E2E", linewidth=2.1, marker="s", markersize=4.0, markerfacecolor="white")
        ax.set_xlabel("目标日产量 / (t/d)")
        ax.set_ylabel("吨氨成本 / (元/t)")
        ax.set_xticks(q)
        _style_axes(ax)
        ax.legend(frameon=False, loc="upper left")
        best_idx = int(np.argmin(typical_cost))
        ax.scatter([q[best_idx]], [typical_cost[best_idx]], s=55, color="#3B7F5C", zorder=5)
        ax.text(q[best_idx] + 1.0, typical_cost[best_idx], "典型最优", ha="left", va="center", fontsize=8.3, color="#3B7F5C")
        fig.tight_layout(pad=0.9)
        fig.savefig(FIG_DIR / "p2_cost_by_production.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_indicator_distribution() -> None:
    rows = _read_csv("p2_daily_cases.csv")
    labels = ["自发自用", "绿电比例", "上网比例"]
    data = [
        np.array([float(row["self_use_ratio"]) * 100 for row in rows]),
        np.array([float(row["green_ratio"]) * 100 for row in rows]),
        np.array([float(row["sell_ratio"]) * 100 for row in rows]),
    ]
    thresholds = [60.0, 30.0, 20.0]

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "axes.labelsize": 10.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(5.9, 3.3))
        parts = ax.violinplot(data, positions=np.arange(3), widths=0.58, showmeans=True, showextrema=False)
        colors = ["#8FA9C7", "#92B39A", "#D7A77A"]
        for body, color in zip(parts["bodies"], colors):
            body.set_facecolor(color)
            body.set_edgecolor("#2B2B2B")
            body.set_linewidth(0.8)
            body.set_alpha(0.88)
        parts["cmeans"].set_color("#2B2B2B")
        parts["cmeans"].set_linewidth(1.0)
        for i, t in enumerate(thresholds):
            ax.hlines(t, i - 0.34, i + 0.34, colors="#3A3A3A", linestyles=(0, (4, 2)), linewidth=1.0)
            ax.text(i + 0.38, t, f"{t:.0f}%", ha="left", va="center", fontsize=8.0, color="#5A5A5A")
        ax.set_xticks(np.arange(3), labels)
        ax.set_ylabel("比例 / %")
        ax.set_ylim(0, 105)
        _style_axes(ax)
        fig.tight_layout(pad=0.85)
        fig.savefig(FIG_DIR / "p2_indicator_distribution.pdf", bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot_typical_schedule()
    plot_cost_by_production()
    plot_indicator_distribution()


if __name__ == "__main__":
    main()
