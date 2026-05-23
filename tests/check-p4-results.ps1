param()
$ErrorActionPreference = "Stop"

$problem = "p4"
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
    "P_charge_MW",
    "P_discharge_MW",
    "SOC_MWh",
    "P_curtail_MW",
    "NH3_t",
    "cost_yuan"
)
$nonnegativeColumns = @(
    "P_load_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_charge_MW",
    "P_discharge_MW",
    "SOC_MWh",
    "P_curtail_MW",
    "NH3_t",
    "cost_yuan"
)

Write-Host "检查问题四 (p4) 结果结构与基本数值约束..."

if (-Not (Test-Path $resultDir)) {
    Write-Warning "问题四结果尚未生成: $resultDir。后续完成 p4 求解后将启用严格结构检查。"
    exit 0
}

$missingFiles = @($summaryPath, $hourlyPath) | Where-Object { -Not (Test-Path $_) }
if ($missingFiles.Count -gt 0) {
    Write-Warning "问题四结果尚未生成完整，缺少: $($missingFiles -join ', ')。后续完成 p4 求解后将启用严格结构检查。"
    exit 0
}

$summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
foreach ($field in @("scenario_count", "annual_days", "total_production_t", "total_cost_yuan", "unit_cost_yuan_per_t", "storage_capacity_MWh", "green_indicators")) {
    if (-Not ($summary.PSObject.Properties.Name -contains $field)) {
        Write-Error "p4_summary.json 缺少字段: $field"
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
if ([double]$summary.unit_cost_yuan_per_t -lt -1e-6) {
    Write-Error "unit_cost_yuan_per_t 出现负值: $($summary.unit_cost_yuan_per_t)"
}
if ([double]$summary.total_cost_yuan -lt -1e-6) {
    Write-Error "total_cost_yuan 出现负值: $($summary.total_cost_yuan)"
}

foreach ($name in @("self_use_ratio", "green_ratio", "curtail_ratio")) {
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
    Write-Error "p4_hourly_cases.csv 应为 24*24=576 行，当前为 $($rows.Count)"
}

foreach ($col in $requiredColumns) {
    if (-Not ($rows[0].PSObject.Properties.Name -contains $col)) {
        Write-Error "p4_hourly_cases.csv 缺少字段: $col"
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

$figures = Get-ChildItem figures -Filter "p4_*.pdf" -ErrorAction SilentlyContinue
if ($figures.Count -eq 0) {
    Write-Warning "尚未发现问题四图表文件: figures/p4_*.pdf。图表生成阶段完成后应补齐。"
}

Write-Host "问题四结果结构检查通过。" -ForegroundColor Green
