param()
$ErrorActionPreference = "Stop"

Write-Host "检查全局结果汇总..."

$scripts = @(
    "tests/check-p2-results.ps1",
    "tests/check-p3-results.ps1",
    "tests/check-p4-results.ps1"
)

foreach ($script in $scripts) {
    if (Test-Path $script) {
        Write-Host "运行 $script" -ForegroundColor Cyan
        pwsh -ExecutionPolicy Bypass -File $script
    }
    else {
        Write-Error "缺少检查脚本: $script"
    }
}

Write-Host "全局结构检查完毕。" -ForegroundColor Green
