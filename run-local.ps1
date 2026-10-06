param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000,
  [switch]$NoBrowser,
  [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Test-LocalPortOpen {
  param(
    [string]$TargetHost,
    [int]$TargetPort
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $task = $client.ConnectAsync($TargetHost, $TargetPort)
    if (-not $task.Wait(300)) {
      return $false
    }
    return $client.Connected
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Open-PhotoboothUrl {
  param([string]$Url)

  if (-not $NoBrowser) {
    Start-Process $Url
  }
}

$Url = "http://${HostName}:${Port}/"

$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
  Write-Host "Creating local virtual environment in .venv..."
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 -m venv .venv
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv .venv
  } else {
    throw "Python 3.11+ was not found. Install Python first, then run this script again."
  }
}

& $Python -c "from importlib.metadata import version; import fastapi, uvicorn; version('photobooth-app')" *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Installing photobooth-app into .venv..."
  & $Python -m pip install --upgrade pip
  & $Python -m pip install -e .
}

# Rebuild the kiosk frontend only when a Node toolchain is available AND either the
# built output is stale or -BuildFrontend was passed. On a machine without Node the
# committed build under src/web/frontend/ is used as-is.
$KioskSource = Join-Path $Root "frontend-kiosk"
$KioskBuilt = Join-Path $Root "src\web\frontend\framebooth.html"
if (Test-Path -LiteralPath $KioskSource) {
  $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if ($pnpm -or $npm) {
    $newestSource = Get-ChildItem -LiteralPath (Join-Path $KioskSource "src") -Recurse -File -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $stale = $true
    if ((Test-Path -LiteralPath $KioskBuilt) -and $newestSource) {
      $stale = $newestSource.LastWriteTime -gt (Get-Item -LiteralPath $KioskBuilt).LastWriteTime
    }
    if ($BuildFrontend -or $stale) {
      Write-Host "Building kiosk frontend (frontend-kiosk)..."
      if ($pnpm) {
        & pnpm --dir $KioskSource install --frozen-lockfile
        & pnpm --dir $KioskSource run build
      } else {
        & npm --prefix $KioskSource ci
        & npm --prefix $KioskSource run build
      }
    }
  } elseif ($BuildFrontend) {
    Write-Warning "-BuildFrontend requested but neither pnpm nor npm was found on PATH."
  }
}

if (Test-LocalPortOpen -TargetHost $HostName -TargetPort $Port) {
  Write-Host "Photobooth is already running at $Url"
  Open-PhotoboothUrl -Url $Url
  exit 0
}

if (-not $NoBrowser) {
  $OpenCommand = "Start-Sleep -Seconds 4; Start-Process '$Url'"
  Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $OpenCommand
}

Write-Host "Starting Photobooth at $Url"
Write-Host "Press Ctrl+C in this window to stop."
& $Python -m photobooth --host $HostName --port $Port
