支撑材料说明

一、目录结构

1. support/code
   存放论文建模与绘图所用 Python 源程序。

2. support/results
   存放论文采用的关键中间结果和汇总结果，包括逐日结果、代表性逐时结果、
   汇总 JSON 文件和储能候选配置结果。

3. figures
   存放论文正文使用的 PDF 图表。

4. support/data
   该目录仅保留数据说明。根据竞赛支撑材料要求，赛题提供的原始附件不重复放入压缩包。
   若需重新运行源程序，请将赛题附件 1--8 的 Excel 文件按原文件名放入该目录。

5. external_sources
   存放自主查阅资料的来源说明。正文中使用的公开资料以网址形式列出。

二、运行方式

建议在压缩包根目录执行以下命令：

python support/code/p1_solve.py
python support/code/p2_solve.py
python support/code/p2_figures.py
python support/code/p3_solve.py
python support/code/p3_figures.py
python support/code/p4_solve.py
python support/code/p4_figures.py

运行前需安装 Python 3、numpy、pandas、matplotlib、scipy 等依赖。
问题一中的部分图表使用本机 LaTeX 环境生成 PDF；若本机没有 xelatex，可直接使用
figures 目录中已生成的图表。

三、未包含内容

1. 未包含赛题原始附件和 A 题 PDF，避免重复提交赛题已提供数据。
2. 未包含 __pycache__、探索性输出、LaTeX 编译残余文件和版本管理目录。
3. 未包含过大的枚举过程表，仅保留能够支撑论文结果和结论的关键输出。
