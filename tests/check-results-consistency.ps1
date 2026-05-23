param()
$ErrorActionPreference = "Stop"

Write-Host "检查基于第一题(p1)的结果一致性..."

$missingFiles = 0
$resultsFiles = @(
    "support/results/p1/p1_summary.json",
    "support/results/p1/p1_hourly_power.csv",
    "figures/p1_power_curves.pdf",
    "figures/p1_indicator_thresholds.pdf",
    "figures/p1_cost_breakdown.pdf"
)

foreach ($file in $resultsFiles) {
    if (-Not (Test-Path $file)) {
        Write-Error "缺少结果文件: $file"
        $missingFiles++
    }
}

if ($missingFiles -gt 0) {
    Write-Error "结果文件不齐全，请先执行求解代码 (python support/code/p1_solve.py)。"
    exit 1
}

Write-Host "检查 p1_hourly_power.csv 是否含有24小时数据..."
$csvContent = Import-Csv "support/results/p1/p1_hourly_power.csv"
if ($csvContent.Count -ne 24) {
    Write-Error "p1_hourly_power.csv 的数据行数不为24！当前行数：$($csvContent.Count)"
} else {
    Write-Host "p1_hourly_power.csv 行数检查通过。" -ForegroundColor Green
}

# 可在此进一步解析 p1_summary.json 校验 0~1 的指标范围，以及购电量非负等原则
Write-Host "基础一致性检查通过。" -ForegroundColor Green
