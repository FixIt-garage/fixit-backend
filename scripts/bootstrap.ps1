<#
.SYNOPSIS
  One-command local setup for fixit-backend (Windows PowerShell 5.1 or PowerShell 7).

.DESCRIPTION
  Creates .env (with a generated JWT_SECRET_KEY), builds and starts Postgres + the API
  with Docker Compose and waits until /health is OK.
  Safe to run again: an existing .env is kept (only an empty JWT_SECRET_KEY gets filled in).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Seed
#>
param(
    # Also load dev seed data after the API is up.
    [switch]$Seed
)

# Native commands (docker) report failures via $LASTEXITCODE, checked explicitly below.
$ErrorActionPreference = 'Continue'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Stop-WithError([string]$Message) {
    Write-Host "`nERROR: $Message" -ForegroundColor Red
    exit 1
}

# A JWT_SECRET_KEY assignment as docker compose / python-dotenv accept it:
# optional "export", spaces around the key and "=".
$JwtLinePattern = '^\s*(export\s+)?JWT_SECRET_KEY\s*='

# Value of an assignment line without surrounding spaces, quotes or an inline comment.
function Get-EnvValue([string]$Line) {
    $raw = $Line -replace '^[^=]*=', ''
    $value = $raw.TrimStart()
    if ($value.StartsWith('"') -or $value.StartsWith("'")) {
        # Quoted: the value ends at the closing quote; only spaces or a comment may follow.
        $end = $value.IndexOf($value[0], 1)
        if ($end -gt 0 -and $value.Substring($end + 1) -match '^\s*(#.*)?$') {
            return $value.Substring(1, $end - 1).Trim()
        }
    }
    # Unquoted: " #..." (a # after whitespace) starts a comment.
    return ($raw -replace '\s+#.*$', '').Trim()
}

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    Write-Step 'Checking Docker'
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Stop-WithError 'Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop/'
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker is not running. Start Docker Desktop and run this script again.' }
    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Docker Compose v2 ('docker compose') is required." }

    Write-Step 'Preparing .env'
    $envPath = Join-Path $root '.env'
    if (Test-Path $envPath) {
        Write-Host '.env already exists, keeping it.'
        # Explicit UTF-8: Windows PowerShell 5.1 would read a file without BOM as ANSI.
        $lines = @(Get-Content -LiteralPath $envPath -Encoding UTF8)
    } else {
        $lines = @(Get-Content -LiteralPath (Join-Path $root '.env.example') -Encoding UTF8)
        Write-Host 'Creating .env from .env.example.'
    }
    # The last assignment wins, as in docker compose and python-dotenv.
    $keyLines = @($lines | Where-Object { $_ -cmatch $JwtLinePattern })
    $currentKey = if ($keyLines.Count -gt 0) { Get-EnvValue $keyLines[-1] } else { '' }
    $changed = -not (Test-Path $envPath)
    if (-not $currentKey) {
        $newLine = "JWT_SECRET_KEY=$(New-Secret)"
        if ($keyLines.Count -gt 0) {
            # Replace every (empty) assignment, keep all other lines as they are.
            $lines = @($lines | ForEach-Object { if ($_ -cmatch $JwtLinePattern) { $newLine } else { $_ } })
        } else {
            $lines += @('', $newLine)
        }
        $changed = $true
        Write-Host 'Generated a new JWT_SECRET_KEY in .env.'
    }
    if ($changed) {
        # UTF-8 without BOM: docker compose and python-dotenv read the first key wrongly with a BOM.
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($envPath, [string[]]$lines, $utf8NoBom)
    }

    Write-Step 'Building and starting Postgres + backend (first run can take a few minutes)'
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError ("docker compose failed. If it says 'port is already allocated', set POSTGRES_PORT in .env " +
            '(e.g. 5433) or stop whatever uses port 8000. See README > Troubleshooting.')
    }

    Write-Step 'Waiting for the API to become healthy'
    $probe = "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"
    $healthy = $false
    for ($i = 0; $i -lt 60; $i++) {
        docker compose exec -T backend python -c $probe *> $null
        if ($LASTEXITCODE -eq 0) { $healthy = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) {
        docker compose logs --tail 40 backend
        Stop-WithError 'The API did not become healthy within 2 minutes. See the backend logs above.'
    }

    if ($Seed) {
        Write-Step 'Loading dev seed data'
        docker compose exec -T backend python -m app.seed
        if ($LASTEXITCODE -ne 0) { Stop-WithError 'Loading seed data failed. See the output above.' }
    }

    Write-Host ''
    Write-Host 'FixIt backend is running.' -ForegroundColor Green
    Write-Host '  API:          http://localhost:8000'
    Write-Host '  Health check: http://localhost:8000/health'
    Write-Host '  API docs:     http://localhost:8000/docs'
    Write-Host ''
    Write-Host '  Logs:  docker compose logs -f backend'
    Write-Host '  Stop:  docker compose down        (add -v to also delete the database)'
} finally {
    Pop-Location
}
