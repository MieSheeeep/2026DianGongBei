# 2026 DianGongBei LaTeX Template

本仓库为“中国电机工程学会杯”全国大学生电工数学建模竞赛论文模板。

## 目录结构

- `main.tex`：论文主文件，负责格式设置和章节装配。
- `sections/`：正文各章节文件。
- `appendices/`：附录文件。
- `figures/`：论文图片。
- `support/`：支撑材料目录，可放源程序、数据和中间结果，提交前压缩为 RAR 或 ZIP。

## 编译方式

建议使用 XeLaTeX 编译：

```powershell
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

## 格式说明

- A4 纸，上下左右页边距均为 2.5 cm。
- 正文字号为小四，中文字体使用 CTeX 默认宋体配置。
- 第一页为封面，不编页码。
- 第二页为题目、摘要和关键词，并从此页开始以阿拉伯数字编号。
- 正文从第三页开始，不生成目录。
