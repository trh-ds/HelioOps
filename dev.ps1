$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$held = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($held) {
    $owner = Get-Process -Id $held.OwningProcess -ErrorAction SilentlyContinue
    Write-Error "Port 8000 is already in use by PID $($held.OwningProcess) ($($owner.ProcessName)). Stop it first:  taskkill /T /F /PID $($held.OwningProcess)"
    exit 1
}

$backend = Start-Process -PassThru -WorkingDirectory $root `
    -FilePath "$root\backend\.venv\Scripts\python.exe" `
    -ArgumentList '-m', 'uvicorn', 'backend.app:app', '--reload', '--port', '8000'

try {
    npm --prefix "$root\frontend" run dev
}
finally {
    if (-not $backend.HasExited) { taskkill /T /F /PID $backend.Id 2>&1 | Out-Null }
}
