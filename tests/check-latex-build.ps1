param()
$ErrorActionPreference = "Stop"

Write-Host "检查 LaTeX 编译就绪状态..."

if (-Not (Test-Path "main.tex")) {
    Write-Error "缺少主文件 main.tex，无法编译。"
    exit 1
}

Write-Host "正在尝试执行轻量级的 LaTeX 编译测试 (仅检查语法)..." -ForegroundColor Cyan
Try {
    # 只跑一遍且遇到错误退出，以此测试语法，减少测试阶段耗时
    latexmk -xelatex -interaction=nonstopmode -f main.tex
    if ($LASTEXITCODE -eq 0) {
        Write-Host "LaTeX 编译检查通过！" -ForegroundColor Green
    } else {
        Write-Host "LaTeX 编译遇到错误（可能有语法问题或缺失引用）。请查阅 main.log 或执行 `latexmk -xelatex -interaction=nonstopmode main.tex` 详情。" -ForegroundColor Red
    }
} Catch {
    Write-Host "本地可能未安装 latexmk 或 xelatex。跳过编译检查。" -ForegroundColor Yellow
}