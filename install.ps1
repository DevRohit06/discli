# discli installer for Windows
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

Write-Host "Installing discli..." -ForegroundColor Cyan

# Install the package
pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install package." -ForegroundColor Red
    exit 1
}

# Find where discli.exe was installed
$scriptsDir = pip show discord-cli-agent 2>$null |
    Select-String "Location:" |
    ForEach-Object { $_.Line -replace "Location: ", "" }

if ($scriptsDir) {
    # Convert site-packages path to Scripts path
    $scriptsDir = Join-Path (Split-Path $scriptsDir) "Scripts"
}

if (-not $scriptsDir -or -not (Test-Path $scriptsDir)) {
    # Fallback: search common locations
    $scriptsDir = Get-ChildItem -Path "$env:LOCALAPPDATA" -Recurse -Filter "discli.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 |
        ForEach-Object { $_.DirectoryName }
}

if (-not $scriptsDir) {
    Write-Host "Could not find discli.exe. You may need to add Python Scripts to PATH manually." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found discli at: $scriptsDir" -ForegroundColor Green

# Check if already on PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ";" | Where-Object { $_ -eq $scriptsDir }) {
    Write-Host "Already on PATH." -ForegroundColor Green
} else {
    $newPath = "$userPath;$scriptsDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$env:Path;$scriptsDir"
    Write-Host "Added to PATH: $scriptsDir" -ForegroundColor Green
    Write-Host "Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
}

# Verify
Write-Host ""
& "$scriptsDir\discli.exe" --help
Write-Host ""
Write-Host "discli installed successfully!" -ForegroundColor Cyan
Write-Host "Run 'discli config set token YOUR_BOT_TOKEN' to get started." -ForegroundColor White
