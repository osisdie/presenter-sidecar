# Start presenter-sidecar: panel server -> panel window (Chrome/Edge --app) -> mirror.py
# Usage: double-click start.bat, or: powershell -ExecutionPolicy Bypass -File start.ps1 [-Profile <name>]
# -Profile picks the panel profile (notes, timer sections, follow rules); e.g. a meeting.bat with
#   call "%~dp0start.bat" -Profile meeting
# If the panel server is already running, its open panels are asked to switch to that profile.
param([Alias('Profile')][string]$SessionProfile = '')  # $PROFILE is a PowerShell built-in: do not shadow it
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfgPath = Join-Path $here 'config.json'
if (-not (Test-Path $cfgPath)) {
    Copy-Item (Join-Path $here 'config.example.json') $cfgPath
    Write-Host "Created config.json from config.example.json (edit it to customise)."
}
$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$logs = Join-Path $here 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
Remove-Item (Join-Path $logs 'mirror.stop') -ErrorAction SilentlyContinue

$port = if ($cfg.panel_port) { $cfg.panel_port } else { 8765 }
$base = "http://127.0.0.1:$port"
$runtime = if ($cfg.panel_runtime) { "$($cfg.panel_runtime)".ToLower() } else { 'windows' }
$py = Join-Path $here '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Python venv not found: $py. Create it first (see README, Quick start)." }

function Test-Panel {
    try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$base/api/health").StatusCode -eq 200 } catch { $false }
}

# 1) Panel server
if (Test-Panel) {
    Write-Host "Panel server already running: $base"
    if ($SessionProfile) {
        try {
            # Bytes, not a string: Windows PowerShell 5.1 sends a string body as ISO-8859-1: a Chinese name would arrive as "??". Keep this file ASCII (no BOM).
            $json = @{ name = $SessionProfile } | ConvertTo-Json -Compress
            Invoke-RestMethod -Method Post -Uri "$base/api/profile" -Headers @{ 'X-Panel' = '1' } `
                -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json)) | Out-Null
            Write-Host "Asked the panel to switch to profile '$SessionProfile'"
        } catch { Write-Warning "Profile '$SessionProfile' not switched: $($_.Exception.Message)" }
    }
} else {
    if ($runtime -eq 'wsl') {
        # \\wsl.localhost\<distro>\home\... -> /home/... ; any other path -> wslpath (e.g. C:\... -> /mnt/c/...)
        if ($here -match '^\\\\wsl(\.localhost|\$)\\[^\\]+') {
            $wslHere = ($here -replace '^\\\\wsl(\.localhost|\$)\\[^\\]+', '') -replace '\\', '/'
        } else {
            $wslHere = (& wsl.exe wslpath -u ($here -replace '\\', '/')).Trim()
        }
        $wslArgs = @()
        if ($cfg.wsl_distro) { $wslArgs += @('-d', $cfg.wsl_distro) }
        # Quotes are stripped as in the Windows branch below: the name sits inside '...' inside "..." here.
        $profArg = if ($SessionProfile) { " --profile '" + ($SessionProfile -replace "['""]", "") + "'" } else { '' }
        $cmd = "cd '$wslHere' && mkdir -p logs && exec python3 panel_server.py$profArg >> logs/panel_server.log 2>&1"
        Write-Host "Starting panel server in WSL..."
        Start-Process -WindowStyle Hidden -FilePath 'wsl.exe' -ArgumentList ($wslArgs + @('--', 'bash', '-lc', "`"$cmd`""))
    } else {
        Write-Host "Starting panel server (Windows Python)..."
        $serverArgs = "`"$here\panel_server.py`""
        if ($SessionProfile) { $serverArgs += " --profile `"$($SessionProfile -replace '"', '')`"" }
        Start-Process -WindowStyle Hidden -FilePath $py -WorkingDirectory $here -ArgumentList $serverArgs `
            -RedirectStandardOutput (Join-Path $logs 'panel_server.log') -RedirectStandardError (Join-Path $logs 'panel_server.err.log')
    }
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) { Start-Sleep -Milliseconds 500; if (Test-Panel) { $ok = $true; break } }
    if (-not $ok) { throw "Panel server did not start. See logs\panel_server*.log" }
    Write-Host "Panel server OK: $base"
}

# 2) Panel window: Chrome/Edge --app with its own profile (does not touch your normal browser profile)
$browser = $null
if ($cfg.panel_browser -and (Test-Path $cfg.panel_browser)) { $browser = $cfg.panel_browser }
if (-not $browser) {
    $browser = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
$profileDir = Join-Path $env:LOCALAPPDATA 'presenter-sidecar-panel'
$running = Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='msedge.exe'" |
    Where-Object { $_.CommandLine -like '*presenter-sidecar-panel*' }
if ($running) {
    Write-Host "Panel window already open"
} elseif ($browser) {
    # Initial position in DIPs (the browser scales it); mirror.py then docks it exactly in physical pixels.
    Add-Type -AssemblyName System.Windows.Forms
    $scr = [System.Windows.Forms.Screen]::PrimaryScreen
    $ratio = if ($cfg.panel_width_ratio) { [double]$cfg.panel_width_ratio } else { 0.26 }
    $w = [int]($scr.Bounds.Width * $ratio)
    $x = $scr.Bounds.Right - $w
    $h = $scr.WorkingArea.Height
    Start-Process -FilePath $browser -ArgumentList @(
        "--app=$base/", "--user-data-dir=`"$profileDir`"", '--no-first-run', '--no-default-browser-check',
        '--disable-features=Translate', "--window-position=$x,0", "--window-size=$w,$h")
    Write-Host "Panel window opened ($browser)"
} else {
    Write-Warning "Chrome / Edge not found. Open $base manually or set panel_browser in config.json."
}

# 3) Mirror (Windows Python)
$pidFile = Join-Path $logs 'mirror.pid'
$alive = $false
if (Test-Path $pidFile) { $alive = [bool](Get-Process -Id (Get-Content $pidFile) -ErrorAction SilentlyContinue) }
if ($alive) {
    Write-Host "mirror.py already running"
} else {
    Start-Process -WindowStyle Hidden -FilePath $py -WorkingDirectory $here -ArgumentList "`"$here\mirror.py`"" `
        -RedirectStandardOutput (Join-Path $logs 'mirror.log') -RedirectStandardError (Join-Path $logs 'mirror.err.log')
    Write-Host "mirror.py started (log: logs\mirror.log)"
}
$hk = $cfg.hotkeys
Write-Host ""
Write-Host "Done. Hotkeys: $($hk.pick) pick source | $($hk.bring) bring source back | $($hk.freeze) freeze | $($hk.blank) blank | $($hk.style) ring/spotlight"
Write-Host "       $($hk.next) / $($hk.prev) notes | $($hk.popups) follow popups | $($hk.clip) mouse lock | $($hk.quit) quit mirror"
Write-Host "Online meetings: share 'entire screen -> display 2' (the projector), never the laptop display."
