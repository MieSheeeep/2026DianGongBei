"""问题四论文图表绘制。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULT_DIR = HERE.parent / "results" / "p4"
P3_RESULT_DIR = HERE.parent / "results" / "p3"
FIG_DIR = HERE.parents[1] / "figures"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (RESULT_DIR / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _style_axes(ax: plt.Axes, axis: str = "y") -> None:
    ax.grid(True, axis=axis, linewidth=0.45, color="#D9D9D9", alpha=0.85)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.85)
    ax.spines["bottom"].set_linewidth(0.85)


def plot_offgrid_dispatch_example() -> None:
    rows = [r for r in _read_csv("p4_offgrid_hourly_cases.csv") if r["scenario_id"] == "W4_P1"]
    h = np.array([float(r["hour"]) + 0.5 for r in rows])
    p_re = np.array([float(r["P_re_MW"]) for r in rows])
    p_use = np.array([float(r["P_load_MW"]) + float(r["P_plant_MW"]) for r in rows])
    p_curt = np.array([float(r["P_curtail_MW"]) for r in rows])
    ratio = np.array([float(r["plant_load_ratio"]) for r in rows])

    with plt.rc_context({"font.family": ["Times New Roman", "SimSun"], "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig, ax = plt.subplots(figsize=(6.7, 3.65))
        ax.plot(h, p_re, label="风光发电功率", color="#3B7F5C", linewidth=2.2, marker="s", markersize=3.0, markerfacecolor="white", markevery=2)
        ax.plot(h, p_use, label="园区用电功率", color="#2C5C8A", linewidth=2.2, marker="o", markersize=3.0, markerfacecolor="white", markevery=2)
        ax.plot(h, p_curt, label="弃电功率", color="#A65E2E", linewidth=1.8, linestyle="--", marker="^", markersize=2.8, markerfacecolor="white", markevery=2)
        ax.set_xlabel("时段 / h")
        ax.set_ylabel("功率 / MW")
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlim(0, 24)
        ax.set_ylim(bottom=0)
        _style_axes(ax)
        ax2 = ax.twinx()
        ax2.fill_between(h, ratio, 0, step="mid", color="#8FA9C7", alpha=0.25, label="负荷率")
        ax2.plot(h, ratio, color="#5F7896", linewidth=1.4)
        ax2.set_ylabel("负荷率")
        ax2.set_ylim(0, 1.05)
        ax2.spines["top"].set_visible(False)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        fig.savefig(FIG_DIR / "p4_offgrid_dispatch_example.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_curtailment_by_scenario() -> None:
    no_rows = _read_csv("p4_offgrid_daily_cases.csv")
    st_rows = _read_csv("p4_storage_daily_cases.csv")
    labels = [r["scenario_id"] for r in no_rows]
    no = np.array([float(r["daily_curtail_MWh"]) for r in no_rows])
    st_by_id = {r["scenario_id"]: float(r["daily_curtail_MWh"]) for r in st_rows}
    st = np.array([st_by_id[label] for label in labels])
    x = np.arange(len(labels))

    with plt.rc_context({"font.family": ["Times New Roman", "SimSun"], "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig, ax = plt.subplots(figsize=(7.0, 3.4))
        ax.bar(x, no, color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.55, label="无储能")
        ax.bar(x, st, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.55, label="有储能")
        ax.set_xticks(x, labels, rotation=60, ha="right")
        ax.set_ylabel("日弃电量 / MWh")
        _style_axes(ax)
        ax.legend(frameon=False, loc="upper left")
        fig.tight_layout(pad=0.8)
        fig.savefig(FIG_DIR / "p4_curtailment_by_scenario.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_storage_dispatch() -> None:
    rows = [r for r in _read_csv("p4_storage_hourly_cases.csv") if r["scenario_id"] == "W4_P1"]
    h = np.array([float(r["hour"]) + 0.5 for r in rows])
    ch = np.array([float(r["P_charge_MW"]) for r in rows])
    dis = np.array([float(r["P_discharge_MW"]) for r in rows])
    soc = np.array([float(r["SOC_MWh"]) for r in rows])
    ratio = np.array([float(r["plant_load_ratio"]) for r in rows])

    with plt.rc_context({"font.family": ["Times New Roman", "SimSun"], "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig, ax = plt.subplots(figsize=(6.7, 3.55))
        ax.bar(h, ch, width=0.72, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.45, label="充电功率")
        ax.bar(h, -dis, width=0.72, color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.45, label="放电功率")
        ax.set_xlabel("时段 / h")
        ax.set_ylabel("充放电功率 / MW")
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlim(0, 24)
        _style_axes(ax)
        ax2 = ax.twinx()
        ax2.plot(h, soc, color="#2C5C8A", linewidth=2.0, marker="o", markersize=3.0, markerfacecolor="white", markevery=2, label="储能电量")
        ax2.plot(h, ratio * max(float(soc.max()), 1.0), color="#3B7F5C", linewidth=1.5, linestyle="--", label="负荷率(缩放)")
        ax2.set_ylabel("储能电量 / MWh")
        ax2.spines["top"].set_visible(False)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        fig.savefig(FIG_DIR / "p4_storage_dispatch.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_mode_cost_compare() -> None:
    p4 = _read_json(RESULT_DIR / "p4_summary.json")
    p3 = _read_json(P3_RESULT_DIR / "p3_summary.json")
    no_storage = p4["offgrid_no_storage"]
    storage = p4["storage"]["summary"]
    labels = ["联网连续", "离网无储能", "离网有储能"]
    costs = [
        p3["annual_recommended"]["unit_cost_yuan_per_t"],
        no_storage["annual_unit_cost_yuan_per_t"],
        storage["annual_unit_cost_yuan_per_t"],
    ]
    prod = [
        p3["annual_recommended"]["total_production_t"],
        no_storage["annual_total_NH3_t"],
        storage["annual_total_NH3_t"],
    ]
    x = np.arange(3)

    with plt.rc_context({"font.family": ["Times New Roman", "SimSun"], "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig, ax = plt.subplots(figsize=(5.9, 3.35))
        ax.bar(x, costs, color=["#8FA9C7", "#D7A77A", "#92B39A"], edgecolor="#2B2B2B", linewidth=0.8)
        for i, (c, p) in enumerate(zip(costs, prod)):
            ax.text(i, c + 80, f"{c:.0f}\n{p/10000:.2f}万t", ha="center", va="bottom", fontsize=8.0, color="#222222")
        ax.set_xticks(x, labels)
        ax.set_ylabel("吨氨成本 / (元/t)")
        ax.set_ylim(0, max(costs) * 1.20)
        _style_axes(ax)
        fig.tight_layout(pad=0.9)
        fig.savefig(FIG_DIR / "p4_mode_cost_compare.pdf", bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot_offgrid_dispatch_example()
    plot_curtailment_by_scenario()
    plot_storage_dispatch()
    plot_mode_cost_compare()


if __name__ == "__main__":
    main()
