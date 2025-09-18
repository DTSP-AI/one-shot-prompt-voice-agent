Write-Host "🚀 Starting OneShotVoiceAgent development servers..." -ForegroundColor Green

try {
    # Check if environment files exist
    if (-not (Test-Path "backend/.env")) {
        Write-Warning "backend/.env not found. Run .\scripts\setup.ps1 first"
        exit 1
    }

    if (-not (Test-Path "frontend/.env.local")) {
        Write-Warning "frontend/.env.local not found. Run .\scripts\setup.ps1 first"
        exit 1
    }

    # Start backend server
    Write-Host "Starting backend server..." -ForegroundColor Yellow
    $backendJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD\backend
        .\.venv\Scripts\Activate.ps1
        python main.py
    }

    # Wait a moment for backend to start
    Start-Sleep -Seconds 5

    # Check if backend started successfully
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 10
        Write-Host "✅ Backend server started successfully" -ForegroundColor Green
        Write-Host "   Backend: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
    } catch {
        Write-Warning "Backend server may not be fully ready yet"
        Write-Host "   Check backend logs if issues persist" -ForegroundColor Gray
    }

    # Start frontend server
    Write-Host "Starting frontend server..." -ForegroundColor Yellow
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD\frontend
        npm run dev
    }

    # Wait for frontend to start
    Start-Sleep -Seconds 10

    Write-Host "✅ Development servers started!" -ForegroundColor Green
    Write-Host "`nApplication URLs:" -ForegroundColor Cyan
    Write-Host "• Frontend: http://localhost:3000" -ForegroundColor White
    Write-Host "• Backend API: http://localhost:8000" -ForegroundColor White
    Write-Host "• API Documentation: http://localhost:8000/docs" -ForegroundColor White
    Write-Host "• Health Check: http://localhost:8000/health" -ForegroundColor White

    Write-Host "`nPress Ctrl+C to stop servers" -ForegroundColor Yellow

    # Monitor jobs and keep script running
    while ($backendJob.State -eq "Running" -or $frontendJob.State -eq "Running") {
        Start-Sleep -Seconds 5

        # Check backend job
        if ($backendJob.State -eq "Failed") {
            Write-Error "Backend server failed!"
            Receive-Job $backendJob -ErrorAction SilentlyContinue
            break
        }

        # Check frontend job
        if ($frontendJob.State -eq "Failed") {
            Write-Error "Frontend server failed!"
            Receive-Job $frontendJob -ErrorAction SilentlyContinue
            break
        }
    }

} catch {
    Write-Error "❌ Failed to start development servers: $_"
} finally {
    # Cleanup jobs
    if ($backendJob) {
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -ErrorAction SilentlyContinue
    }

    if ($frontendJob) {
        Stop-Job $frontendJob -ErrorAction SilentlyContinue
        Remove-Job $frontendJob -ErrorAction SilentlyContinue
    }

    Write-Host "`n🛑 Development servers stopped" -ForegroundColor Red
}