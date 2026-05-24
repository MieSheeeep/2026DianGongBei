# 问题三建模计划：基于连续制氨调节的绿电直连型电氢氨园区运行分析

## 1. 任务边界与推进状态

问题三在问题二的并网运行框架上，将电氢氨装置由“全额开机/停机”的离散调度扩展为功率连续可调调度。建模边界如下：

- 制氨产能仍为 72 t/d，扩容后设备额定功率沿用问题二口径：ALK 20 MW，PEM 20 MW，合成氨装置 1.5 MW，满负荷制氨 3 t/h。
- 电氢氨装置功率连续可调，下限按题面要求取额定功率的 10%。ALK 电解槽、PEM 电解槽和合成氨装置作为一套同步扩容、同步调节的电氢氨装置，不再分别独立调度。
- 只处理并网运行，可购电、可售电；不引入离网运行，不引入储能。
- 只使用附件 1、3、4、5、6、7、8 和问题二结果作为输入或对比基准；不修改 `support/data/`。
- 在 24 种风光组合出力场景下求最优调度，并与问题二 24 场景离散开停机结果对比。
- 本计划用于指导 `p3_solve.py`、结果检查和后续论文写入；问题三仍不引入储能或离网运行。

## 2. 问题三任务拆解

问题三需要完成三类计算与分析：

1. 对每种日发电场景，求连续可调制氨用电功率最优调度方案，输出相应绿电直连指标、吨氨成本、购电和售电指标。
2. 按每个风光场景代表 15 天、24 个场景共 360 天，统计全年绿电直连指标状态，绘制全年吨氨成本分布曲线，并计算全年总吨氨成本。
3. 与问题二的离散开停机结果对比，分析连续调节对吨氨成本、购电量、上网比例和绿电指标的影响。

## 3. 关键题意解释：产量档位还是自由产量

题面写明：

```text
园区制氨产能增至 72 吨/日，制氨产量从 72 吨/日起，按 9 吨/日递减至 36 吨/日，电氢氨装置功率连续可调（下限为 10%）
```

因此不能跳过 72、63、54、45、36 t/d 五个日产量档位。

### 3.1 主方案：保留五个固定日产量档位

主方案仍令目标日产量集合为：

```text
Q = {72, 63, 54, 45, 36} t/d
```

对每个场景 `s` 和每个日产量 `q`，求连续功率调度下的最小日净成本。然后：

- 固定产量统计：对每个 `q`，汇总 24 场景全年折算结果。
- 推荐方案统计：每个场景在五个 `q` 中选择吨氨成本最低者，再按每个场景 15 天折算全年。
- 与问题二对比：直接使用同一 24 场景、同一五个产量档位、同一成本和指标口径，比较离散开停机和连续调节的差异。

采用该方案的理由：

- 与题面“按 9 吨/日递减至 36 吨/日”一致。
- 与问题二（2）的结果结构完全可比。
- 与现有 `tests/check-p3-results.ps1` 一致，该检查脚本预期 `24 场景 × 5 产量 × 24 小时 = 2880` 行。
- 避免“自由选择产量”在缺少最低年产量或市场需求约束时退化为只追求低成本的模糊问题。

### 3.2 备选方案：每场景自由选择日产量

备选方案可以把日产量作为连续决策量，使每个场景在 36--72 t/d 范围内自由选择产量，并以日净成本或吨氨成本为目标。但该方案存在两个问题：

- 若目标为日净成本最小，模型可能倾向于低产量甚至边界产量，不能回答题面给出的五个产量档位。
- 若目标为吨氨成本最小，分式目标需要额外线性化或枚举产量，而且结果难以与问题二固定档位结果逐项对比。

因此，备选方案仅作为后续敏感性分析的扩展，不作为本论文问题三主实现。

## 4. 输入数据来源

- `support/data/附件1：园区典型日常规电负荷标幺功率曲线.xlsx`：常规负荷标幺曲线。
- `support/data/附件3：园区6种场景的风电标幺功率表.xlsx`：6 种风电日功率场景。
- `support/data/附件4：园区4种场景的光伏标幺功率表.xlsx`：4 种光伏日功率场景。
- `support/data/附件5：风光发电与制氢设备技术参数.xlsx`：风光装机、制氢设备容量、产氢能力、运维系数等。
- `support/data/附件6：储能设备和合成氨装置技术参数.xlsx`：合成氨装置功率、产能、耗氢关系、运维系数等。问题三不使用储能参数。
- `support/data/附件7：分时电价表.xlsx`：逐时购电电价。
- `support/data/附件8：风电、光伏余电上网电价.xlsx`：余电上网电价。
- `support/code/config.py` 与 `support/code/loaders.py`：公共参数与数据读取逻辑。
- `support/results/p2/p2_summary.json`、`support/results/p2/p2_daily_cases.csv`：问题二对比基准。

功率单位为 MW，电量单位为 MWh，氢气质量单位为 kg，氨产量单位为 t，电价和运维系数单位为 元/kWh，成本单位为 元。调度步长为 `Δt = 1 h`。

## 5. 决策变量设计

对每个场景 `s`、日产量 `q` 和小时 `t=1,...,24`，设置连续变量：

- `r[s,t,q]`：整套电氢氨装置统一负荷率，无量纲。
- `P_buy[s,t,q]`：购电功率，MW。
- `P_sell[s,t,q]`：上网功率，MW。
- `P_curtail[s,t,q]`：弃电功率，MW。并网场景主口径下取 0 或仅作平衡审计字段。

统一负荷率派生全部设备功率和产氨量：

```text
P_alk[s,t,q] = 20 * r[s,t,q]
P_pem[s,t,q] = 20 * r[s,t,q]
P_nh3[s,t,q] = 1.5 * r[s,t,q]
m_nh3[s,t,q] = 3 * r[s,t,q]
P_plant[s,t,q] = 41.5 * r[s,t,q]
```

主方案采用统一负荷率连续调节，并保留购售电互斥变量以避免同小时同时购电和售电，因此代码实现为带少量二元购售电模式变量的 MILP。该处理避免优化器人为改变 ALK 与 PEM 配比，更符合题面中电氢氨装置同步扩容、同步调节的口径。若后续题意明确允许设备独立调度，才可把 `P_alk`、`P_pem` 和 `m_nh3` 重新拆为独立变量；本论文主实现不采用该口径。

下限 10% 的主处理方式为：连续可调装置在 24 小时均保持在线运行，统一负荷率满足 `0.1 <= r[s,t,q] <= 1`。若后续审查认为“可以停机，且开机时最低 10%”才符合题意，则需要额外引入在线状态变量并使用 `0 或 [10%,100%]` 的混合整数约束；该方案列为备选，不进入主实现，除非用户明确要求。

## 6. 目标函数

对给定场景 `s` 和固定日产量 `q`，目标为日净成本最小：

```text
min net_cost_yuan(s, q)
```

成本字段继续沿用问题二口径：

- `cost_yuan`：非负支出，包括风电度电成本、光伏度电成本、设备运维成本和购电成本，不扣除售电收入。
- `sell_revenue_yuan`：余电上网收入。
- `net_cost_yuan = cost_yuan - sell_revenue_yuan`：净成本。
- `unit_cost_yuan_per_t = daily_net_cost_yuan / target_NH3_t_per_day`：吨氨成本。

日净成本公式为：

```text
C_net =
  1000 * (
    c_wind * E_wind
  + c_pv   * E_pv
  + Σ_t (20*c_alk + 20*c_pem + 1.5*c_nh3) * r[t] * Δt
  + Σ_t c_buy,t * P_buy,t * Δt
  - c_sell * E_sell
  )
```

其中 `E` 以 MWh 计，价格以 元/kWh 计，乘以 1000 完成 MWh 到 kWh 的换算。

## 7. 约束条件

### 7.1 逐小时功率平衡

```text
P_re[s,t] + P_buy[s,t,q]
= P_load[s,t] + 41.5 * r[s,t,q]
  + P_sell[s,t,q] + P_curtail[s,t,q]
```

并网主口径下允许购电和售电，不主动弃电，建议实现时取：

```text
P_curtail[s,t,q] = 0
```

若为防止数值误差或极端价格导致异常，可保留 `P_curtail >= 0` 作为审计字段，但不应通过弃电替代可售电。

### 7.2 购电、售电非负性

```text
P_buy[s,t,q]  >= 0
P_sell[s,t,q] >= 0
```

在线性目标下，同一小时同时购电和售电通常不会在最优解中出现，因为购电价格高于上网价格且购售电同时发生只会增加净成本。结果检查仍需验证 `P_buy` 和 `P_sell` 不出现不合理的同时正值；如求解器数值容差导致微小同时正值，可用 `1e-6` 阈值处理。

### 7.3 统一负荷率上下限

主方案按连续在线调节处理：

```text
0.1 <= r[s,t,q] <= 1
```

由此自动得到扩容后各设备功率范围：

```text
2 MW <= P_alk[s,t,q] <= 20 MW
2 MW <= P_pem[s,t,q] <= 20 MW
0.15 MW <= P_nh3[s,t,q] <= 1.5 MW
0.3 t/h <= m_nh3[s,t,q] <= 3.0 t/h
```

### 7.4 合成氨装置功率与产量关系

合成氨装置扩容后满负荷功率为 1.5 MW，满负荷产量为 3 t/h。连续调节下：

```text
P_nh3[s,t,q] = 1.5 * r[s,t,q] MW
m_nh3[s,t,q] = 3 * r[s,t,q] t/h
```

其中 0.3 t/h 是 3 t/h 的 10%，0.5 MWh/t 来自 1.5 MW 对应 3 t/h。

### 7.5 产氢与耗氢平衡

不引入氢储存和跨时段库存，逐小时制氢量与合成氨耗氢量平衡。采用统一负荷率后，该平衡由比例关系自动保证：

```text
H2_prod[s,t,q]
= 14 * (20*r[s,t,q]) + 16 * (20*r[s,t,q])
= 600 * r[s,t,q]

H2_cons[s,t,q]
= 200 * (3*r[s,t,q])
= 600 * r[s,t,q]
```

因此无需再把 `14 * P_alk + 16 * P_pem = 200 * m_nh3` 作为独立约束写入优化器；输出结果仍保留 `H2_prod_kg` 和 `H2_cons_kg` 作为审计字段。

### 7.6 日产氨量约束

对每个目标日产量：

```text
Σ_t 3 * r[s,t,q] * Δt = q
```

其中：

```text
q ∈ {72, 63, 54, 45, 36} t/d
Δt = 1 h
```

由于每小时最小产量为 0.3 t/h，24 小时最低日产量为 7.2 t/d；五个目标产量均可行。

### 7.7 不引入储能、不跨时段库存

问题三不得使用储能充放电功率、储能容量、SOC、初末 SOC、氢储罐库存或合成氨库存等跨时段状态变量。所有能源平衡均在每小时内完成。

## 8. 绿电直连指标

问题三必须沿用题目官方口径，与问题一、问题二保持一致：

```text
E_re    = Σ_t P_re[t] * Δt
E_buy   = Σ_t P_buy[t] * Δt
E_sell  = Σ_t P_sell[t] * Δt
E_self  = E_re - E_sell
E_total = E_re + E_buy
```

三项官方指标为：

```text
self_use_ratio = E_self / E_re
green_ratio    = E_self / E_total
sell_ratio     = E_sell / E_re
```

阈值为：

```text
self_use_ratio > 0.60
green_ratio    > 0.30
sell_ratio     < 0.20
```

可继续输出 `green_internal_use_ratio = E_self / E_use` 作为补充审计字段，但不得用它替代题目官方 `green_ratio`。

## 9. 输出结果设计

问题三结果输出到 `support/results/p3/`。主方案保留五个产量档位，因此结果规模与检查脚本一致。

### 9.1 `p3_hourly_cases.csv`

24 场景 × 5 产量 × 24 小时，共 2880 行。建议字段包括：

- `scenario_id`
- `target_NH3_t_per_day`
- `hour`
- `P_load_MW`
- `P_wind_MW`
- `P_pv_MW`
- `P_re_MW`
- `plant_load_ratio`
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

可额外输出：

- `H2_prod_kg`
- `H2_cons_kg`
- `alk_load_ratio`
- `pem_load_ratio`
- `nh3_load_ratio`

### 9.2 `p3_daily_cases.csv`

24 场景 × 5 产量，共 120 行。建议字段包括：

- `scenario_id`
- `target_NH3_t_per_day`
- `E_re_MWh`
- `E_buy_MWh`
- `E_sell_MWh`
- `E_self_MWh`
- `E_total_MWh`
- `E_use_MWh`
- `E_alk_MWh`
- `E_pem_MWh`
- `E_nh3_MWh`
- `self_use_ratio`
- `green_ratio`
- `green_internal_use_ratio`
- `sell_ratio`
- `daily_cost_yuan`
- `daily_sell_revenue_yuan`
- `daily_net_cost_yuan`
- `unit_cost_yuan_per_t`
- `alk_utilization`
- `pem_utilization`
- `nh3_utilization`
- `plant_utilization`
- `indicator_class`

### 9.3 `p3_summary.json`

建议包含：

- `scenario_count`: 24
- `annual_days`: 360
- `scenario_days`: 15
- `production_levels_t_per_day`: `[36, 45, 54, 63, 72]`
- `annual_by_production`
- `annual_recommended`
- `p2_comparison`
- `total_production_t`
- `total_cost_yuan`
- `unit_cost_yuan_per_t`
- `green_indicators`

其中 `annual_recommended` 与问题二一致：每个场景在五个日产量中选择吨氨成本最低方案，再按每个场景代表 15 天折算全年。`p2_comparison` 可读取 `support/results/p2/p2_summary.json`，记录连续调节相对于离散开停机的成本、购电、售电和指标变化。

### 9.4 图表 manifest

图表阶段再输出：

- `support/results/p3/p3_figure_manifest.json`

manifest 记录每张图的路径、数据来源、关键结论和是否推荐写入论文正文。

## 10. 图表设计

问题三后续图表建议输出到 `figures/p3_*.pdf`：

- `p3_continuous_schedule.pdf`：代表场景连续调度曲线，展示风光出力、统一负荷率、整套电氢氨装置功率、购电、上网和产氨量。
- `p3_annual_unit_cost_distribution.pdf`：推荐方案或固定产量全年吨氨成本分布。
- `p3_indicator_distribution.pdf`：24 场景下三项官方绿电指标分布及阈值线。
- `p3_cost_by_production.pdf`：不同日产量的全年吨氨成本对比。
- `p3_p2_cost_comparison.pdf`：问题二与问题三吨氨成本对比。
- `p3_p2_indicator_comparison.pdf`：问题二与问题三三项绿电指标对比。
- `p3_grid_exchange_comparison.pdf`：连续调节相对离散开停机的购电量、售电量变化对比。

## 11. 与问题二对比逻辑

问题三必须以问题二为基准进行同口径对比：

- 吨氨成本：比较 `annual_recommended.unit_cost_yuan_per_t`，以及固定五个产量档位的 `annual_by_production`。
- 购电量：比较全年 `energy_MWh.grid_buy` 或日均购电量。
- 上网比例：比较官方 `sell_ratio`，并结合 `E_sell_MWh` 解释新能源消纳变化。
- 绿电指标：比较 `self_use_ratio`、`green_ratio`、`sell_ratio`，不得使用 `green_internal_use_ratio` 替代。
- 达标天数：比较全满足、部分满足、全不满足天数。

连续调节通常优于离散开停机的原因是：在同一目标日产量下，连续模型可以把制氨负荷细分到更多小时，并跟随风光出力变化调整功率，从而减少“低产量只集中少数小时开机”导致的余电上网，也减少满开小时对高价购电的依赖。但也可能出现成本改善而指标仍不全满足的情况，尤其是在低产量或高风光出力场景下，园区总用电规模不足以完全消纳新能源。

## 12. 验证方法

阶段 B/C 完成代码后，应执行：

```powershell
conda run -n learn3.8 python support/code/p3_solve.py
powershell -ExecutionPolicy Bypass -File tests/check-p3-results.ps1
```

必须检查：

- `p3_hourly_cases.csv` 是否为 2880 行。
- `p3_daily_cases.csv` 是否为 120 行。
- 是否覆盖 24 个场景和 5 个产量档位。
- 每小时功率平衡是否成立。
- `plant_load_ratio` 是否满足 10%--100% 上下限。
- ALK、PEM、合成氨装置是否均由同一个 `plant_load_ratio` 同步缩放。
- 派生的产氢与耗氢是否逐小时平衡。
- 日产量是否等于目标产量。
- 购电、售电、产量、成本是否非负。
- `cost_yuan`、`sell_revenue_yuan`、`net_cost_yuan` 口径是否与问题二一致。
- 三项官方绿电指标公式是否与题面、问题一、问题二一致。
- 全年统计是否按每个场景 15 天、共 360 天折算。
- 与 `support/results/p2/p2_summary.json` 的对比是否同口径。

若当前 `tests/check-p3-results.ps1` 尚未检查 `p3_daily_cases.csv`、统一负荷率同步关系、氢平衡、10% 下限、净成本公式和指标公式，应在代码阶段同步增强测试脚本，但不得修改题面数据。

## 13. 后续代码实现建议

建议新增 `support/code/p3_solve.py`，优先复用问题二的数据读取和年度统计逻辑。连续优化可采用以下实现路径：

1. 读取附件 1、3、4、5、6、7、8，构造 24 个风光组合场景。
2. 对每个场景和每个 `q` 建立统一负荷率调度模型。
3. 使用 `scipy.optimize.milp` 求解 `r[t]`、购电、售电和购售电模式变量；若后续去掉购售电互斥变量，也可退化为线性规划。
4. 输出逐时与日汇总结果。
5. 汇总 `annual_by_production` 和 `annual_recommended`。
6. 读取 `p2_summary.json`，生成 `p2_comparison`。
7. 运行 `tests/check-p3-results.ps1`，根据失败信息做最多 3 轮最小修复。

## 14. 互审意见与修正记录

### 14.1 fatal issues

本地自审未发现 fatal issue。主方案明确保留五个产量档位，不引入储能或离网运行，能够与题面、问题二和现有检查脚本保持一致。

### 14.2 must-fix issues

- 题意歧义：问题三文字同时包含五个日产量档位和“每种日发电场景下最优调度”。修正：第 3 节已明确主方案保留五个固定产量档位，推荐方案再从五个档位中按场景选择最低吨氨成本方案。
- 10% 下限处理可能引入二元变量。修正：第 5、7 节已明确主方案采用连续在线调节，不引入二元变量；“可停机且开机下限 10%”作为备选 MILP，不进入主实现。
- 独立调度变量会允许优化器人为改变 ALK/PEM 配比。修正：第 5、7 节已改为统一负荷率 `r[s,t,q]`，ALK、PEM、合成氨功率和产氨量均由 `r` 派生，氢平衡由同步缩放自动保证。
- 官方绿电比例不得误用内部用电绿电比例。修正：第 8 节明确 `green_internal_use_ratio` 仅为补充审计字段。

### 14.3 optional improvements

- 后续代码阶段可增强 `tests/check-p3-results.ps1`，增加 `p3_daily_cases.csv`、统一负荷率同步关系、氢平衡、10% 下限、指标公式和净成本公式检查。
- 图表阶段可选择一个典型高风光场景与一个低风光场景，展示连续调节对购售电曲线的改善，而不只展示全年汇总图。

修正后，问题三建模计划、求解代码和检查脚本均采用统一负荷率口径；后续图表和论文正文应沿用该口径，不再描述 ALK、PEM、合成氨装置独立调度。
