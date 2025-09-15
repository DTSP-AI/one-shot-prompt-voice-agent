param(
    [string]$Tag = "latest",
    [switch]$NoBuild = $false,
    [switch]$NoCache = $false
)

Write-Host "🐳 Building OneShotVoiceAgent Docker Images..." -ForegroundColor Green

try {
    $buildArgs = @()
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }

    if (-not $NoBuild) {
        Write-Host "Building backend image..." -ForegroundColor Yellow
        $backendCmd = @("docker", "build") + $buildArgs + @("-f", "Dockerfile.backend", "-t", "oneshot-backend:$Tag", ".")
        & $backendCmd[0] $backendCmd[1..($backendCmd.Length-1)]

        if ($LASTEXITCODE -ne 0) {
            throw "Backend image build failed"
        }

        Write-Host "Building frontend image..." -ForegroundColor Yellow
        $frontendCmd = @("docker", "build") + $buildArgs + @("-f", "Dockerfile.frontend", "-t", "oneshot-frontend:$Tag", ".")
        & $frontendCmd[0] $frontendCmd[1..($frontendCmd.Length-1)]

        if ($LASTEXITCODE -ne 0) {
            throw "Frontend image build failed"
        }

        Write-Host "✅ Docker images built successfully" -ForegroundColor Green
    }

    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found. Creating from .env.example"
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Host "📋 Please edit .env file with your configuration" -ForegroundColor Yellow
        } else {
            Write-Error ".env.example file not found"
            exit 1
        }
    }

    Write-Host "Starting services with Docker Compose..." -ForegroundColor Yellow
    docker-compose up -d

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed to start services"
    }

    Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
    $retries = 0
    $maxRetries = 24  # 2 minutes max wait

    do {
        Start-Sleep -Seconds 5

        # Check backend health
        $backendHealth = "unknown"
        try {
            $backendInspect = docker inspect oneshot-backend --format='{{.State.Health.Status}}' 2>$null
            if ($LASTEXITCODE -eq 0) {
                $backendHealth = $backendInspect.Trim()
            }
        } catch {
            $backendHealth = "unknown"
        }

        # Check frontend health
        $frontendHealth = "unknown"
        try {
            $frontendInspect = docker inspect oneshot-frontend --format='{{.State.Health.Status}}' 2>$null
            if ($LASTEXITCODE -eq 0) {
                $frontendHealth = $frontendInspect.Trim()
            }
        } catch {
            $frontendHealth = "unknown"
        }

        $retries++
        Write-Host "Health check $retries/$maxRetries - Backend: $backendHealth, Frontend: $frontendHealth" -ForegroundColor Gray

        if ($retries -gt $maxRetries) {
            Write-Warning "Services did not become healthy within 2 minutes"
            Write-Host "Checking service logs..." -ForegroundColor Yellow
            docker-compose logs --tail=20
            break
        }
    } while ($backendHealth -ne "healthy" -or $frontendHealth -ne "healthy")

    if ($backendHealth -eq "healthy" -and $frontendHealth -eq "healthy") {
        Write-Host "✅ All services are healthy!" -ForegroundColor Green
    } else {
        Write-Warning "Some services may not be fully ready"
    }

    Write-Host "`nService URLs:" -ForegroundColor Cyan
    Write-Host "• Frontend: http://localhost:3000" -ForegroundColor White
    Write-Host "• Backend API: http://localhost:8000" -ForegroundColor White
    Write-Host "• API Docs: http://localhost:8000/docs" -ForegroundColor White
    Write-Host "• Qdrant Dashboard: http://localhost:6333/dashboard" -ForegroundColor White

    Write-Host "`nDocker Commands:" -ForegroundColor Cyan
    Write-Host "• View logs: docker-compose logs -f" -ForegroundColor White
    Write-Host "• Stop services: docker-compose down" -ForegroundColor White
    Write-Host "• Restart services: docker-compose restart" -ForegroundColor White
    Write-Host "• View status: docker-compose ps" -ForegroundColor White

} catch {
    Write-Error "❌ Docker build/deployment failed: $_"
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "• Check Docker is installed and running" -ForegroundColor White
    Write-Host "• Ensure ports 3000, 8000, 6333, 6334 are not in use" -ForegroundColor White
    Write-Host "• Check .env file configuration" -ForegroundColor White
    Write-Host "• View logs: docker-compose logs" -ForegroundColor White
    Write-Host "• Clean up: docker-compose down -v" -ForegroundColor White
    exit 1
}