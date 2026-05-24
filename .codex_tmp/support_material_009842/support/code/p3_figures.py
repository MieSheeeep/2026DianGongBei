from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
P3_RESULT_DIR = ROOT / "support" / "results" / "p3"
P2_RESULT_DIR = ROOT / "support" / "results" / "p2"
FIGURE_DIR = ROOT / "figures"

PRODUCTION_LEVELS = [36, 45, 54, 63, 72]
INDICATOR_KEYS = ["self_use_ratio", "green_ratio", "sell_ratio"]
INDICATOR_THRESHOLDS = {
    "self_use_ratio": 0.60,
    "green_ratio": 0.30,
    "sell_ratio": 0.20,
}

ZH = {
    "hour": "时刻/h",
    "power": "功率/MW",
    "ratio": "负荷率/比例",
    "production": "日产量/(t/d)",
    "unit_cost": "吨氨成本/(元/t)",
    "energy": "电量/MWh",
    "scenario": "场景序号",
    "renewable": "风光发电",
    "use": "园区总用电",
    "buy": "购电",
    "sell": "上网",
    "load_ratio": "统一负荷率",
    "nh3": "产氨量/(t/h)",
    "self_use_ratio": "自发自用比例",
    "green_ratio": "总用电量绿电比例",
    "sell_ratio": "上网比例",
    "p2": "问题二",
    "p3": "问题三",
    "buy_energy": "全年购电量",
    "sell_energy": "全年上网量",
}

EN = {
    "hour": "Hour",
    "power": "Power (MW)",
    "ratio": "Load ratio / ratio",
    "production": "Daily production (t/d)",
    "unit_cost": "Unit cost (yuan/t)",
    "energy": "Energy (MWh)",
    "scenario": "Scenario index",
    "renewable": "Renewable",
    "use": "Total use",
    "buy": "Grid buy",
    "sell": "Grid export",
    "load_ratio": "Plant load ratio",
    "nh3": "NH3 output (t/h)",
    "self_use_ratio": "Self-use ratio",
    "green_ratio": "Green ratio",
    "sell_ratio": "Export ratio",
    "p2": "P2",
    "p3": "P3",
    "buy_energy": "Annual grid buy",
    "sell_energy": "Annual grid export",
}


def choose_labels() -> dict[str, str]:
    candidates = (
        "SimHei",
        "Microsoft YaHei",
        "Microsoft YaHei UI",
        "KaiTi",
        "FangSong",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
    )
    installed = {font.name for font in fm.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return ZH
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return EN


LABEL = choose_labels()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fobj:
        return list(csv.DictReader(fobj))


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fobj:
        return json.load(fobj)


def f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def save_pdf(fig: plt.Figure, name: str) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / name
    fig.tight_layout()
    fig.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return path


def style_axes(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.grid(True, axis=grid_axis, linewidth=0.5, color="#D9DDE3", alpha=0.85)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.85)
    ax.spines["bottom"].set_linewidth(0.85)
    ax.tick_params(width=0.7, length=3)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def best_representative_case(daily_rows: list[dict[str, str]], summary: dict) -> tuple[str, float]:
    target = float(summary["annual_recommended"]["unit_cost_yuan_per_t"])
    candidates = [row for row in daily_rows if f(row, "target_NH3_t_per_day") == 36.0]
    row = min(candidates, key=lambda item: abs(f(item, "unit_cost_yuan_per_t") - target))
    return row["scenario_id"], f(row, "target_NH3_t_per_day")


def plot_continuous_schedule(summary: dict) -> Path:
    hourly = read_csv(P3_RESULT_DIR / "p3_hourly_cases.csv")
    daily = read_csv(P3_RESULT_DIR / "p3_daily_cases.csv")
    scenario_id, target = best_representative_case(daily, summary)
    rows = [
        row
        for row in hourly
        if row["scenario_id"] == scenario_id and f(row, "target_NH3_t_per_day") == target
    ]
    rows.sort(key=lambda row: int(float(row["hour"])))

    hours = [int(float(row["hour"])) for row in rows]
    renewable = [f(row, "P_re_MW") for row in rows]
    use = [
        f(row, "P_load_MW") + f(row, "P_alk_MW") + f(row, "P_pem_MW") + f(row, "P_nh3_MW")
        for row in rows
    ]
    buy = [f(row, "P_buy_MW") for row in rows]
    sell = [f(row, "P_sell_MW") for row in rows]
    ratio = [f(row, "plant_load_ratio") for row in rows]
    nh3 = [f(row, "NH3_t") for row in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.8, 4.85), sharex=True, height_ratios=[3, 1.25])
    ax1.plot(hours, renewable, marker="s", linewidth=2.0, markersize=3.2, markerfacecolor="white", color="#3B7F5C", label=LABEL["renewable"])
    ax1.plot(hours, use, marker="o", linewidth=2.0, markersize=3.2, markerfacecolor="white", color="#2C5C8A", label=LABEL["use"])
    ax1.plot(hours, buy, linewidth=1.55, linestyle="--", color="#A65E2E", label=LABEL["buy"])
    ax1.plot(hours, sell, linewidth=1.55, linestyle="-.", color="#6F5B9A", label=LABEL["sell"])
    ax1.set_ylabel(LABEL["power"])
    style_axes(ax1)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, fontsize=8.5)

    ax2.plot(hours, ratio, marker="o", color="#5F7896", markerfacecolor="white", linewidth=1.6, label=LABEL["load_ratio"])
    ax2.axhline(0.1, color="#A65E2E", linestyle=(0, (4, 2)), linewidth=1.0)
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel(LABEL["ratio"])
    ax2.set_xlabel(LABEL["hour"])
    style_axes(ax2)
    ax3 = ax2.twinx()
    ax3.plot(hours, nh3, color="#6F5B9A", linewidth=1.3, label=LABEL["nh3"])
    ax3.set_ylabel(LABEL["nh3"])
    ax3.set_ylim(0, 3.15)
    handles2, labels2 = ax2.get_legend_handles_labels()
    handles3, labels3 = ax3.get_legend_handles_labels()
    ax2.legend(handles2 + handles3, labels2 + labels3, loc="upper center", ncol=2, fontsize=9)
    ax2.set_xlim(-0.3, 23.3)
    return save_pdf(fig, "p3_continuous_schedule.pdf")


def plot_cost_by_production(summary: dict) -> Path:
    costs = [summary["annual_by_production"][str(prod)]["unit_cost_yuan_per_t"] for prod in PRODUCTION_LEVELS]
    fig, ax = plt.subplots(figsize=(5.9, 3.25))
    bars = ax.bar([str(prod) for prod in PRODUCTION_LEVELS], costs, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.65)
    best_idx = PRODUCTION_LEVELS.index(36)
    bars[best_idx].set_color("#D97C74")
    ax.annotate(
        f"36 t/d\n{costs[best_idx]:.2f}",
        xy=(best_idx, costs[best_idx]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#d62728",
    )
    ax.set_xlabel(LABEL["production"])
    ax.set_ylabel(LABEL["unit_cost"])
    style_axes(ax)
    return save_pdf(fig, "p3_cost_by_production.pdf")


def plot_indicator_distribution() -> Path:
    rows = read_csv(P3_RESULT_DIR / "p3_daily_cases.csv")
    best_by_scenario: dict[str, dict[str, str]] = {}
    for row in rows:
        sid = row["scenario_id"]
        if sid not in best_by_scenario or f(row, "unit_cost_yuan_per_t") < f(best_by_scenario[sid], "unit_cost_yuan_per_t"):
            best_by_scenario[sid] = row
    ordered = sorted(best_by_scenario.values(), key=lambda row: row["scenario_id"])
    x = list(range(1, len(ordered) + 1))

    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.15), sharex=True)
    for ax, key in zip(axes, INDICATOR_KEYS):
        values = [f(row, key) for row in ordered]
        ax.scatter(x, values, s=24, color="#2C5C8A", edgecolors="white", linewidths=0.45)
        ax.axhline(INDICATOR_THRESHOLDS[key], color="#A65E2E", linestyle=(0, (4, 2)), linewidth=1.0)
        if key == "sell_ratio":
            ax.text(0.04, 0.93, "< 0.20", transform=ax.transAxes, fontsize=9, color="#d62728")
        else:
            ax.text(0.04, 0.93, f"> {INDICATOR_THRESHOLDS[key]:.2f}", transform=ax.transAxes, fontsize=9, color="#d62728")
        ax.set_title(LABEL[key], fontsize=10)
        ax.set_ylim(0, 1.02)
        style_axes(ax)
        ax.set_xlabel(LABEL["scenario"])
    axes[0].set_ylabel(LABEL["ratio"])
    return save_pdf(fig, "p3_indicator_distribution.pdf")


def plot_p2_p3_cost_comparison(p2: dict, p3: dict) -> Path:
    p2_cost = p2["annual_recommended"]["unit_cost_yuan_per_t"]
    p3_cost = p3["annual_recommended"]["unit_cost_yuan_per_t"]
    delta = p2_cost - p3_cost
    fig, ax = plt.subplots(figsize=(5.5, 3.3))
    bars = ax.bar([LABEL["p2"], LABEL["p3"]], [p2_cost, p3_cost], color=["#8FA9C7", "#92B39A"], edgecolor="#2B2B2B", linewidth=0.7)
    for bar, value in zip(bars, [p2_cost, p3_cost]):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    ax.annotate(
        f"-{delta:.2f} yuan/t" if LABEL is EN else f"降低 {delta:.2f} 元/t",
        xy=(1, p3_cost),
        xytext=(0.5, max(p2_cost, p3_cost) * 1.08),
        textcoords="data",
        arrowprops={"arrowstyle": "->", "color": "#A65E2E"},
        ha="center",
        color="#A65E2E",
        fontsize=10,
    )
    ax.set_ylabel(LABEL["unit_cost"])
    style_axes(ax)
    return save_pdf(fig, "p3_p2_cost_comparison.pdf")


def plot_p2_p3_indicator_comparison(p2: dict, p3: dict) -> Path:
    p2_ind = p2["annual_recommended"]["green_indicators"]
    p3_ind = p3["annual_recommended"]["green_indicators"]
    x = list(range(len(INDICATOR_KEYS)))
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.6, 3.45))
    ax.bar([n - width / 2 for n in x], [p2_ind[key] for key in INDICATOR_KEYS], width=width, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.6, label=LABEL["p2"])
    ax.bar([n + width / 2 for n in x], [p3_ind[key] for key in INDICATOR_KEYS], width=width, color="#92B39A", edgecolor="#2B2B2B", linewidth=0.6, label=LABEL["p3"])
    for idx, key in enumerate(INDICATOR_KEYS):
        ax.hlines(
            INDICATOR_THRESHOLDS[key],
            idx - 0.45,
            idx + 0.45,
            colors="#A65E2E",
            linestyles=(0, (4, 2)),
            linewidth=1.0,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[key] for key in INDICATOR_KEYS])
    ax.set_ylim(0, 0.75)
    ax.set_ylabel(LABEL["ratio"])
    ax.text(2, p3_ind["sell_ratio"] + 0.04, "> 0.20", ha="center", fontsize=8.5, color="#A65E2E")
    style_axes(ax)
    ax.legend(frameon=False)
    return save_pdf(fig, "p3_p2_indicator_comparison.pdf")


def plot_grid_exchange_comparison(p2: dict, p3: dict) -> Path:
    p2_energy = p2["annual_recommended"]["energy_MWh"]
    p3_energy = p3["annual_recommended"]["energy_MWh"]
    categories = [LABEL["buy_energy"], LABEL["sell_energy"]]
    p2_values = [p2_energy["grid_buy"], p2_energy["grid_sell"]]
    p3_values = [p3_energy["grid_buy"], p3_energy["grid_sell"]]
    x = [0, 1]
    width = 0.34
    fig, ax = plt.subplots(figsize=(5.9, 3.35))
    ax.bar([n - width / 2 for n in x], p2_values, width=width, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.6, label=LABEL["p2"])
    ax.bar([n + width / 2 for n in x], p3_values, width=width, color="#92B39A", edgecolor="#2B2B2B", linewidth=0.6, label=LABEL["p3"])
    for idx, (old, new) in enumerate(zip(p2_values, p3_values)):
        ax.annotate(
            f"-{old - new:.0f}",
            xy=(idx + width / 2, new),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#3B7F5C",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(LABEL["energy"])
    style_axes(ax)
    ax.legend(frameon=False)
    return save_pdf(fig, "p3_grid_exchange_comparison.pdf")


def write_manifest(paths: list[Path], p2: dict, p3: dict) -> None:
    delta = p2["annual_recommended"]["unit_cost_yuan_per_t"] - p3["annual_recommended"]["unit_cost_yuan_per_t"]
    manifest = {
        "renderer": "matplotlib",
        "note": "Generated by p3_figures.py. Figures use synchronized plant_load_ratio results only.",
        "figures": [
            {
                "path": rel(paths[0]),
                "data_files": ["support/results/p3/p3_hourly_cases.csv", "support/results/p3/p3_daily_cases.csv"],
                "description": "代表性场景下同步负荷率连续调节逐时运行曲线。",
                "key_findings": [
                    "plant_load_ratio 全时段位于 0.1 到 1 之间。",
                    "设备功率和产氨量由统一负荷率同步派生。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[1]),
                "data_files": ["support/results/p3/p3_summary.json"],
                "description": "问题三五个日产量档位的全年吨氨成本对比。",
                "key_findings": ["36 t/d 为当前推荐产量，全年吨氨成本最低。"],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[2]),
                "data_files": ["support/results/p3/p3_daily_cases.csv"],
                "description": "问题三推荐方案下24场景三项官方绿电指标分布。",
                "key_findings": ["self_use_ratio 和 green_ratio 多数表现改善，但 sell_ratio 仍存在高于 0.20 的问题。"],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[3]),
                "data_files": ["support/results/p2/p2_summary.json", "support/results/p3/p3_summary.json"],
                "description": "问题二与问题三推荐方案吨氨成本对比。",
                "key_findings": [f"问题三较问题二吨氨成本降低 {delta:.2f} 元/t。"],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[4]),
                "data_files": ["support/results/p2/p2_summary.json", "support/results/p3/p3_summary.json"],
                "description": "问题二与问题三三项官方绿电指标对比。",
                "key_findings": [
                    "问题三 self_use_ratio 和 green_ratio 提升，sell_ratio 降低。",
                    "问题三 sell_ratio 仍高于 0.20，推荐方案并非三项全部达标。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[5]),
                "data_files": ["support/results/p2/p2_summary.json", "support/results/p3/p3_summary.json"],
                "description": "问题二与问题三全年购电量和上网量对比。",
                "key_findings": ["连续调节后全年购电量和上网量均下降。"],
                "recommended_for_paper": True,
            },
        ],
    }
    with (P3_RESULT_DIR / "p3_figure_manifest.json").open("w", encoding="utf-8") as fobj:
        json.dump(manifest, fobj, ensure_ascii=False, indent=2)
        fobj.write("\n")


def main() -> None:
    p2_summary = read_json(P2_RESULT_DIR / "p2_summary.json")
    p3_summary = read_json(P3_RESULT_DIR / "p3_summary.json")
    paths = [
        plot_continuous_schedule(p3_summary),
        plot_cost_by_production(p3_summary),
        plot_indicator_distribution(),
        plot_p2_p3_cost_comparison(p2_summary, p3_summary),
        plot_p2_p3_indicator_comparison(p2_summary, p3_summary),
        plot_grid_exchange_comparison(p2_summary, p3_summary),
    ]
    write_manifest(paths, p2_summary, p3_summary)
    for path in paths:
        print(rel(path))
    print(rel(P3_RESULT_DIR / "p3_figure_manifest.json"))


if __name__ == "__main__":
    main()
