# 构建脚本：把分模块源码合并为单文件 LifeSimulator.py
param(
    [string]$Workspace = "C:\Users\刘石珣\Documents\deepseek-harness\default-workspace"
)
$parts = @(
    "part1_header.py",
    "part2_city_disease.py",
    "part3_events.py",
    "part4_player_engine.py",
    "part5_ui_main.py"
)
$sb = New-Object System.Text.StringBuilder
foreach ($p in $parts) {
    $full = Join-Path (Join-Path $Workspace "build") $p
    if (-not (Test-Path $full)) { throw "缺少模块文件: $full" }
    [void]$sb.Append((Get-Content -Raw -Encoding UTF8 $full))
    [void]$sb.Append("`r`n")
}
$out = Join-Path $Workspace "LifeSimulator.py"
[System.IO.File]::WriteAllText($out, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("已生成: {0}  ({1} 字节, {2} 行)" -f $out, (Get-Item $out).Length, (Get-Content $out).Count)
