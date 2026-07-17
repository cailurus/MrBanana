# Mr. Banana - Quick Start Script (PowerShell)
# Usage: .\run.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$ChromeProfile = "C:\temp\mcp-chrome-profile"
$CDPPort = 9222

# -------------------------------------------------------------------
# 1. Launch Chrome with CDP debugging for cookie extraction
# -------------------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mr. Banana - Cookie Helper" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$cdpRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$CDPPort/json" -TimeoutSec 2 -ErrorAction Stop
    $cdpRunning = $true
} catch {
    $cdpRunning = $false
}

if (-not $cdpRunning) {
    if (Test-Path $ChromePath) {
        Write-Host "Launching Chrome with CDP mode..." -ForegroundColor Green
        Start-Process -FilePath $ChromePath -ArgumentList @(
            "--remote-debugging-port=$CDPPort",
            "--user-data-dir=`"$ChromeProfile`"",
            "--remote-allow-origins=*"
        )
        Start-Sleep -Seconds 2
        # Open jable.tv login page in the CDP-enabled Chrome
        Start-Process -FilePath $ChromePath -ArgumentList @(
            "--remote-debugging-port=$CDPPort",
            "--user-data-dir=`"$ChromeProfile`"",
            "https://jable.tv/login/"
        )
    } else {
        Write-Host "WARNING: Chrome not found at $ChromePath" -ForegroundColor Yellow
        Write-Host "  Please start Chrome manually with:" -ForegroundColor Yellow
        Write-Host "  chrome --remote-debugging-port=$CDPPort --remote-allow-origins=*" -ForegroundColor DarkGray
    }
} else {
    Write-Host "Chrome CDP already running on port $CDPPort" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  請在 Chrome 中登錄 jable.tv" -ForegroundColor Yellow
Write-Host "  登錄完成後，按任意鍵繼續啟動 Mr. Banana..." -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# -------------------------------------------------------------------
# 2. Setup virtual environment
# -------------------------------------------------------------------
Write-Host ""
$VenvActivate = Join-Path $ScriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    . $VenvActivate
} else {
    Write-Host "WARNING: .venv not found at $VenvActivate" -ForegroundColor Yellow
    Write-Host "Run: python -m venv .venv && .venv\Scripts\Activate.ps1 && pip install -r requirements.txt" -ForegroundColor Yellow
}

# -------------------------------------------------------------------
# 3. Build frontend if needed
# -------------------------------------------------------------------
if (-not (Test-Path "static/index.html")) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location web
    npm run build
    Pop-Location
    if (Test-Path "web/dist/index.html") {
        Remove-Item -Recurse -Force static -ErrorAction SilentlyContinue
        Copy-Item -Recurse web/dist static
        Write-Host "Frontend built and copied to static/" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Frontend build failed or web/dist/ not found. Skipping." -ForegroundColor Yellow
    }
}

# -------------------------------------------------------------------
# 4. Auto-extract cookies from CDP Chrome and write to config
# -------------------------------------------------------------------
Write-Host "Extracting jable.tv cookies from Chrome..." -ForegroundColor Green
try {
    $cookieResult = python -c @"
import json, sys
sys.path.insert(0, r'$ScriptDir')
from scripts.mcp_cdp_cookie_server import extract_cookies_for_domain, format_for_mr_banana
try:
    cookies = extract_cookies_for_domain('jable.tv')
    result = format_for_mr_banana(cookies)
    print('COOKIE_OK')
    print(result['jable_cookie'])
except Exception as e:
    print('COOKIE_ERR: ' + str(e))
"@ 2>&1
    if ($cookieResult -match "COOKIE_OK") {
        $cookieLine = ($cookieResult | Select-String -Pattern "^PHPSESSID=" -SimpleMatch).Line
        if ($cookieLine) {
            $cookieStr = $cookieLine.Trim()
            python -c @"
import json
from mr_banana.utils.config import load_config, save_config
cfg = load_config()
cfg.jable_cookie = r'$cookieStr'
save_config(cfg)
print('Cookie saved to config.json')
"@
            Write-Host "jable.tv cookie extracted and saved to config.json!" -ForegroundColor Green
        }
    } else {
        Write-Host "Cookie extraction: $cookieResult" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Cookie extraction failed (Chrome CDP may not be running): $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "You can still extract cookies later via MCP or browser console script." -ForegroundColor DarkGray
}

# -------------------------------------------------------------------
# 5. Start server
# -------------------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mr. Banana starting at" -ForegroundColor Cyan -NoNewline
Write-Host " http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  (Press Ctrl+C to stop)" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
