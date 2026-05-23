param()
$ErrorActionPreference = "Stop"

Write-Host "检查数据是否正常被读取..."
$missingFiles = 0

$requiredDataFiles = @(
    "support/data/附件1：园区典型日常规电负荷标幺功率曲线.xlsx",
    "support/data/附件2：典型日风电、光伏标幺功率表.xlsx",
    "support/data/附件3：园区6种场景的风电标幺功率表.xlsx",
    "support/data/附件4：园区4种场景的光伏标幺功率表.xlsx",
    "support/data/附件5：风光发电与制氢设备技术参数.xlsx",
    "support/data/附件6：储能设备和合成氨装置技术参数.xlsx",
    "support/data/附件7：分时电价表.xlsx",
    "support/data/附件8：风电、光伏余电上网电价.xlsx"
)

foreach ($file in $requiredDataFiles) {
    if (-Not (Test-Path $file)) {
        Write-Error "缺失数据文件: $file"
        $missingFiles++
    }
}

if ($missingFiles -eq 0) {
    Write-Host "所有基础 Excel 附件均已就位。" -ForegroundColor Green
}
else {
    Write-Host "缺少 $missingFiles 个基础数据文件，请检查！" -ForegroundColor Red
}