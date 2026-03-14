# discli installer for Windows
# irm https://raw.githubusercontent.com/DevRohit06/discli/main/install.ps1 | iex

Write-Host "Installing discli..." -ForegroundColor Cyan
Write-Host ""

# Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Error: Python 3.10+ is required. Install from https://python.org" -ForegroundColor Red
    exit 1
}

$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pyMajor = python -c "import sys; print(sys.version_info.major)"
$pyMinor = python -c "import sys; print(sys.version_info.minor)"

if ([int]$pyMajor -lt 3 -or ([int]$pyMajor -eq 3 -and [int]$pyMinor -lt 10)) {
    Write-Host "Error: Python 3.10+ is required (found $pyVersion)" -ForegroundColor Red
    exit 1
}

Write-Host "Using Python $pyVersion" -ForegroundColor Green

# Install from GitHub
python -m pip install git+https://github.com/DevRohit06/discli.git
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: pip install failed." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Check PATH
$discliCmd = Get-Command discli -ErrorAction SilentlyContinue
if ($discliCmd) {
    Write-Host "discli is ready!" -ForegroundColor Green
    discli --help
} else {
    $scriptsDir = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
    if ($scriptsDir -and (Test-Path "$scriptsDir\discli.exe")) {
        Write-Host "discli installed to: $scriptsDir" -ForegroundColor Green
        Write-Host ""

        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -split ";" | Where-Object { $_ -eq $scriptsDir }) {
            Write-Host "Already on PATH. Restart your terminal to use discli." -ForegroundColor Yellow
        } else {
            $newPath = if ($userPath) { "$userPath;$scriptsDir" } else { $scriptsDir }
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            $env:Path = "$env:Path;$scriptsDir"
            Write-Host "Added to PATH. Restart your terminal to use discli." -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Done! Get started:" -ForegroundColor Cyan
Write-Host "  discli config set token YOUR_BOT_TOKEN"
Write-Host "  discli server list"
