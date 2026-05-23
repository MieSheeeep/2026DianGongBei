# 问题二结果口径审计

## 1. 审计范围

本次审计对象为问题二“基于离散制氨调节的绿电直连型电氢氨园区运行优化”的已生成代码与结果。审计只检查结果口径、公式一致性、成本口径和全年折算，不生成图表，不修改论文正文。

当前分支为 `codex/p2-discrete-optimization`，问题二代码阶段提交为 `c5d29b7`。

## 2. 结果文件清单

问题二结果位于 `support/results/p2/`，文件清单如下：

- `p2_typical_hourly.csv`：典型风光场景逐时结果，5 个产量档位 × 24 小时，共 120 行。
- `p2_typical_daily.csv`：典型风光场景日汇总，5 个产量档位，共 5 行。
- `p2_hourly_cases.csv`：24 个风光组合场景逐时结果，24 个场景 × 5 个产量档位 × 24 小时，共 2880 行。
- `p2_daily_cases.csv`：24 个风光组合场景日汇总，24 个场景 × 5 个产量档位，共 120 行。
- `p2_summary.json`：典型场景最优方案、固定产量全年统计、推荐方案全年统计和关键指标汇总。

`tests/check-p2-results.ps1` 已通过，除缺少 `figures/p2_*.pdf` 的预期提示外无失败项。图表文件属于后续图表生成阶段。

## 3. 指标公式审计

`题目.md` 给出的三项绿电直连指标为：

- 新能源自发自用电量占总可用发电量比例 = （总用电量 - 上网电量 - 网购电量）/ 新能源发电量，要求大于 60%。
- 总用电量绿电比例 = （新能源发电量 - 上网电量）/ 总用电量，要求大于 30%。
- 新能源上网电量比例 = 上网电量 / 新能源发电量，要求小于 20%。

问题一已经明确采用题目公式的“总用电量”宽口径：

```text
E_total = E_re + E_buy = E_self + E_sell + E_buy
E_self  = E_re - E_sell
```

问题二沿用同一口径：

```text
E_re_MWh    = 新能源发电量
E_buy_MWh   = 网购电量
E_sell_MWh  = 上网电量
E_self_MWh  = E_re_MWh - E_sell_MWh
E_total_MWh = E_re_MWh + E_buy_MWh
```

据此三项指标为：

```text
self_use_ratio = E_self_MWh / E_re_MWh
green_ratio    = E_self_MWh / E_total_MWh
sell_ratio     = E_sell_MWh / E_re_MWh
```

审计结论：`p2_solve.py`、`p2_summary.json` 和 `tests/check-p2-results.ps1` 对三项官方指标使用同一公式，口径一致。

## 4. 关键字段含义

- `E_total_MWh`：题目公式口径的总用电量，定义为 `E_re_MWh + E_buy_MWh`。它不是园区内部实际消耗电量。
- `E_re_MWh`：风电与光伏发电量之和。
- `E_buy_MWh`：外部电网购电量。
- `E_sell_MWh`：新能源余电上网电量。
- `E_use_MWh`：园区内部实际用电量，定义为 `E_load_MWh + E_alk_MWh + E_pem_MWh + E_nh3_MWh`，也等于 `E_self_MWh + E_buy_MWh`。
- `self_use_ratio`：新能源自发自用比例，`E_self_MWh / E_re_MWh`。
- `green_ratio`：题目口径总用电量绿电比例，`E_self_MWh / E_total_MWh`。
- `sell_ratio`：新能源上网电量比例，`E_sell_MWh / E_re_MWh`。
- `green_internal_use_ratio`：补充审计字段，表示园区内部实际用电绿电比例，`E_self_MWh / E_use_MWh`。该字段不替代题目要求的 `green_ratio`。

## 5. p1 与 p2 口径一致性

`support/code/p1_solve.py` 中：

```text
E_self = E_re - E_sell
E_total = E_re + E_buy
self_use_ratio = E_self / E_re
green_in_total_wide = E_self / E_total
grid_sell_ratio = E_sell / E_re
```

`support/code/p2_solve.py` 中：

```text
E_self = E_re - E_sell
E_total = E_re + E_buy
self_use_ratio = E_self / E_re
green_ratio = E_self / E_total
sell_ratio = E_sell / E_re
```

审计结论：p1 与 p2 的官方三项指标口径一致，不存在题意差异导致的分母变化，也未发现代码错误。p2 额外输出 `E_use_MWh` 和 `green_internal_use_ratio`，仅用于说明内部实际用电口径与题目公式口径的区别。

## 6. 成本口径审计

逐时结果中：

- `cost_yuan` 表示非负总支出，包括风电度电成本、光伏度电成本、ALK 运维、PEM 运维、合成氨运维和购电成本，不扣除售电收入。
- `sell_revenue_yuan` 单独表示余电上网收入。
- `net_cost_yuan = cost_yuan - sell_revenue_yuan`。

日汇总中：

- `daily_cost_yuan` 为逐时 `cost_yuan` 之和。
- `daily_sell_revenue_yuan` 为逐时 `sell_revenue_yuan` 之和。
- `daily_net_cost_yuan = daily_cost_yuan - daily_sell_revenue_yuan`。
- `unit_cost_yuan_per_t = daily_net_cost_yuan / target_NH3_t_per_day`。

审计发现 `p2_hourly_cases.csv` 中有部分小时的 `net_cost_yuan` 为负，最小值约为 `-16817.56` 元。这是局部小时售电收入高于该小时非负支出导致的抵扣结果，不代表总成本异常。典型场景与 24 场景日净成本、全年净成本均为正，未发现净成本为负或异常偏低的问题。

## 7. 典型场景关键结果

典型场景 5 个产量档位的最优开机小时数为：

| 日产量 (t/d) | 开机小时数 | 设备利用率 | 吨氨成本 (元/t) | 自发自用比例 | 总用电量绿电比例 | 上网比例 | 达标情况 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 72 | 24 | 1.000 | 6219.14 | 0.9326 | 0.5128 | 0.0674 | 全满足 |
| 63 | 21 | 0.875 | 5328.06 | 0.9217 | 0.5678 | 0.0783 | 全满足 |
| 54 | 18 | 0.750 | 4591.27 | 0.9008 | 0.6265 | 0.0992 | 全满足 |
| 45 | 15 | 0.625 | 3944.54 | 0.7549 | 0.5481 | 0.2451 | 部分满足 |
| 36 | 12 | 0.500 | 3191.67 | 0.5525 | 0.4023 | 0.4475 | 部分满足 |

典型场景下吨氨成本最低的日产量为 `36 t/d`。该方案：

- 新能源自发自用比例为 `0.5525`，未达到 `> 0.60`。
- 总用电量绿电比例为 `0.4023`，达到 `> 0.30`。
- 新能源上网比例为 `0.4475`，未达到 `< 0.20`。
- 设备利用率为 `0.500`，与 `36/72` 的产量比例一致。

审计结论：典型场景开机小时数与产量集合严格对应，设备利用率符合产量比例；最低吨氨成本方案并非三项指标全达标。

## 8. 24 场景与全年统计摘要

24 场景结果结构：

- `p2_daily_cases.csv` 为 120 行。
- `p2_hourly_cases.csv` 为 2880 行。
- 24 个风光组合场景均覆盖 72、63、54、45、36 t/d 五个产量档位。

全年折算方法：

- `annual_by_production`：固定某一日产量，24 个场景各代表 15 天，按 360 天折算全年总产量、总成本、吨氨成本和绿电指标。
- `annual_recommended`：每个场景独立选择吨氨成本最低的日产量，再按每个场景 15 天折算。当前结果中，每个场景的最低吨氨成本方案均为 36 t/d，因此 `annual_recommended` 与 `annual_by_production["36"]` 一致。

固定产量全年统计摘要：

| 日产量 (t/d) | 年产量 (t) | 年吨氨成本 (元/t) | 自发自用比例 | 总用电量绿电比例 | 上网比例 | 全满足天数 | 部分满足天数 | 全不满足天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 72 | 25920 | 7182.67 | 0.9295 | 0.4058 | 0.0705 | 270 | 90 | 0 |
| 63 | 22680 | 6523.27 | 0.8879 | 0.4288 | 0.1121 | 210 | 150 | 0 |
| 54 | 19440 | 5909.66 | 0.8201 | 0.4370 | 0.1799 | 180 | 180 | 0 |
| 45 | 16200 | 5290.32 | 0.6885 | 0.3942 | 0.3115 | 15 | 345 | 0 |
| 36 | 12960 | 4493.82 | 0.5478 | 0.3369 | 0.4522 | 0 | 345 | 15 |

`annual_recommended` 摘要：

- 年产量：`12960 t`。
- 年总净成本：`58,239,941.06 元`。
- 年吨氨成本：`4493.82 元/t`。
- 年度官方三项指标：`self_use_ratio = 0.5478`，`green_ratio = 0.3369`，`sell_ratio = 0.4522`。
- 全满足天数：`0`，部分满足天数：`345`，全不满足天数：`15`。

## 9. 是否发现必须修复的问题

未发现必须修复的问题。

已确认：

- p1 与 p2 的官方绿电指标口径一致。
- p2 成本字段区分总支出、售电收入和净成本。
- 吨氨成本基于净成本计算。
- 典型场景开机小时数、设备利用率与产量档位一致。
- 24 场景和全年折算结构正确。
- `tests/check-p2-results.ps1` 已验证功率平衡、产量、成本、指标公式、行数和年度折算。

非阻塞说明：

- `docs/codex/p2-model-plan.md` 中仍保留“当前 worktree 内未跟踪题目.md”的阶段 A 历史说明；现在 `题目.md` 已被纳入 Git。该句属于历史审查记录，不影响当前结果口径。
- `green_internal_use_ratio` 是补充审计字段，不是题目三项官方指标。

## 10. 是否允许进入图表生成阶段

允许进入问题二图表生成阶段。

建议下一阶段只生成 `figures/p2_*.pdf` 和必要的图表说明数据，继续暂不写论文正文，待图表验证后再进入论文写入阶段。
