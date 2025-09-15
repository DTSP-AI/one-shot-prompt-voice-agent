param(
    [string]$PythonPath = "python"
)

Write-Host "🚀 Setting up OneShotVoiceAgent..." -ForegroundColor Green

try {
    # Verify prerequisites
    Write-Host "Checking prerequisites..." -ForegroundColor Yellow

    # Check Python version
    $pythonVersion = & $PythonPath --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found. Install Python 3.11+ and add to PATH"
    }
    Write-Host "✅ $pythonVersion" -ForegroundColor Green

    # Check Node.js version
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Node.js not found. Install Node.js 18+ and add to PATH"
    }
    Write-Host "✅ Node.js $nodeVersion" -ForegroundColor Green

    # Setup Backend
    Write-Host "`nSetting up backend..." -ForegroundColor Yellow
    Set-Location backend

    # Create virtual environment
    if (Test-Path ".venv") {
        Remove-Item -Recurse -Force ".venv"
    }
    & $PythonPath -m venv .venv

    # Activate virtual environment
    .venv\Scripts\Activate.ps1

    # Upgrade pip and install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    # Validate backend setup
    python -c "
from core.config import settings
print('✅ Backend configuration loaded')
"

    Write-Host "✅ Backend setup complete" -ForegroundColor Green

    # Setup Frontend
    Write-Host "`nSetting up frontend..." -ForegroundColor Yellow
    Set-Location ../frontend

    # Install dependencies
    npm install

    # Validate frontend build
    npm run type-check
    npm run lint

    Write-Host "✅ Frontend setup complete" -ForegroundColor Green

    # Create environment files
    Write-Host "`nCreating environment files..." -ForegroundColor Yellow
    Set-Location ..

    if (-not (Test-Path "backend/.env")) {
        Copy-Item "backend/.env.example" "backend/.env"
        Write-Host "📋 Created backend/.env from template" -ForegroundColor Yellow
    }

    if (-not (Test-Path "frontend/.env.local")) {
        Copy-Item "frontend/.env.example" "frontend/.env.local"
        Write-Host "📋 Created frontend/.env.local from template" -ForegroundColor Yellow
    }

    Write-Host "`n🎉 Setup completed successfully!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. Edit backend/.env with your API keys" -ForegroundColor White
    Write-Host "   - LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET" -ForegroundColor White
    Write-Host "   - OPENAI_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY" -ForegroundColor White
    Write-Host "2. Edit frontend/.env.local if needed" -ForegroundColor White
    Write-Host "3. Run .\scripts\start-dev.ps1 to start both servers" -ForegroundColor White
    Write-Host "`nDocumentation: See README.md for detailed setup instructions" -ForegroundColor Gray

} catch {
    Write-Error "❌ Setup failed: $_"
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "• Ensure Python 3.11+ is installed and in PATH" -ForegroundColor White
    Write-Host "• Ensure Node.js 18+ is installed and in PATH" -ForegroundColor White
    Write-Host "• Run as Administrator if permissions fail" -ForegroundColor White
    Write-Host "• Check internet connectivity for package downloads" -ForegroundColor White
    Write-Host "• Try running setup again after resolving issues" -ForegroundColor White
    exit 1
}