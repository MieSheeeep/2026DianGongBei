# Codex Workflow for Problems 2-4

## 总目标

完成 A 题问题二、三、四的建模、代码求解、结果验证、图表生成和论文写入。

## 总体策略

问题二、三、四不要一次性完成。必须按问题编号推进：

1. 问题二：离散开停机制氨优化；
2. 问题三：连续功率可调优化；
3. 问题四：离网运行与储能配置。

每个问题内部按以下顺序：

建模计划 → 模型互审 → 代码实现 → 结果验证 → 图表生成 → 论文写入 → 整体验证 → Git commit。

## 问题边界

- 问题二只处理并网条件下的离散开停机方案，电氢氨装置只有全额开机和停机两种状态，不得引入储能。
- 问题三只处理并网条件下的连续功率可调方案，功率下限按题面要求处理，不得混入离网储能配置。
- 问题四再处理离网运行、能源自给和储能容量配置，不得把问题四的储能约束提前写入问题二或问题三。
- 每个问题都必须先写模型计划并完成互审，再写求解代码。

## 模型互搏机制

每个问题至少进行一次互审：

1. 主 agent 提出模型。
2. model_reviewer 从题意、变量、目标函数、约束角度批判模型。
3. data_auditor 从数据、单位、指标公式、边界条件角度批判模型。
4. 主 agent 汇总意见，修订模型。
5. 修订后的模型写入 `docs/codex/pX-model.md`。
6. 只有模型文档通过后才允许写代码。

## 自我修复循环

代码运行失败或结果异常时，最多修复 3 轮。

每轮必须记录：

- 失败命令；
- 错误输出；
- 失败类别；
- 修改文件；
- 修改原因；
- 重新运行结果。

不要无限循环。

## Git 规则

每个阶段开始前必须：

```powershell
git status --short
```

每个阶段结束都必须：

```powershell
git diff --stat
git status --short
```

验证通过后提交：

```powershell
git add <相关文件>
git commit -m "<type>: <message>"
```

推荐提交粒度：

* `docs: add p2 modeling plan`
* `feat: implement p2 discrete scheduler`
* `test: validate p2 results`
* `figures: add p2 scenario plots`
* `paper: write p2 results section`

禁止自动 push。
