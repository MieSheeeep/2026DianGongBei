param()
$ErrorActionPreference = "Stop"

$problem = "p3"
$resultDir = "support/results/$problem"
$summaryPath = "$resultDir/${problem}_summary.json"
$hourlyPath = "$resultDir/${problem}_hourly_cases.csv"
$dailyPath = "$resultDir/${problem}_daily_cases.csv"
$requiredHourlyColumns = @(
    "scenario_id",
    "target_NH3_t_per_day",
    "hour",
    "P_load_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "H2_prod_kg",
    "H2_cons_kg",
    "cost_yuan",
    "sell_revenue_yuan",
    "net_cost_yuan"
)
$requiredDailyColumns = @(
    "scenario_id",
    "target_NH3_t_per_day",
    "E_re_MWh",
    "E_buy_MWh",
    "E_sell_MWh",
    "E_self_MWh",
    "E_total_MWh",
    "E_use_MWh",
    "NH3_t",
    "H2_prod_kg",
    "H2_cons_kg",
    "self_use_ratio",
    "green_ratio",
    "green_internal_use_ratio",
    "sell_ratio",
    "daily_cost_yuan",
    "daily_sell_revenue_yuan",
    "daily_net_cost_yuan",
    "unit_cost_yuan_per_t",
    "indicator_class"
)
$nonnegativeColumns = @(
    "target_NH3_t_per_day",
    "P_load_MW",
    "P_re_MW",
    "P_alk_MW",
    "P_pem_MW",
    "P_nh3_MW",
    "P_buy_MW",
    "P_sell_MW",
    "P_curtail_MW",
    "NH3_t",
    "H2_prod_kg",
    "H2_cons_kg",
    "cost_yuan",
    "sell_revenue_yuan"
)
$expectedProduction = @(36, 45, 54, 63, 72)
$tol = 1e-5

Write-Host "检查问题三 (p3) 结果结构与基本数值约束..."

if (-Not (Test-Path $resultDir)) {
    Write-Warning "问题三结果尚未生成: $resultDir。后续完成 p3 求解后将启用严格结构检查。"
    exit 0
}

$missingFiles = @($summaryPath, $hourlyPath, $dailyPath) | Where-Object { -Not (Test-Path $_) }
if ($missingFiles.Count -gt 0) {
    Write-Warning "问题三结果尚未生成完整，缺少: $($missingFiles -join ', ')。后续完成 p3 求解后将启用严格结构检查。"
    exit 0
}

$summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
foreach ($field in @("scenario_count", "annual_days", "production_levels_t_per_day", "total_production_t", "total_cost_yuan", "unit_cost_yuan_per_t", "green_indicators", "annual_recommended", "annual_by_production")) {
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
$expectedHourlyRows = 24 * 24 * $expectedProduction.Count
$expectedDailyRows = 24 * $expectedProduction.Count
if ($rows.Count -ne $expectedHourlyRows) {
    Write-Error "p3_hourly_cases.csv 应为 24 场景 * $($expectedProduction.Count) 个产量 * 24 小时 = $expectedHourlyRows 行，当前为 $($rows.Count)"
}
if ($dailyRows.Count -ne $expectedDailyRows) {
    Write-Error "p3_daily_cases.csv 应为 24 场景 * $($expectedProduction.Count) 个产量 = $expectedDailyRows 行，当前为 $($dailyRows.Count)"
}

foreach ($col in $requiredHourlyColumns) {
    if (-Not ($rows[0].PSObject.Properties.Name -contains $col)) {
        Write-Error "p3_hourly_cases.csv 缺少字段: $col"
    }
}
foreach ($col in $requiredDailyColumns) {
    if (-Not ($dailyRows[0].PSObject.Properties.Name -contains $col)) {
        Write-Error "p3_daily_cases.csv 缺少字段: $col"
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
    if ([double]$row.P_alk_MW -lt 2.0 - 1e-5 -or [double]$row.P_alk_MW -gt 20.0 + 1e-5) {
        Write-Error "ALK 功率超出 10%-100% 范围: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([double]$row.P_pem_MW -lt 2.0 - 1e-5 -or [double]$row.P_pem_MW -gt 20.0 + 1e-5) {
        Write-Error "PEM 功率超出 10%-100% 范围: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([double]$row.NH3_t -lt 0.3 - 1e-5 -or [double]$row.NH3_t -gt 3.0 + 1e-5) {
        Write-Error "合成氨产量超出 10%-100% 范围: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([math]::Abs(([double]$row.P_nh3_MW) - 0.5 * ([double]$row.NH3_t)) -gt 1e-5) {
        Write-Error "合成氨功率与产量关系不一致: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([math]::Abs(([double]$row.H2_prod_kg) - ([double]$row.H2_cons_kg)) -gt 1e-4) {
        Write-Error "逐小时产氢耗氢不平衡: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    $balanceLeft = [double]$row.P_re_MW + [double]$row.P_buy_MW
    $balanceRight = [double]$row.P_load_MW + [double]$row.P_alk_MW + [double]$row.P_pem_MW + [double]$row.P_nh3_MW + [double]$row.P_sell_MW + [double]$row.P_curtail_MW
    if ([math]::Abs($balanceLeft - $balanceRight) -gt 1e-5) {
        Write-Error "功率平衡失败: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([double]$row.P_buy_MW -gt 1e-6 -and [double]$row.P_sell_MW -gt 1e-6) {
        Write-Error "同一小时同时购电和售电: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
    if ([math]::Abs(([double]$row.net_cost_yuan) - ([double]$row.cost_yuan - [double]$row.sell_revenue_yuan)) -gt 1e-4) {
        Write-Error "逐时净成本公式不一致: scenario=$($row.scenario_id), target=$($row.target_NH3_t_per_day), hour=$($row.hour)"
    }
}

foreach ($daily in $dailyRows) {
    $caseRows = $rows | Where-Object { $_.scenario_id -eq $daily.scenario_id -and [double]$_.target_NH3_t_per_day -eq [double]$daily.target_NH3_t_per_day }
    $nh3 = ($caseRows | Measure-Object -Property NH3_t -Sum).Sum
    if ([math]::Abs([double]$nh3 - [double]$daily.target_NH3_t_per_day) -gt 1e-5) {
        Write-Error "日产量不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day), sum=$nh3"
    }
    if ([math]::Abs(([double]$daily.NH3_t) - [double]$nh3) -gt 1e-5) {
        Write-Error "日汇总 NH3_t 与小时求和不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.H2_prod_kg) - ([double]$daily.H2_cons_kg)) -gt 1e-3) {
        Write-Error "日汇总产氢耗氢不平衡: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.E_self_MWh) - ([double]$daily.E_re_MWh - [double]$daily.E_sell_MWh)) -gt 1e-5) {
        Write-Error "E_self 公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
    }
    if ([math]::Abs(([double]$daily.E_total_MWh) - ([double]$daily.E_re_MWh + [double]$daily.E_buy_MWh)) -gt 1e-5) {
        Write-Error "E_total 题目口径公式不一致: scenario=$($daily.scenario_id), target=$($daily.target_NH3_t_per_day)"
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

$figures = Get-ChildItem figures -Filter "p3_*.pdf" -ErrorAction SilentlyContinue
if ($figures.Count -eq 0) {
    Write-Warning "尚未发现问题三图表文件: figures/p3_*.pdf。图表生成阶段完成后应补齐。"
}

Write-Host "问题三结果结构检查通过。" -ForegroundColor Green
