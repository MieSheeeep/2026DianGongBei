param()
$ErrorActionPreference = "Stop"

$problem = "p3"
$resultDir = "support/results/$problem"
$summaryPath = "$resultDir/${problem}_summary.json"
$hourlyPath = "$resultDir/${problem}_hourly_cases.csv"
$requiredColumns = @(
    "scenario_id",
    "hour",
    "P_load_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t"
)
$nonnegativeColumns = @(
    "P_load_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t"
)

Write-Host "检查问题三 (p3) 结果结构与基本数值约束..."

foreach ($path in @($summaryPath, $hourlyPath)) {
    if (-Not (Test-Path $path)) {
        Write-Error "缺少结果文件: $path"
    }
}

$summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
foreach ($field in @("scenario_count", "annual_days", "total_production_t", "unit_cost_yuan_per_t", "green_indicators")) {
    if (-Not ($summary.PSObject.Properties.Name -contains $field)) {
        Write-Error "p3_summary.json 缺少字段: $field"
    }
}

if ([int]$summary.scenario_count -ne 24) {
    Write-Error "scenario_count 应为 24，当前为 $($summary.scenario_count)"
}
if ([int]$summary.annual_days -ne 360) {
    Write-Error "annual_days 应为 360，即 24 个场景各代表 15 天，当前为 $($summary.annual_days)"
}
if (-Not [double]::IsFinite([double]$summary.unit_cost_yuan_per_t)) {
    Write-Error "unit_cost_yuan_per_t 不是有限数"
}

foreach ($name in @("self_use_ratio", "green_ratio", "sell_ratio")) {
    if (-Not ($summary.green_indicators.PSObject.Properties.Name -contains $name)) {
        Write-Error "green_indicators 缺少字段: $name"
    }
    $value = [double]$summary.green_indicators.$name
    if ($value -lt 0 -or $value -gt 1) {
        Write-Error "$name 应在 [0, 1] 范围内，当前为 $value"
    }
}

$rows = Import-Csv $hourlyPath
if ($rows.Count -ne 576) {
    Write-Error "p3_hourly_cases.csv 应为 24*24=576 行，当前为 $($rows.Count)"
}

foreach ($col in $requiredColumns) {
    if (-Not ($rows[0].PSObject.Properties.Name -contains $col)) {
        Write-Error "p3_hourly_cases.csv 缺少字段: $col"
    }
}

$scenarioIds = $rows | Select-Object -ExpandProperty scenario_id -Unique
if ($scenarioIds.Count -ne 24) {
    Write-Error "场景数量应为 24，当前为 $($scenarioIds.Count)"
}

foreach ($sid in $scenarioIds) {
    $hours = $rows | Where-Object { $_.scenario_id -eq $sid }
    if ($hours.Count -ne 24) {
        Write-Error "场景 $sid 的小时数应为 24，当前为 $($hours.Count)"
    }
}

foreach ($row in $rows) {
    foreach ($col in $nonnegativeColumns) {
        $value = [double]$row.$col
        if ($value -lt -1e-6) {
            Write-Error "$col 出现负值: $value"
        }
    }
}

$figures = Get-ChildItem figures -Filter "p3_*.pdf" -ErrorAction SilentlyContinue
if ($figures.Count -eq 0) {
    Write-Error "缺少问题三图表文件: figures/p3_*.pdf"
}

Write-Host "问题三结果结构检查通过。" -ForegroundColor Green
