param()
$ErrorActionPreference = "Stop"

Write-Host "检查问题二 (p2) 结果文件结构..."

$expectedFiles = @(
    "support/results/p2/p2_summary.json",
    "support/results/p2/p2_hourly_cases.csv"
)

$missing = 0
foreach ($f in $expectedFiles) {
    if (-Not (Test-Path $f)) {
        Write-Warning "文件丢失: $f"
        $missing++
    }
}

if ($missing -eq 0) {
    Write-Host "基本结果文件结构存在。执行通过。" -ForegroundColor Green
}
else {
    Write-Error "文件缺失！"
}
