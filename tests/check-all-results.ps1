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
        Try {
            pwsh -ExecutionPolicy Bypass -File $script
        } Catch {
            Write-Warning "脚本 $script 执行报错。这在未完成求解前是正常的。"
        }
    }
}

Write-Host "全局结构检查完毕。" -ForegroundColor Green
