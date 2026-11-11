$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'
$dist = Join-Path $frontend 'dist'
$server = Join-Path $root 'backend\server.py'

if (-not (Test-Path -LiteralPath $dist)) {
    Write-Host '[1/2] frontend/dist 不存在，开始构建前端...' -ForegroundColor Cyan
    Push-Location $frontend
    try {
        pnpm build
    }
    finally {
        Pop-Location
    }
}

$bundledPython = 'C:\Users\zyf\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (Test-Path -LiteralPath $bundledPython) {
    $python = $bundledPython
}
elseif ($py) {
    $python = $py.Source
}
else {
    throw '未找到 python，请先安装 Python 或修改 start.ps1 中的解释器路径'
}

Write-Host '[2/2] 启动质量智脑：http://127.0.0.1:8010' -ForegroundColor Green
Write-Host '      停止：在本窗口按 Ctrl+C，或另开窗口运行 .\stop.ps1' -ForegroundColor DarkGray
& $python $server
