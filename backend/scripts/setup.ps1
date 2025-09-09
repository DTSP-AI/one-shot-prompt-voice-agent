param([string]$Py="python")

Write-Host "🚀 Setting up LiveKit LangGraph Voice Agent Backend..." -ForegroundColor Green

try {
    # Check Python version
    Write-Host "Checking Python installation..." -ForegroundColor Yellow
    & $Py --version
    if ($LASTEXITCODE -ne 0) { 
        throw "Python not found. Please install Python 3.11+ and ensure it's in PATH."
    }
    
    $pythonVersion = & $Py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $majorMinor = [decimal]$pythonVersion
    if ($majorMinor -lt 3.11) {
        throw "Python 3.11 or higher required. Found: Python $pythonVersion"
    }
    
    Write-Host "✅ Python $pythonVersion detected" -ForegroundColor Green
    
    # Create virtual environment
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    if (Test-Path ".venv") {
        Write-Host "Virtual environment already exists. Removing old one..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force ".venv"
    }
    
    & $Py -m venv .venv
    if ($LASTEXITCODE -ne 0) { 
        throw "Failed to create virtual environment"
    }
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\.venv\Scripts\Activate.ps1
    
    # Upgrade pip
    Write-Host "Upgrading pip..." -ForegroundColor Yellow
    pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { 
        throw "Failed to upgrade pip"
    }
    
    # Install requirements
    Write-Host "Installing Python packages..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { 
        throw "Failed to install requirements"
    }
    
    # Verify key packages
    Write-Host "Verifying installations..." -ForegroundColor Yellow
    $packages = @("fastapi", "uvicorn", "langgraph", "langchain", "livekit", "deepgram-sdk", "elevenlabs")
    foreach ($package in $packages) {
        pip show $package | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "⚠️  Package $package may not be installed correctly"
        } else {
            Write-Host "  ✅ $package" -ForegroundColor Green
        }
    }
    
    # Check environment file
    Write-Host "Checking environment configuration..." -ForegroundColor Yellow
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Host "📋 Created .env from .env.example" -ForegroundColor Yellow
            Write-Host "⚠️  Please edit .env and add your API keys!" -ForegroundColor Red
        } else {
            Write-Warning "No .env.example found. You'll need to create .env manually."
        }
    } else {
        Write-Host "✅ .env file exists" -ForegroundColor Green
    }
    
    # Run basic tests
    Write-Host "Running basic validation tests..." -ForegroundColor Yellow
    $testResult = & python -c "
import sys
try:
    import fastapi
    import uvicorn
    import langgraph
    import langchain
    print('✅ Core packages imported successfully')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
    
    if ($LASTEXITCODE -ne 0) {
        throw "Package validation failed"
    }
    
    Write-Host ""
    Write-Host "🎉 Backend setup completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Edit .env file with your API keys" -ForegroundColor White
    Write-Host "2. Run: .\scripts\test.ps1 to run tests" -ForegroundColor White
    Write-Host "3. Run: .\scripts\run-local.ps1 to start the server" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Error "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ☠️ Setup failed: $_"
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "• Ensure Python 3.11+ is installed" -ForegroundColor White
    Write-Host "• Check that pip is available" -ForegroundColor White
    Write-Host "• Try running as Administrator" -ForegroundColor White
    Write-Host "• Check internet connectivity for package downloads" -ForegroundColor White
    exit 1
}