Write-Host "🔍 Validating OneShotVoiceAgent Installation..." -ForegroundColor Green

$validationResults = @{
    Backend = @{}
    Frontend = @{}
    Services = @{}
    Docker = @{}
}

try {
    # Backend Validation
    Write-Host "`n🔧 Validating Backend..." -ForegroundColor Yellow

    # Check Python virtual environment
    if (Test-Path "backend\.venv\Scripts\python.exe") {
        $validationResults.Backend.VirtualEnv = "✅ Found"
        Write-Host "✅ Python virtual environment found" -ForegroundColor Green
    } else {
        $validationResults.Backend.VirtualEnv = "❌ Missing"
        Write-Host "❌ Python virtual environment not found" -ForegroundColor Red
    }

    # Check backend dependencies
    Set-Location backend
    if (Test-Path ".venv") {
        .\.venv\Scripts\Activate.ps1

        try {
            python -c "
import fastapi, uvicorn, langgraph, livekit, mem0ai
print('✅ Core dependencies installed')
" 2>$null

            if ($LASTEXITCODE -eq 0) {
                $validationResults.Backend.Dependencies = "✅ Installed"
                Write-Host "✅ Backend dependencies installed" -ForegroundColor Green
            } else {
                throw "Dependency check failed"
            }
        } catch {
            $validationResults.Backend.Dependencies = "❌ Missing"
            Write-Host "❌ Backend dependencies missing" -ForegroundColor Red
        }

        # Test backend imports
        try {
            python -c "
from core.config import settings
from models.agent import AgentPayload
from services.livekit_service import LiveKitManager
print('✅ Backend imports successful')
" 2>$null

            if ($LASTEXITCODE -eq 0) {
                $validationResults.Backend.Imports = "✅ Valid"
                Write-Host "✅ Backend imports successful" -ForegroundColor Green
            } else {
                throw "Import check failed"
            }
        } catch {
            $validationResults.Backend.Imports = "❌ Failed"
            Write-Host "❌ Backend import errors found" -ForegroundColor Red
        }
    }

    Set-Location ..

    # Frontend Validation
    Write-Host "`n🎨 Validating Frontend..." -ForegroundColor Yellow
    Set-Location frontend

    # Check node_modules
    if (Test-Path "node_modules") {
        $validationResults.Frontend.Dependencies = "✅ Installed"
        Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
    } else {
        $validationResults.Frontend.Dependencies = "❌ Missing"
        Write-Host "❌ Frontend dependencies missing" -ForegroundColor Red
    }

    # TypeScript compilation check
    try {
        npm run type-check 2>$null
        if ($LASTEXITCODE -eq 0) {
            $validationResults.Frontend.TypeScript = "✅ Valid"
            Write-Host "✅ TypeScript compilation successful" -ForegroundColor Green
        } else {
            throw "TypeScript compilation failed"
        }
    } catch {
        $validationResults.Frontend.TypeScript = "❌ Errors"
        Write-Host "❌ TypeScript compilation errors" -ForegroundColor Red
    }

    # Linting check
    try {
        npm run lint 2>$null
        if ($LASTEXITCODE -eq 0) {
            $validationResults.Frontend.Linting = "✅ Clean"
            Write-Host "✅ ESLint validation passed" -ForegroundColor Green
        } else {
            $validationResults.Frontend.Linting = "⚠️ Warnings"
            Write-Host "⚠️ ESLint warnings found" -ForegroundColor Yellow
        }
    } catch {
        $validationResults.Frontend.Linting = "❌ Errors"
        Write-Host "❌ ESLint errors found" -ForegroundColor Red
    }

    Set-Location ..

    # Environment Configuration
    Write-Host "`n⚙️ Validating Configuration..." -ForegroundColor Yellow

    # Backend environment
    if (Test-Path "backend\.env") {
        $backendEnv = Get-Content "backend\.env" -Raw
        $requiredKeys = @('LIVEKIT_URL', 'LIVEKIT_API_KEY', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY', 'ELEVENLABS_API_KEY')
        $missingKeys = @()

        foreach ($key in $requiredKeys) {
            if ($backendEnv -notmatch "$key=.+") {
                $missingKeys += $key
            }
        }

        if ($missingKeys.Count -eq 0) {
            $validationResults.Backend.Environment = "✅ Configured"
            Write-Host "✅ Backend environment configured" -ForegroundColor Green
        } else {
            $validationResults.Backend.Environment = "⚠️ Incomplete"
            Write-Host "⚠️ Missing backend environment variables: $($missingKeys -join ', ')" -ForegroundColor Yellow
        }
    } else {
        $validationResults.Backend.Environment = "❌ Missing"
        Write-Host "❌ Backend .env file missing" -ForegroundColor Red
    }

    # Frontend environment
    if (Test-Path "frontend\.env.local") {
        $validationResults.Frontend.Environment = "✅ Configured"
        Write-Host "✅ Frontend environment configured" -ForegroundColor Green
    } else {
        $validationResults.Frontend.Environment = "⚠️ Optional"
        Write-Host "⚠️ Frontend .env.local file missing (optional)" -ForegroundColor Yellow
    }

    # Docker Validation
    Write-Host "`n🐳 Validating Docker Setup..." -ForegroundColor Yellow

    try {
        docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $validationResults.Docker.Engine = "✅ Available"
            Write-Host "✅ Docker engine available" -ForegroundColor Green
        } else {
            throw "Docker not found"
        }
    } catch {
        $validationResults.Docker.Engine = "❌ Missing"
        Write-Host "❌ Docker engine not available" -ForegroundColor Red
    }

    try {
        docker-compose --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $validationResults.Docker.Compose = "✅ Available"
            Write-Host "✅ Docker Compose available" -ForegroundColor Green
        } else {
            throw "Docker Compose not found"
        }
    } catch {
        $validationResults.Docker.Compose = "❌ Missing"
        Write-Host "❌ Docker Compose not available" -ForegroundColor Red
    }

    # Service Connectivity (if servers are running)
    Write-Host "`n🌐 Testing Service Connectivity..." -ForegroundColor Yellow

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 5
        $validationResults.Services.Backend = "✅ Running"
        Write-Host "✅ Backend API responding" -ForegroundColor Green
    } catch {
        $validationResults.Services.Backend = "⚠️ Not Running"
        Write-Host "⚠️ Backend API not responding (may not be started)" -ForegroundColor Yellow
    }

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -Method Get -TimeoutSec 5 -UseBasicParsing
        $validationResults.Services.Frontend = "✅ Running"
        Write-Host "✅ Frontend responding" -ForegroundColor Green
    } catch {
        $validationResults.Services.Frontend = "⚠️ Not Running"
        Write-Host "⚠️ Frontend not responding (may not be started)" -ForegroundColor Yellow
    }

    # Generate Validation Report
    Write-Host "`n📋 Validation Report" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan

    Write-Host "`nBackend:" -ForegroundColor White
    foreach ($key in $validationResults.Backend.Keys) {
        Write-Host "  $key`: $($validationResults.Backend[$key])" -ForegroundColor Gray
    }

    Write-Host "`nFrontend:" -ForegroundColor White
    foreach ($key in $validationResults.Frontend.Keys) {
        Write-Host "  $key`: $($validationResults.Frontend[$key])" -ForegroundColor Gray
    }

    Write-Host "`nDocker:" -ForegroundColor White
    foreach ($key in $validationResults.Docker.Keys) {
        Write-Host "  $key`: $($validationResults.Docker[$key])" -ForegroundColor Gray
    }

    Write-Host "`nServices:" -ForegroundColor White
    foreach ($key in $validationResults.Services.Keys) {
        Write-Host "  $key`: $($validationResults.Services[$key])" -ForegroundColor Gray
    }

    # Overall Status
    $errors = 0
    $warnings = 0

    foreach ($category in $validationResults.Values) {
        foreach ($result in $category.Values) {
            if ($result -like "❌*") { $errors++ }
            elseif ($result -like "⚠️*") { $warnings++ }
        }
    }

    Write-Host "`n📊 Summary:" -ForegroundColor Cyan
    if ($errors -eq 0 -and $warnings -eq 0) {
        Write-Host "🎉 All validations passed! Your installation is ready." -ForegroundColor Green
    } elseif ($errors -eq 0) {
        Write-Host "✅ Core installation valid with $warnings warning(s)" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Found $errors error(s) and $warnings warning(s)" -ForegroundColor Red
        Write-Host "Please resolve errors before proceeding" -ForegroundColor Red
    }

    Write-Host "`nNext Steps:" -ForegroundColor Cyan
    if ($errors -gt 0) {
        Write-Host "• Run .\scripts\setup.ps1 to fix installation issues" -ForegroundColor White
        Write-Host "• Configure missing environment variables" -ForegroundColor White
    } elseif ($validationResults.Services.Backend -like "⚠️*") {
        Write-Host "• Run .\scripts\start-dev.ps1 to start development servers" -ForegroundColor White
    } else {
        Write-Host "• Your installation is ready to use!" -ForegroundColor White
        Write-Host "• Visit http://localhost:3000 to access the application" -ForegroundColor White
    }

} catch {
    Write-Error "❌ Validation failed: $_"
    exit 1
}