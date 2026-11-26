# Stop presenter-sidecar. Only closes what start.ps1 opened; your other browser windows are untouched.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfgPath = Join-Path $here 'config.json'
if (-not (Test-Path $cfgPath)) { $cfgPath = Join-Path $here 'config.example.json' }
$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$logs = Join-Path $here 'logs'
$port = if ($cfg.panel_port) { $cfg.panel_port } else { 8765 }
$base = "http://127.0.0.1:$port"
$py = Join-Path $here '.venv\Scripts\python.exe'

# 1) mirror.py: ask it to exit cleanly (releases AppBar and mouse clip); force after 5 s
$pidFile = Join-Path $logs 'mirror.pid'
if (Test-Path $pidFile) {
    $mpid = [int](Get-Content $pidFile)
    New-Item -ItemType File -Force (Join-Path $logs 'mirror.stop') | Out-Null
    for ($i = 0; $i -lt 25 -and (Get-Process -Id $mpid -ErrorAction SilentlyContinue); $i++) { Start-Sleep -Milliseconds 200 }
    if (Get-Process -Id $mpid -ErrorAction SilentlyContinue) {
        Write-Host "mirror.py not responding, forcing it to stop"
        Stop-Process -Id $mpid -Force
        & $py "$here\mirror.py" --cleanup
    }
    Remove-Item $pidFile, (Join-Path $logs 'mirror.stop') -ErrorAction SilentlyContinue
    Write-Host "mirror.py stopped"
} elseif (Test-Path (Join-Path $logs 'mirror.appbar')) {
    & $py "$here\mirror.py" --cleanup
}

# 2) Panel window (only the presenter-sidecar-panel profile)
$panel = Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='msedge.exe'" |
    Where-Object { $_.CommandLine -like '*presenter-sidecar-panel*' }
if ($panel) {
    $panel | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "Panel window closed"
}

# 3) Panel server
try {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Method Post -Headers @{ 'X-Panel' = '1' } "$base/api/shutdown" | Out-Null
    Write-Host "Panel server stopped"
} catch {
    $srvPid = Join-Path $logs 'panel_server.pid'
    if ("$($cfg.panel_runtime)".ToLower() -eq 'wsl') {
        $wslArgs = @()
        if ($cfg.wsl_distro) { $wslArgs += @('-d', $cfg.wsl_distro) }
        & wsl.exe @wslArgs -- pkill -f 'python3 panel_server.py' 2>$null
    } elseif (Test-Path $srvPid) {
        Stop-Process -Id ([int](Get-Content $srvPid)) -Force -ErrorAction SilentlyContinue
        Remove-Item $srvPid -ErrorAction SilentlyContinue
    }
}
Write-Host "All stopped."
