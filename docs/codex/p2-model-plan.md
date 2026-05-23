# 问题二建模计划：基于离散制氨调节的绿电直连型电氢氨园区运行优化

## 1. 任务边界与审查状态

问题二只处理并网条件下的离散开停机制氨优化。电氢氨装置只有全额开机和停机两种状态，不引入储能，不使用连续功率调节，不改变风电、光伏和常规负荷原始数据。

题面依据为用户主工作区中的 `题目.md`。当前 worktree 内未跟踪该文件，但阶段 A 已读取 `C:\Users\15pro\Desktop\co\diangongbei\题目.md` 并按其中问题二原文建模；后续若在 worktree 中运行代理审查，应确保 `题目.md` 可读或继续明确使用该主工作区文件作为只读题面来源。

问题二包含两类计算任务：

1. 典型风光场景：对日产量 72、63、54、45、36 t/d 分别求成本最低的生产时段安排、绿电直连指标、吨氨成本、购售电量和设备利用率，并找出吨氨成本最低的日产量。
2. 24 种风光场景：由 6 种风电场景和 4 种光伏场景组合生成 24 种日出力场景；对每个场景和每个日产量求最优生产时段安排，统计成本、购电、售电、绿电指标分布，并按每个场景代表 15 天折算全年结果。

## 2. 输入数据来源

- `support/data/附件1：园区典型日常规电负荷标幺功率曲线.xlsx`：常规负荷标幺曲线。
- `support/data/附件2：典型日风电、光伏标幺功率表.xlsx`：典型日风光标幺曲线。
- `support/data/附件3：园区6种场景的风电标幺功率表.xlsx`：6 种风电标幺场景。
- `support/data/附件4：园区4种场景的光伏标幺功率表.xlsx`：4 种光伏标幺场景。
- `support/data/附件5：风光发电与制氢设备技术参数.xlsx`：风光发电与制氢设备技术参数，包括电解槽容量、效率、产氢速率、运维和寿命等原始依据。
- `support/data/附件6：储能设备和合成氨装置技术参数.xlsx`：储能设备和合成氨装置技术参数。问题二不使用储能，但合成氨装置功率、运维和寿命参数应以该附件为原始依据。
- `support/data/附件7：分时电价表.xlsx`：峰、平、谷分时购电电价。
- `support/data/附件8：风电、光伏余电上网电价.xlsx`：风电、光伏余电上网电价。
- `support/code/config.py`：风电、光伏、负荷、制氢氨设备、成本、电价和上网电价等常量。
- `support/code/loaders.py`：读取典型日与多场景数据的公共函数。
- `support/results/p1/p1_summary.json`：问题一口径参考，尤其是绿电指标和吨氨成本计算单位。

所有计算步长为 1 h。功率单位 MW，电量单位 MWh，电价单位 元/kWh，成本单位 元。

## 3. 产量集合与扩容参数

题设要求园区制氨产能增至 72 t/d，日产量从 72 t/d 起按 9 t/d 递减至 36 t/d，因此产量集合为

```text
Q = {72, 63, 54, 45, 36} t/d
```

初始 36 t/d 装置对应：

- ALK 电解槽：10 MW，140 kg H2/h；
- PEM 电解槽：10 MW，160 kg H2/h；
- 合成氨装置：0.75 MW，1.5 t NH3/h。

扩容至 72 t/d 后，电氢氨装置额定功率和产氨速率按产能线性同步提升，满开状态下采用：

- ALK 电解槽：20 MW；
- PEM 电解槽：20 MW；
- 合成氨装置：1.5 MW；
- 产氨速率：3 t/h。

因此不同日产量对应的开机小时数为：

| 日产量 t/d | 满开小时数 h |
| --- | --- |
| 72 | 24 |
| 63 | 21 |
| 54 | 18 |
| 45 | 15 |
| 36 | 12 |

满开状态下 ALK 与 PEM 合计产氢速率为 600 kg H2/h；按题设合成氨耗氢量 0.2 kg H2/kg NH3，3 t NH3/h 需要 600 kg H2/h。因此问题二采用制氢与制氨同步开停机且无氢储存、无中间库存的口径。

## 4. 场景处理方式

### 4.1 典型风光场景

典型日使用附件 2 的风电、光伏标幺曲线：

```text
P_wind,t = WIND_CAPACITY_MW * wind_pu,t
P_pv,t   = PV_CAPACITY_MW * pv_pu,t
P_re,t   = P_wind,t + P_pv,t
```

常规负荷使用附件 1：

```text
P_load,t = LOAD_PEAK_MW * load_pu,t
```

### 4.2 24 种风光场景

24 种风光场景由附件 3 的 6 种风电曲线和附件 4 的 4 种光伏曲线笛卡尔积构造：

```text
scenario_id = W{i}_P{j}, i = 1..6, j = 1..4
P_re,t,s = WIND_CAPACITY_MW * wind_pu,t,i + PV_CAPACITY_MW * pv_pu,t,j
```

每个场景均含 24 个小时。全年统计时，每个风光场景代表 15 天，因此 24 个场景共代表 360 天。

## 5. 决策变量

对每个场景 `s` 和目标日产量 `q`，定义二元变量：

```text
u_t ∈ {0, 1}, t = 0..23
```

其中 `u_t = 1` 表示第 t 小时电氢氨装置全额开机，`u_t = 0` 表示停机。

派生变量：

- `P_alk,t = u_t * 20 MW`
- `P_pem,t = u_t * 20 MW`
- `P_nh3,t = u_t * 1.5 MW`
- `m_nh3,t = u_t * 3 t/h`
- `P_use,t = P_load,t + P_alk,t + P_pem,t + P_nh3,t`
- `P_buy,t = max(P_use,t - P_re,t, 0)`
- `P_sell,t = max(P_re,t - P_use,t, 0)`
- 并网模式下不主动弃电，`P_curtail,t = 0`。

## 6. 目标函数

对给定场景 `s` 和日产量 `q`，选择开机小时集合，使日运行净成本最小：

```text
min C_day(s, q, u)
```

日净成本包括风电度电成本、光伏度电成本、设备运维成本、分时购电成本和余电上网收入抵扣：

```text
C_day =
  1000 * (
    c_wind * E_wind
  + c_pv   * E_pv
  + c_alk  * E_alk
  + c_pem  * E_pem
  + c_nh3  * E_nh3
  + Σ_t c_buy,t * P_buy,t
  - c_sell * E_sell
  )
```

其中电量以 MWh 计，电价和运维系数以 元/kWh 计，因此乘以 1000 完成 MWh 到 kWh 的换算。

电量定义为：

```text
E_wind = Σ_t P_wind,t * Δt
E_pv   = Σ_t P_pv,t   * Δt
E_alk  = Σ_t P_alk,t  * Δt
E_pem  = Σ_t P_pem,t  * Δt
E_nh3  = Σ_t P_nh3,t  * Δt
E_sell = Σ_t P_sell,t * Δt
E_buy  = Σ_t P_buy,t  * Δt
Δt = 1 h
```

绿电直连三项指标作为评价指标输出，不作为优化硬约束。若某一成本最低方案不满足阈值，论文阶段应据实分析其不合格原因。

由于固定场景下风光发电成本为常数，且问题二没有启停成本、最小开停机时间、爬坡约束、储能状态或跨时段库存等耦合约束，后续代码可按每个小时的“开机相对停机增量成本”排序，选择增量成本最低的 `q / 3` 个小时开机；该方法与枚举所有二元组合等价，但计算量更小。若后续加入任何跨时段耦合约束，则该排序法不再直接适用。

## 7. 约束条件

### 7.1 离散开停机约束

```text
u_t ∈ {0, 1}
```

设备只能全额开机或停机，不允许 10% 下限、连续调节、部分负荷运行。

### 7.2 日产量约束

```text
Σ_t 3 * u_t = q
```

等价于：

```text
Σ_t u_t = q / 3
```

对 `q = {72, 63, 54, 45, 36}`，右端分别为 `{24, 21, 18, 15, 12}`。

### 7.3 功率平衡约束

每小时满足：

```text
P_re,t + P_buy,t = P_use,t + P_sell,t
```

并通过正负缺额定义：

```text
P_buy,t  = max(P_use,t - P_re,t, 0)
P_sell,t = max(P_re,t - P_use,t, 0)
```

同一小时内不会同时购电和售电。

### 7.4 非负性约束

```text
P_buy,t >= 0
P_sell,t >= 0
P_curtail,t = 0
NH3_t >= 0
cost_yuan >= 0
```

`cost_yuan` 在逐时文件中定义为非负的小时总支出，不扣除售电收入：

```text
cost_yuan =
  1000 * (
    c_wind * P_wind,t
  + c_pv   * P_pv,t
  + c_alk  * P_alk,t
  + c_pem  * P_pem,t
  + c_nh3  * P_nh3,t
  + c_buy,t * P_buy,t
  ) * Δt
```

售电收入单独输出为 `sell_revenue_yuan`，逐时净成本输出为 `net_cost_yuan = cost_yuan - sell_revenue_yuan`。优化目标、日净成本和吨氨成本均使用 `net_cost_yuan` 汇总，不用 `cost_yuan` 替代净成本。

## 8. 绿电直连指标

沿用问题一的题目口径，定义：

```text
E_re    = Σ_t P_re,t
E_buy   = Σ_t P_buy,t
E_sell  = Σ_t P_sell,t
E_self  = E_re - E_sell
E_total = E_re + E_buy
```

三个指标为：

```text
self_use_ratio = E_self / E_re
green_ratio    = E_self / E_total
sell_ratio     = E_sell / E_re
```

阈值判定：

```text
self_use_ratio > 0.60
green_ratio    > 0.30
sell_ratio     < 0.20
```

日结果按三项指标满足数量划分：

- 全满足：三项均满足；
- 部分满足：至少一项满足但不是全部满足；
- 全不满足：三项均不满足。

## 9. 吨氨成本、购售电和利用率口径

### 9.1 吨氨成本

```text
unit_cost_yuan_per_t = C_day / q
```

对 24 场景全年统计：

```text
annual_total_cost = Σ_s 15 * C_day,s
annual_total_production = Σ_s 15 * q_s
annual_unit_cost = annual_total_cost / annual_total_production
```

若按每个目标日产量分别汇总全年结果，则 `q_s` 固定为该目标产量；若汇总推荐方案，则 `q_s` 为每个场景下被选择的最优日产量。

### 9.2 日购电、日售电

```text
E_buy_day  = Σ_t P_buy,t
E_sell_day = Σ_t P_sell,t
```

单位为 MWh。24 场景分析中输出每个场景和每个日产量下的日购电、日售电，并统计分布特征。

### 9.3 设备利用率

由于问题二中 ALK、PEM、合成氨装置同步全额开停机，设备日利用率相同：

```text
utilization = on_hours / 24 = q / 72
```

也可按电量口径复核：

```text
util_alk = E_alk / (20 * 24)
util_pem = E_pem / (20 * 24)
util_nh3 = E_nh3 / (1.5 * 24)
```

## 10. 结果文件设计

问题二结果写入 `support/results/p2/`。

### 10.1 `p2_typical_hourly.csv` 与 `p2_typical_daily.csv`

典型风光场景结果单独输出，不写入 `p2_hourly_cases.csv`，以避免与 24 组合场景结构检查冲突。

`p2_typical_hourly.csv` 每行对应一个目标日产量和一个小时，字段与 `p2_hourly_cases.csv` 保持一致，但 `scenario_id` 固定为 `typical`。

`p2_typical_daily.csv` 每行对应一个目标日产量，字段与 `p2_daily_cases.csv` 保持一致。典型场景用于回答问题二（1）中的每种产量最低成本生产时段安排，以及典型场景下吨氨成本最低的日产量。

### 10.2 `p2_hourly_cases.csv`

该文件只存放 24 种风光组合场景，不包含典型场景。每行对应一个组合场景、一个目标日产量、一个小时，共 `24 * 5 * 24 = 2880` 行，字段至少包括：

- `scenario_id`
- `target_NH3_t_per_day`
- `hour`
- `u_on`
- `P_load_MW`
- `P_wind_MW`
- `P_pv_MW`
- `P_re_MW`
- `P_alk_MW`
- `P_pem_MW`
- `P_nh3_MW`
- `P_buy_MW`
- `P_sell_MW`
- `P_curtail_MW`
- `NH3_t`
- `cost_yuan`
- `sell_revenue_yuan`
- `net_cost_yuan`

其中 `tests/check-p2-results.ps1` 当前强制检查 `scenario_id`、`target_NH3_t_per_day`、`hour`、`P_load_MW`、`P_re_MW`、`P_buy_MW`、`P_sell_MW`、`P_curtail_MW`、`NH3_t`、`cost_yuan`。

### 10.3 `p2_daily_cases.csv`

该文件只存放 24 种风光组合场景，不包含典型场景。每行对应一个组合场景和一个目标日产量，共 `24 * 5 = 120` 行，字段建议包括：

- `scenario_id`
- `target_NH3_t_per_day`
- `on_hours`
- `on_hour_list`
- `E_re_MWh`
- `E_buy_MWh`
- `E_sell_MWh`
- `E_self_MWh`
- `E_total_MWh`
- `self_use_ratio`
- `green_ratio`
- `sell_ratio`
- `daily_cost_yuan`
- `daily_sell_revenue_yuan`
- `daily_net_cost_yuan`
- `unit_cost_yuan_per_t`
- `device_utilization`
- `indicator_class`

### 10.4 `p2_summary.json`

字段至少包括：

- `scenario_count`: 24
- `annual_days`: 360
- `production_levels_t_per_day`: `[36, 45, 54, 63, 72]`
- `typical_best`
- `typical_by_production`
- `scenario_best_by_production`
- `annual_by_production`
- `annual_recommended`
- `total_production_t`
- `total_cost_yuan`
- `unit_cost_yuan_per_t`
- `green_indicators`

其中 `green_indicators` 至少包含：

- `self_use_ratio`
- `green_ratio`
- `sell_ratio`

顶层 `total_production_t`、`total_cost_yuan`、`unit_cost_yuan_per_t` 和 `green_indicators` 明确对应 `annual_recommended`，即每个场景内从 5 个日产量方案中选择吨氨成本最低的方案后，再按每个场景 15 天折算全年结果。固定日产量的全年统计只放在 `annual_by_production` 中，不与顶层推荐方案混加，避免把 5 个产量档位重复计入全年总量。

## 11. 图表设计

后续图表输出到 `figures/`，文件名使用 `p2_*.pdf`，建议包括：

- `p2_typical_schedule.pdf`：典型风光场景下最优日产量的开停机安排、风光出力与购售电功率。
- `p2_cost_by_production.pdf`：典型场景和 24 场景下，不同日产量吨氨成本对比。
- `p2_indicator_distribution.pdf`：24 场景下三项绿电指标分布及阈值线。
- `p2_annual_unit_cost_distribution.pdf`：按每场景代表 15 天折算的全年吨氨成本分布曲线。
- `p2_grid_exchange_distribution.pdf`：日购电量、日售电量的场景分布。

## 12. 后续代码实现建议

后续代码应新增 `support/code/p2_solve.py`，并复用 `support/code/loaders.py` 和 `support/code/config.py`。

建议实现顺序：

1. 构造典型场景和 24 个风光组合场景。
2. 定义 72 t/d 扩容后的满开功率与产氨速率。
3. 对每个场景和每个日产量计算停机基线小时成本、开机小时成本、开机增量成本。
4. 对固定开机小时数 `q / 3`，选择增量成本最低的小时作为开机时段。
5. 由最优 `u_t` 生成逐时功率、电量、指标和成本。
6. 输出 `p2_typical_hourly.csv`、`p2_typical_daily.csv`、`p2_hourly_cases.csv`、`p2_daily_cases.csv`、`p2_summary.json`。
7. 运行 `tests/check-p2-results.ps1`，根据结构检查结果修复字段或口径问题。
8. 再进入图表生成与论文写入阶段。

## 13. 待互审关注点

- 离散开停机是否正确体现“只有全额开机和停机两种运行方式”。
- 72 t/d 扩容后的功率和产氨速率是否全部按线性同步提升处理。
- 成本最小化应使用扣除售电收入后的 `net_cost_yuan`，而逐时 `cost_yuan` 仅表示非负总支出。
- 典型场景结果必须使用独立文件，不能混入 `p2_hourly_cases.csv`。
- 24 场景全年折算必须严格按每个场景 15 天、共 360 天计算。

## 14. 互审意见与修正记录

### 14.1 fatal issues

- data_auditor 指出当前 worktree 中没有 `题目.md`，无法在代理环境内直接核验题面。处理：本阶段已从用户主工作区 `C:\Users\15pro\Desktop\co\diangongbei\题目.md` 读取题面，并在第 1 节明确该只读来源；后续若需要代理完全独立复核，应使 `题目.md` 在 worktree 内可读。

### 14.2 must-fix issues

- 典型场景输出与 24 场景输出混淆，可能导致 `tests/check-p2-results.ps1` 行数检查失败。处理：第 10 节已规定典型场景写入 `p2_typical_hourly.csv` 和 `p2_typical_daily.csv`，`p2_hourly_cases.csv` 仅包含 24 组合场景。
- `cost_yuan` 字段与净成本口径不清，售电收入抵扣可能导致逐时净成本为负。处理：第 7.4 节已规定 `cost_yuan` 为非负小时总支出，`sell_revenue_yuan` 和 `net_cost_yuan` 单独输出，优化目标和吨氨成本使用净成本。
- 附件 5-8 的原始数据溯源不足。处理：第 2 节已补充设备、电价、上网价等参数对应的原始附件。
- 氢平衡只是隐含成立。处理：第 3 节已补充满开制氢 600 kg/h 与 3 t/h 合成氨耗氢 600 kg/h 的一致性，并明确无氢储存和中间库存。
- `p2_summary.json` 顶层全年统计含义不清。处理：第 10.4 节已规定顶层统计对应 `annual_recommended`，固定日产量统计放在 `annual_by_production`。

### 14.3 optional improvements

- 已补充 `E_wind`、`E_pv`、`E_alk`、`E_pem`、`E_nh3`、`E_buy`、`E_sell` 的电量定义和 `Δt = 1 h`。
- 已明确绿电直连阈值是评价指标，不作为问题二成本最小化的硬约束。
- 已说明增量成本排序法成立的前提：无启停成本、无最小开停机时间、无爬坡、无储能状态、无跨时段库存。

修正后，问题二建模计划可进入下一阶段代码实现；本阶段仍不写求解代码、不生成结果、不修改论文正文。
