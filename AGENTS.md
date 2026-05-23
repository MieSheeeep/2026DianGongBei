# AGENTS.md

## 项目身份

本项目是数学建模论文项目，题目为“A 题 绿电直连型电氢氨园区优化运行”。当前重点是完成问题二、问题三、问题四，包括模型建立、代码求解、结果验证、图表生成和 LaTeX 论文撰写。

## 目录约定

- `题目.md`：题目原文，所有建模必须以此为准。
- `support/data/`：原始附件数据，禁止修改。
- `support/code/`：求解代码。
- `support/results/`：结果输出。
- `figures/`：论文图表。
- `sections/`：LaTeX 正文。
- `docs/`：Codex 工作计划、模型说明、审查记录。
- `tests/`：格式检查、结果一致性检查脚本。

## 基本工作纪律

1. 修改前必须先运行 `git status --short`，确认当前工作区状态。
2. 每个阶段开始前必须说明本阶段计划、涉及文件、验证方式。
3. 不允许修改 `support/data/` 原始附件。
4. 不允许凭空编造数值。论文中的所有指标、成本、产量、购电、售电、利用率必须来自 `support/results/`。
5. 不允许只写论文不跑代码；不允许只跑代码不检查论文一致性。
6. 如果模型失败、结果异常或指标明显不合理，必须先记录问题，再最小修改模型或代码。
7. 每个问题的结果必须能通过脚本复现。
8. 每次完成一个阶段后，必须运行 `git diff --stat` 和 `git status --short`。
9. 阶段通过验证后，创建 Git commit；不要自动 push。
10. 如果验证失败，不要 commit 成功状态；可以 commit 为 `wip:`，但必须在提交信息中说明失败项。

## 建模边界与递进策略

问题二、三、四必须采用递进策略：
- 问题二作为离散开停机基线。不得引入储能。
- 问题三作为连续功率可调改进。维持并网基础，不得混入离网储能配置。
- 问题四作为离网与储能扩展。

## 问题二、三、四的标准流水线

每个问题都按以下阶段执行：

### 阶段 A：建模计划

输出到 `docs/codex/pX-model.md`：

- 问题目标；
- 决策变量；
- 目标函数；
- 约束条件；
- 输入数据；
- 输出结果；
- 验证方法；
- 可能的简化假设。

阶段 A 完成后 commit：

`docs: add pX modeling plan`

### 阶段 B：模型互审

至少启用两个只读审查角色：

- model_reviewer：审查数学模型和约束是否符合题意；
- data_auditor：审查单位、数据口径、指标公式和边界条件。

两个审查都通过或主要问题处理完后，再进入代码。

### 阶段 C：代码实现

代码输出规则：

- 问题二：`support/code/p2_solve.py`
- 问题三：`support/code/p3_solve.py`
- 问题四：`support/code/p4_solve.py`
- 可复用函数放入 `support/code/optimization.py` 或 `support/code/metrics.py`
- 每个问题结果输出到 `support/results/pX/`

代码阶段完成后必须运行对应脚本。

阶段 C 通过后 commit：

`feat: implement pX optimization solver`

### 阶段 D：结果验证与自我修复

最多进行 3 轮：

1. 运行脚本；
2. 检查结果文件；
3. 运行结果一致性检查（如 `tests/check-pX-results.ps1`）；
4. 如果失败，定位为数据读取、单位换算、模型约束、优化器、输出格式或论文引用问题；
5. 做最小修改；
6. 重新运行。

如果 3 轮后仍失败，停止并报告失败原因，不要继续盲改。

阶段 D 通过后 commit：

`test: validate pX optimization results`

### 阶段 E：图表生成

生成论文图表到 `figures/`，结果表格到 `support/results/pX/`。

阶段 E 通过后 commit：

`figures: add pX result figures`

### 阶段 F：论文写入

修改 `sections/problemX.tex`，要求：

- 先写模型，再写求解，再写结果，再写分析；
- 所有数值从结果文件读取；
- 图表引用真实存在；
- 与 `symbols.tex` 符号一致；
- 结论不得超出数据支持。

阶段 F 通过后 commit：

`paper: write pX model and results`

### 阶段 G：整体验证

运行：

```powershell
pwsh -ExecutionPolicy Bypass -File tests/check-paper-format.ps1
pwsh -ExecutionPolicy Bypass -File tests/check-all-results.ps1
```

如有 LaTeX 环境，运行：

```powershell
latexmk -xelatex -interaction=nonstopmode main.tex
```

最终 commit：

`chore: verify pX paper integration`

## 完成汇报格式

每次任务结束必须报告：

* 本次完成的阶段；
* 修改文件；
* 生成结果；
* 运行命令；
* 通过项；
* 失败项；
* Git commit hash 或未提交原因；
* 下一步建议。
