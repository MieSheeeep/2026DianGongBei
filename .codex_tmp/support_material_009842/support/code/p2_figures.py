from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "support" / "results" / "p2"
FIGURE_DIR = ROOT / "figures"


PRODUCTION_LEVELS = [36, 45, 54, 63, 72]
INDICATOR_THRESHOLDS = {
    "self_use_ratio": 0.60,
    "green_ratio": 0.30,
    "sell_ratio": 0.20,
}


ZH_LABELS = {
    "hour": "时刻/h",
    "power": "功率/MW",
    "production": "日产量/(t/d)",
    "unit_cost": "吨氨成本/(元/t)",
    "ratio": "比例",
    "energy": "电量/MWh",
    "scenario": "场景序号",
    "typical_schedule_title": "典型场景最低成本方案逐时运行",
    "cost_title": "不同日产量吨氨成本比较",
    "indicator_title": "24场景绿电直连指标分布",
    "annual_title": "推荐方案吨氨成本场景分布",
    "grid_title": "不同日产量日购电量与日上网量分布",
    "renewable": "风光发电",
    "use": "园区总用电",
    "buy": "购电",
    "sell": "上网",
    "on": "开机状态",
    "typical": "典型场景",
    "annual_fixed": "全年固定产量",
    "self_use_ratio": "自发自用比例",
    "green_ratio": "总用电量绿电比例",
    "sell_ratio": "上网比例",
    "buy_energy": "日购电量",
    "sell_energy": "日上网量",
    "sell_ratio_line": "全年上网比例",
    "recommended_note": "推荐方案均为 36 t/d",
}


EN_LABELS = {
    "hour": "Hour",
    "power": "Power (MW)",
    "production": "Daily production (t/d)",
    "unit_cost": "Unit cost (yuan/t)",
    "ratio": "Ratio",
    "energy": "Energy (MWh)",
    "scenario": "Scenario index",
    "typical_schedule_title": "Typical scenario hourly operation",
    "cost_title": "Unit cost by daily production",
    "indicator_title": "Green-direct indicator distribution",
    "annual_title": "Recommended unit cost by scenario",
    "grid_title": "Daily purchase and export by production",
    "renewable": "Renewable",
    "use": "Total use",
    "buy": "Grid buy",
    "sell": "Grid export",
    "on": "On/off",
    "typical": "Typical",
    "annual_fixed": "Annual fixed",
    "self_use_ratio": "Self-use ratio",
    "green_ratio": "Green ratio",
    "sell_ratio": "Export ratio",
    "buy_energy": "Daily buy",
    "sell_energy": "Daily export",
    "sell_ratio_line": "Annual export ratio",
    "recommended_note": "Recommended plans all select 36 t/d",
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
            return ZH_LABELS
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return EN_LABELS


LABELS = choose_labels()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def i(row: dict[str, str], key: str) -> int:
    return int(round(float(row[key])))


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


def load_summary() -> dict:
    with (RESULT_DIR / "p2_summary.json").open("r", encoding="utf-8") as fobj:
        return json.load(fobj)


def plot_typical_schedule(summary: dict) -> Path:
    rows = read_csv_rows(RESULT_DIR / "p2_typical_hourly.csv")
    best_prod = float(summary["typical_best"]["target_NH3_t_per_day"])
    rows = [row for row in rows if math.isclose(f(row, "target_NH3_t_per_day"), best_prod)]

    hours = [i(row, "hour") for row in rows]
    renewable = [f(row, "P_re_MW") for row in rows]
    use = [f(row, "P_load_MW") + f(row, "P_alk_MW") + f(row, "P_pem_MW") + f(row, "P_nh3_MW") for row in rows]
    buy = [f(row, "P_buy_MW") for row in rows]
    sell = [f(row, "P_sell_MW") for row in rows]
    on = [f(row, "u_on") for row in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.8, 4.65), sharex=True, height_ratios=[3.0, 0.85])
    ax1.plot(hours, renewable, marker="s", linewidth=2.0, markersize=3.2, markerfacecolor="white", color="#3B7F5C", label=LABELS["renewable"])
    ax1.plot(hours, use, marker="o", linewidth=2.0, markersize=3.2, markerfacecolor="white", color="#2C5C8A", label=LABELS["use"])
    ax1.plot(hours, buy, linewidth=1.65, linestyle="--", color="#A65E2E", label=LABELS["buy"])
    ax1.plot(hours, sell, linewidth=1.65, linestyle="-.", color="#6F5B9A", label=LABELS["sell"])
    ax1.set_ylabel(LABELS["power"])
    style_axes(ax1)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, fontsize=8.5)

    ax2.step(hours, on, where="mid", color="#2B2B2B", linewidth=1.4, label=LABELS["on"])
    ax2.fill_between(hours, 0, on, step="mid", color="#8FA9C7", alpha=0.28)
    ax2.set_yticks([0, 1])
    ax2.set_xlabel(LABELS["hour"])
    ax2.set_ylabel(LABELS["on"])
    style_axes(ax2, "x")
    ax2.set_xlim(-0.3, 23.3)

    return save_pdf(fig, "p2_typical_schedule.pdf")


def plot_cost_by_production(summary: dict) -> Path:
    typical_rows = {i(row, "target_NH3_t_per_day"): row for row in read_csv_rows(RESULT_DIR / "p2_typical_daily.csv")}
    typical_cost = [f(typical_rows[p], "unit_cost_yuan_per_t") for p in PRODUCTION_LEVELS]
    annual_cost = [summary["annual_by_production"][str(p)]["unit_cost_yuan_per_t"] for p in PRODUCTION_LEVELS]

    fig, ax = plt.subplots(figsize=(6.2, 3.45))
    width = 0.34
    x = list(range(len(PRODUCTION_LEVELS)))
    ax.bar([n - width / 2 for n in x], typical_cost, width=width, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.65, label=LABELS["typical"])
    ax.bar([n + width / 2 for n in x], annual_cost, width=width, color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.65, label=LABELS["annual_fixed"])

    min_idx = min(range(len(PRODUCTION_LEVELS)), key=lambda idx: typical_cost[idx])
    ax.scatter([min_idx - width / 2], [typical_cost[min_idx]], color="#d62728", zorder=4)
    ax.annotate(
        f"min {PRODUCTION_LEVELS[min_idx]} t/d",
        xy=(min_idx - width / 2, typical_cost[min_idx]),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color="#d62728",
    )

    ax.set_xticks(x)
    ax.set_xticklabels([str(p) for p in PRODUCTION_LEVELS])
    ax.set_xlabel(LABELS["production"])
    ax.set_ylabel(LABELS["unit_cost"])
    style_axes(ax)
    ax.legend(frameon=False, loc="upper left")
    return save_pdf(fig, "p2_cost_by_production.pdf")


def min_mean_max(values: list[float]) -> tuple[float, float, float]:
    return min(values), sum(values) / len(values), max(values)


def plot_indicator_distribution() -> Path:
    rows = read_csv_rows(RESULT_DIR / "p2_daily_cases.csv")
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[i(row, "target_NH3_t_per_day")].append(row)

    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.15), sharex=True)
    for ax, key in zip(axes, ["self_use_ratio", "green_ratio", "sell_ratio"]):
        means, lower, upper = [], [], []
        for prod in PRODUCTION_LEVELS:
            lo, mean, hi = min_mean_max([f(row, key) for row in grouped[prod]])
            means.append(mean)
            lower.append(mean - lo)
            upper.append(hi - mean)
        ax.errorbar(PRODUCTION_LEVELS, means, yerr=[lower, upper], marker="o", capsize=3.5, linewidth=1.45, color="#2C5C8A", markerfacecolor="white", ecolor="#6F5B9A")
        ax.axhline(INDICATOR_THRESHOLDS[key], linestyle=(0, (4, 2)), color="#A65E2E", linewidth=1.0)
        ax.set_title(LABELS[key], fontsize=10)
        ax.set_ylim(0, 1.02)
        style_axes(ax)
        ax.set_xlabel(LABELS["production"])
    axes[0].set_ylabel(LABELS["ratio"])
    return save_pdf(fig, "p2_indicator_distribution.pdf")


def plot_annual_unit_cost_distribution(summary: dict) -> Path:
    rows = read_csv_rows(RESULT_DIR / "p2_daily_cases.csv")
    best_by_scenario: dict[str, dict[str, str]] = {}
    for row in rows:
        sid = row["scenario_id"]
        if sid not in best_by_scenario or f(row, "unit_cost_yuan_per_t") < f(best_by_scenario[sid], "unit_cost_yuan_per_t"):
            best_by_scenario[sid] = row
    ordered = sorted(best_by_scenario.values(), key=lambda row: f(row, "unit_cost_yuan_per_t"))
    costs = [f(row, "unit_cost_yuan_per_t") for row in ordered]
    prods = sorted({i(row, "target_NH3_t_per_day") for row in ordered})

    fig, ax = plt.subplots(figsize=(6.4, 3.35))
    ax.plot(range(1, len(costs) + 1), costs, marker="o", linewidth=1.6, color="#2C5C8A", markerfacecolor="white")
    annual_cost = summary["annual_recommended"]["unit_cost_yuan_per_t"]
    ax.axhline(annual_cost, linestyle="--", color="#d62728", linewidth=1.2, label=f"annual {annual_cost:.2f}")
    note = LABELS["recommended_note"] if prods == [36] else f"recommended: {prods}"
    ax.text(0.02, 0.96, note, transform=ax.transAxes, va="top", fontsize=9)
    ax.set_xlabel(LABELS["scenario"])
    ax.set_ylabel(LABELS["unit_cost"])
    style_axes(ax)
    ax.legend(frameon=False)
    return save_pdf(fig, "p2_annual_unit_cost_distribution.pdf")


def plot_grid_exchange_distribution(summary: dict) -> Path:
    rows = read_csv_rows(RESULT_DIR / "p2_daily_cases.csv")
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[i(row, "target_NH3_t_per_day")].append(row)

    mean_buy = []
    mean_sell = []
    annual_sell_ratio = []
    for prod in PRODUCTION_LEVELS:
        mean_buy.append(sum(f(row, "E_buy_MWh") for row in grouped[prod]) / len(grouped[prod]))
        mean_sell.append(sum(f(row, "E_sell_MWh") for row in grouped[prod]) / len(grouped[prod]))
        annual_sell_ratio.append(summary["annual_by_production"][str(prod)]["green_indicators"]["sell_ratio"])

    fig, ax1 = plt.subplots(figsize=(6.8, 3.5))
    width = 0.34
    x = list(range(len(PRODUCTION_LEVELS)))
    ax1.bar([n - width / 2 for n in x], mean_buy, width=width, color="#8FA9C7", edgecolor="#2B2B2B", linewidth=0.6, label=LABELS["buy_energy"])
    ax1.bar([n + width / 2 for n in x], mean_sell, width=width, color="#D7A77A", edgecolor="#2B2B2B", linewidth=0.6, label=LABELS["sell_energy"])
    ax1.set_ylabel(LABELS["energy"])
    ax1.set_xlabel(LABELS["production"])
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(p) for p in PRODUCTION_LEVELS])
    style_axes(ax1)

    ax2 = ax1.twinx()
    ax2.plot(x, annual_sell_ratio, color="#A65E2E", marker="o", markerfacecolor="white", linewidth=1.6, label=LABELS["sell_ratio_line"])
    ax2.axhline(INDICATOR_THRESHOLDS["sell_ratio"], linestyle=(0, (4, 2)), color="#A65E2E", alpha=0.7, linewidth=1.0)
    ax2.set_ylabel(LABELS["ratio"])
    ax2.set_ylim(0, max(annual_sell_ratio) * 1.25)

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper center", ncol=3, fontsize=8.5, frameon=False)
    return save_pdf(fig, "p2_grid_exchange_distribution.pdf")


def write_manifest(paths: list[Path], summary: dict) -> None:
    rel = lambda path: str(path.relative_to(ROOT)).replace("\\", "/")
    manifest = {
        "renderer": "matplotlib",
        "note": "Generated with matplotlib in the learn3.8 conda environment.",
        "figures": [
            {
                "path": rel(paths[0]),
                "data_files": ["support/results/p2/p2_typical_hourly.csv", "support/results/p2/p2_summary.json"],
                "description": "典型风光场景下最低吨氨成本方案的逐时功率与开停机状态。",
                "key_findings": [
                    "最低吨氨成本方案为 36 t/d，开机 12 小时。",
                    "低产量方案成本较低，但余电上网功率在高出力时段更突出。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[1]),
                "data_files": ["support/results/p2/p2_typical_daily.csv", "support/results/p2/p2_summary.json"],
                "description": "比较典型场景与24场景固定产量全年折算吨氨成本。",
                "key_findings": [
                    "典型场景最低吨氨成本产量为 36 t/d。",
                    "固定产量全年折算中，36 t/d 吨氨成本最低。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[2]),
                "data_files": ["support/results/p2/p2_daily_cases.csv"],
                "description": "24场景下三项官方绿电指标按产量分布，点为均值，误差线为最小-最大范围。",
                "key_findings": [
                    "低产量方案上网比例明显偏高。",
                    "高产量方案自发自用比例和上网比例更容易达标，但吨氨成本更高。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[3]),
                "data_files": ["support/results/p2/p2_daily_cases.csv", "support/results/p2/p2_summary.json"],
                "description": "24个场景推荐方案吨氨成本排序分布，每个场景代表15天。",
                "key_findings": [
                    "推荐方案均选择 36 t/d。",
                    f"推荐方案全年吨氨成本为 {summary['annual_recommended']['unit_cost_yuan_per_t']:.2f} 元/t。",
                ],
                "recommended_for_paper": True,
            },
            {
                "path": rel(paths[4]),
                "data_files": ["support/results/p2/p2_daily_cases.csv", "support/results/p2/p2_summary.json"],
                "description": "不同固定日产量下24场景平均日购电量、日上网量和全年上网比例对比。",
                "key_findings": [
                    "低日产量方案购电量较低、成本较低，但平均日上网量和上网比例明显偏高。",
                    "高日产量方案更利于降低上网比例，但购电和吨氨成本增加。",
                ],
                "recommended_for_paper": True,
            },
        ],
    }
    with (RESULT_DIR / "p2_figure_manifest.json").open("w", encoding="utf-8") as fobj:
        json.dump(manifest, fobj, ensure_ascii=False, indent=2)
        fobj.write("\n")


def main() -> None:
    summary = load_summary()
    paths = [
        plot_typical_schedule(summary),
        plot_cost_by_production(summary),
        plot_indicator_distribution(),
        plot_annual_unit_cost_distribution(summary),
        plot_grid_exchange_distribution(summary),
    ]
    write_manifest(paths, summary)
    for path in paths:
        print(path.relative_to(ROOT))
    print((RESULT_DIR / "p2_figure_manifest.json").relative_to(ROOT))


if __name__ == "__main__":
    main()
