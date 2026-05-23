param()
$ErrorActionPreference = "Stop"

$problem = "p2"
$resultDir = "support/results/$problem"
$summaryPath = "$resultDir/${problem}_summary.json"
$hourlyPath = "$resultDir/${problem}_hourly_cases.csv"
$dailyPath = "$resultDir/${problem}_daily_cases.csv"
$typicalHourlyPath = "$resultDir/${problem}_typical_hourly.csv"
$typicalDailyPath = "$resultDir/${problem}_typical_daily.csv"
$requiredColumns = @(
    "scenario_id",
    "target_NH3_t_per_day",
    "hour",
    "P_load_MW",
    "P_re_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "cost_yuan"
)
$nonnegativeColumns = @(
    "target_NH3_t_per_day",
    "P_load_MW",
    "P_re_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "cost_yuan"
)
$expectedProduction = @(36, 45, 54, 63, 72)

Write-Host "检查问题二 (p2) 结果结构与基本数值约束..."

if (-Not (Test-Path $resultDir)) {
    Write-Error "问题二结果目录不存在: $resultDir。请先运行 python support/code/p2_solve.py。"
}

$missingFiles = @($summaryPath, $hourlyPath, $dailyPath, $typicalHourlyPath, $typicalDailyPath) | Where-Object { -Not (Test-Path $_) }
if ($missingFiles.Count -gt 0) {
    Write-Error "问题二结果缺失: $($missingFiles -join ', ')"
}

$summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
foreach ($field in @("scenario_count", "annual_days", "production_levels_t_per_day", "total_production_t", "total_cost_yuan", "unit_cost_yuan_per_t", "green_indicators")) {
    if (-Not ($summary.PSObject.Properties.Name -contains $field)) {
        Write-Error "p2_summary.json 缺少字段: $field"
    }
}

if ([int]$summary.scenario_count -ne 24) {
    Write-Error "scenario_count 应为 24，当前为 $($summary.scenario_count)"
}
if ([int]$summary.annual_days -ne 360) {
    Write-Error "annual_days 应为 360，即 24 个场景各代表 15 天，当前为 $($summary.annual_days)"
}
$unitCost = [double]$summary.unit_cost_yuan_per_t
if ([double]::IsNaN($unitCost) -or [double]::IsInfinity($unitCost)) {
    Write-Error "unit_cost_yuan_per_t 不是有限数"
}
if ($unitCost -lt -1e-6) {
    Write-Error "unit_cost_yuan_per_t 出现负值: $($summary.unit_cost_yuan_per_t)"
}
if ([double]$summary.total_cost_yuan -lt -1e-6) {
    Write-Error "total_cost_yuan 出现负值: $($summary.total_cost_yuan)"
}

$levels = @($summary.production_levels_t_per_day | ForEach-Object { [double]$_ })
foreach ($target in $expectedProduction) {
    if (-Not ($levels -contains [double]$target)) {
        Write-Error "production_levels_t_per_day 未覆盖日产量: $target t/d"
    }
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
$dailyRows = Import-Csv $dailyPath
$typicalRows = Import-Csv $typicalHourlyPath
$typicalDailyRows = Import-Csv $typicalDailyPath

$expectedRows = 24 * 24 * $expectedProduction.Count
if ($rows.Count -ne $expectedRows) {
    Write-Error "p2_hourly_cases.csv 应为 24 场景 * $($expectedProduction.Count) 个产量 * 24 小时 = $expectedRows 行，当前为 $($rows.Count)"
}
if ($dailyRows.Count -ne (24 * $expectedProduction.Count)) {
    Write-Error "p2_daily_cases.csv 应为 24 场景 * $($expectedProduction.Count) 个产量 = $(24 * $expectedProduction.Count) 行，当前为 $($dailyRows.Count)"
}
if ($typicalRows.Count -ne (24 * $expectedProduction.Count)) {
    Write-Error "p2_typical_hourly.csv 应为 $($expectedProduction.Count) 个产量 * 24 小时 = $(24 * $expectedProduction.Count) 行，当前为 $($typicalRows.Count)"
}
if ($typicalDailyRows.Count -ne $expectedProduction.Count) {
    Write-Error "p2_typical_daily.csv 应为 $($expectedProduction.Count) 行，当前为 $($typicalDailyRows.Count)"
}

foreach ($col in $requiredColumns) {
    if (-Not ($rows[0].PSObject.Properties.Name -contains $col)) {
        Write-Error "p2_hourly_cases.csv 缺少字段: $col"
    }
}

$scenarioIds = $rows | Select-Object -ExpandProperty scenario_id -Unique
if ($scenarioIds.Count -ne 24) {
    Write-Error "场景数量应为 24，当前为 $($scenarioIds.Count)"
}

$targets = $rows | Select-Object -ExpandProperty target_NH3_t_per_day -Unique
foreach ($target in $expectedProduction) {
    if (-Not (($targets | ForEach-Object { [double]$_ }) -contains [double]$target)) {
        Write-Error "小时结果未覆盖日产量: $target t/d"
    }
}

foreach ($sid in $scenarioIds) {
    foreach ($target in $expectedProduction) {
        $hours = $rows | Where-Object { $_.scenario_id -eq $sid -and [double]$_.target_NH3_t_per_day -eq [double]$target }
        if ($hours.Count -ne 24) {
            Write-Error "场景 $sid、日产量 $target t/d 的小时数应为 24，当前为 $($hours.Count)"
        }
    }
}

foreach ($row in $rows) {
    foreach ($col in $nonnegativeColumns) {
        $value = [double]$row.$col
        if ($value -lt -1e-6) {
            Write-Error "$col 出现负值: $value"
        }
    }
    $balanceLeft = [double]$row.P_re_MW + [double]$row.P_buy_MW
    $balanceRight = [double]$row.P_load_MW + [double]$row.P_alk_MW + [double]$row.P_pem_MW + [double]$row.P_nh3_MW + [double]$row.P_sell_MW + [double]$row.P_curtail_MW
    if ([math]::Abs($balanceLeft - $balanceRight) -gt 1e-5) {
        Write-Error "功率平衡失败: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([double]$row.P_buy_MW -gt 1e-6 -and [double]$row.P_sell_MW -gt 1e-6) {
        Write-Error "同一小时同时购电和售电: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
}

foreach ($daily in $dailyRows) {
    $caseRows = $rows | Where-Object { $_.scenario_id -eq $daily.scenario_id -and [double]$_.target_NH3_t_per_day -eq [double]$daily.target_NH3_t_per_day }
    $nh3 = ($caseRows | Measure-Object -Property NH3_t -Sum).Sum
    if ([math]::Abs([double]$nh3 - [double]$daily.target_NH3_t_per_day) -gt 1e-5) {
        Write-Error "日产量不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day), sum=$nh3"
    }
    if ([math]::Abs(([double]$daily.E_self_MWh) - ([double]$daily.E_re_MWh - [double]$daily.E_sell_MWh)) -gt 1e-5) {
        Write-Error "E_self 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.E_total_MWh) - ([double]$daily.E_re_MWh + [double]$daily.E_buy_MWh)) -gt 1e-5) {
        Write-Error "E_total 题目口径公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.E_use_MWh) - ([double]$daily.E_load_MWh + [double]$daily.E_alk_MWh + [double]$daily.E_pem_MWh + [double]$daily.E_nh3_MWh)) -gt 1e-5) {
        Write-Error "E_use 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.self_use_ratio) - ([double]$daily.E_self_MWh / [double]$daily.E_re_MWh)) -gt 1e-5) {
        Write-Error "self_use_ratio 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.green_ratio) - ([double]$daily.E_self_MWh / [double]$daily.E_total_MWh)) -gt 1e-5) {
        Write-Error "green_ratio 题目口径公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.sell_ratio) - ([double]$daily.E_sell_MWh / [double]$daily.E_re_MWh)) -gt 1e-5) {
        Write-Error "sell_ratio 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.green_internal_use_ratio) - ([double]$daily.E_self_MWh / [double]$daily.E_use_MWh)) -gt 1e-5) {
        Write-Error "green_internal_use_ratio 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.daily_net_cost_yuan) - ([double]$daily.daily_cost_yuan - [double]$daily.daily_sell_revenue_yuan)) -gt 1e-4) {
        Write-Error "日净成本公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.unit_cost_yuan_per_t) - ([double]$daily.daily_net_cost_yuan / [double]$daily.target_NH3_t_per_day)) -gt 1e-4) {
        Write-Error "吨氨成本公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
}

$recommended = $summary.annual_recommended
foreach ($name in @("self_use_ratio", "green_ratio", "sell_ratio")) {
    $expected = [double]$recommended.green_indicators.$name
    $actual = [double]$summary.green_indicators.$name
    if ([math]::Abs($expected - $actual) -gt 1e-6) {
        Write-Error "summary.green_indicators.$name 与 annual_recommended 不一致"
    }
}
$annualEnergy = $recommended.energy_MWh
if ([math]::Abs(([double]$recommended.green_indicators.self_use_ratio) - ([double]$annualEnergy.self_use / [double]$annualEnergy.renewable)) -gt 1e-6) {
    Write-Error "annual_recommended self_use_ratio 公式不一致"
}
if ([math]::Abs(([double]$recommended.green_indicators.green_ratio) - ([double]$annualEnergy.self_use / [double]$annualEnergy.total_wide)) -gt 1e-6) {
    Write-Error "annual_recommended green_ratio 题目口径公式不一致"
}
if ([math]::Abs(([double]$recommended.green_indicators.sell_ratio) - ([double]$annualEnergy.grid_sell / [double]$annualEnergy.renewable)) -gt 1e-6) {
    Write-Error "annual_recommended sell_ratio 公式不一致"
}

foreach ($target in $expectedProduction) {
    $prodRows = $dailyRows | Where-Object { [double]$_.target_NH3_t_per_day -eq [double]$target }
    $annual = $summary.annual_by_production."$target"
    $annualProduction = ($prodRows | Measure-Object -Property target_NH3_t_per_day -Sum).Sum * 15
    $annualCost = ($prodRows | Measure-Object -Property daily_net_cost_yuan -Sum).Sum * 15
    if ([math]::Abs([double]$annual.total_production_t - [double]$annualProduction) -gt 1e-4) {
        Write-Error "全年产量折算不一致: target=$target"
    }
    if ([math]::Abs([double]$annual.total_cost_yuan - [double]$annualCost) -gt 1e-2) {
        Write-Error "全年成本折算不一致: target=$target"
    }
}

$figures = Get-ChildItem figures -Filter "p2_*.pdf" -ErrorAction SilentlyContinue
if ($figures.Count -eq 0) {
    Write-Warning "尚未发现问题二图表文件: figures/p2_*.pdf。图表生成阶段完成后应补齐。"
}

Write-Host "问题二结果结构检查通过。" -ForegroundColor Green
