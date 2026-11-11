param(
    [int[]]$Ports = @(8010)
)

$ErrorActionPreference = 'SilentlyContinue'
$found = $false

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess
        if ($process) {
            Stop-Process -Id $process.Id -Force
            Write-Host "已停止端口 $port 上的进程：$($process.ProcessName)（PID $($process.Id)）" -ForegroundColor Green
            $found = $true
        }
    }
}

if (-not $found) {
    Write-Host "端口 $($Ports -join ' / ') 上没有发现运行中的服务。" -ForegroundColor Yellow
}
