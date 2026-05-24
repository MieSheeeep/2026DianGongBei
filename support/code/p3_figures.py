"""Generate paper figures for problem three."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
P2_RESULT_DIR = HERE.parent / "results" / "p2"
P3_RESULT_DIR = HERE.parent / "results" / "p3"
FIG_DIR = HERE.parents[1] / "figures"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _style_axes(ax: plt.Axes, axis: str = "y") -> None:
    ax.grid(True, axis=axis, linewidth=0.45, color="#D9D9D9", alpha=0.85)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.85)
    ax.spines["bottom"].set_linewidth(0.85)


def plot_dispatch_example() -> None:
    rows_all = _read_csv(P3_RESULT_DIR / "p3_hourly_cases.csv")
    rows = [
        row for row in rows_all
        if row["scenario_id"] == "W4_P1" and float(row["target_NH3_t_per_day"]) == 36.0
    ]
    if len(rows) != 24:
        rows = [row for row in rows_all if float(row["target_NH3_t_per_day"]) == 36.0][:24]

    h_mid = np.array([float(row["hour"]) + 0.5 for row in rows])
    p_re = np.array([float(row["P_re_MW"]) for row in rows])
    p_use = np.array([
        float(row["P_load_MW"]) + float(row["P_alk_MW"]) + float(row["P_pem_MW"]) + float(row["P_nh3_MW"])
        for row in rows
    ])
    p_buy = np.array([float(row["P_buy_MW"]) for row in rows])
    p_sell = np.array([float(row["P_sell_MW"]) for row in rows])
    alpha = np.array([float(row["alpha"]) for row in rows])

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
        fig, ax = plt.subplots(figsize=(6.8, 3.8))
        ax.plot(h_mid, p_use, label="园区用电功率", color="#2C5C8A", linewidth=2.2, marker="o", markersize=3.0, markerfacecolor="white", markevery=2)
        ax.plot(h_mid, p_re, label="风光发电功率", color="#3B7F5C", linewidth=2.2, marker="s", markersize=3.0, markerfacecolor="white", markevery=2)
        ax.plot(h_mid, p_buy, label="网购功率", color="#A65E2E", linewidth=1.8, linestyle="--", marker="^", markersize=2.8, markerfacecolor="white", markevery=2)
        ax.plot(h_mid, p_sell, label="上网功率", color="#6F5B9A", linewidth=1.8, linestyle="-.", marker="D", markersize=2.7, markerfacecolor="white", markevery=2)
        ax.set_xlabel("时段 / h")
        ax.set_ylabel("功率 / MW")
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlim(0, 24)
        ax.set_ylim(bottom=0)
        _style_axes(ax)

        ax2 = ax.twinx()
        ax2.fill_between(h_mid, alpha, 0.1, step="mid", color="#8FA9C7", alpha=0.28, label="负荷率")
        ax2.plot(h_mid, alpha, color="#5F7896", linewidth=1.5)
        ax2.set_ylabel("负荷率")
        ax2.set_ylim(0, 1.05)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_linewidth(0.85)
        ax2.tick_params(labelsize=9, direction="in")

        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=5, frameon=False, handlelength=2.1, columnspacing=1.0)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        fig.savefig(FIG_DIR / "p3_dispatch_example.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_cost_compare() -> None:
    with (P2_RESULT_DIR / "p2_summary.json").open("r", encoding="utf-8") as f:
        p2 = json.load(f)
    with (P3_RESULT_DIR / "p3_summary.json").open("r", encoding="utf-8") as f:
        p3 = json.load(f)
    q = np.array([36, 45, 54, 63, 72], dtype=float)
    p2_cost = np.array([p2["annual_by_production"][str(int(v))]["unit_cost_yuan_per_t"] for v in q])
    p3_cost = np.array([p3["annual_by_production"][str(int(v))]["unit_cost_yuan_per_t"] for v in q])
    x = np.arange(len(q))
    width = 0.34

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(6.2, 3.35))
        ax.bar(x - width / 2, p2_cost, width=width, label="问题二：离散开停", color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.8)
        ax.bar(x + width / 2, p3_cost, width=width, label="问题三：连续调节", color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.8)
        for i, (a, b) in enumerate(zip(p2_cost, p3_cost)):
            ax.text(i, min(a, b) - 180, f"{a-b:.0f}", ha="center", va="top", fontsize=8.0, color="#3B7F5C")
        ax.set_xticks(x, [f"{int(v)}" for v in q])
        ax.set_xlabel("目标日产量 / (t/d)")
        ax.set_ylabel("吨氨成本 / (元/t)")
        _style_axes(ax)
        ax.legend(frameon=False, loc="upper left")
        fig.tight_layout(pad=0.9)
        fig.savefig(FIG_DIR / "p3_cost_compare_p2.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_indicator_compare() -> None:
    with (P2_RESULT_DIR / "p2_summary.json").open("r", encoding="utf-8") as f:
        p2 = json.load(f)
    with (P3_RESULT_DIR / "p3_summary.json").open("r", encoding="utf-8") as f:
        p3 = json.load(f)
    q_key = "36"
    p2_g = p2["annual_by_production"][q_key]["green_indicators"]
    p3_g = p3["annual_by_production"][q_key]["green_indicators"]
    labels = ["自发自用", "绿电比例", "上网比例"]
    p2_vals = np.array([p2_g["self_use_ratio"], p2_g["green_ratio"], p2_g["sell_ratio"]]) * 100
    p3_vals = np.array([p3_g["self_use_ratio"], p3_g["green_ratio"], p3_g["sell_ratio"]]) * 100
    thresholds = [60.0, 30.0, 20.0]
    x = np.arange(3)
    width = 0.32

    with plt.rc_context({
        "font.family": ["Times New Roman", "SimSun"],
        "axes.unicode_minus": False,
        "axes.linewidth": 0.85,
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }):
        fig, ax = plt.subplots(figsize=(5.9, 3.35))
        ax.bar(x - width / 2, p2_vals, width=width, label="问题二", color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.8)
        ax.bar(x + width / 2, p3_vals, width=width, label="问题三", color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.8)
        for i, t in enumerate(thresholds):
            ax.hlines(t, i - 0.42, i + 0.42, colors="#3A3A3A", linestyles=(0, (4, 2)), linewidth=1.0)
            ax.text(i + 0.45, t, f"{t:.0f}%", ha="left", va="center", fontsize=8.0, color="#5A5A5A")
        for i, val in enumerate(p3_vals):
            ax.text(i + width / 2, val + 2.0, f"{val:.1f}%", ha="center", va="bottom", fontsize=8.2, color="#222222")
        ax.set_xticks(x, labels)
        ax.set_ylabel("比例 / %")
        ax.set_ylim(0, 80)
        _style_axes(ax)
        ax.legend(frameon=False, loc="upper right")
        fig.tight_layout(pad=0.85)
        fig.savefig(FIG_DIR / "p3_indicator_compare_p2.pdf", bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot_dispatch_example()
    plot_cost_compare()
    plot_indicator_compare()


if __name__ == "__main__":
    main()
