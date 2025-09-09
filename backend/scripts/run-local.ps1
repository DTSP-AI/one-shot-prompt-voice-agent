param(
    [int]$Port = $null,
    [string]$Host = "0.0.0.0",
    [string]$LogLevel = $null,
    [switch]$Reload = $false
)

Write-Host "🚀 Starting LiveKit LangGraph Voice Agent..." -ForegroundColor Green

try {
    # Check if virtual environment exists
    if (-not (Test-Path ".venv")) { 
        Write-Error "Virtual environment not found. Run .\scripts\setup.ps1 first."
        exit 1
    }
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\.venv\Scripts\Activate.ps1
    
    # Set environment variables with defaults
    if (-not $Port) {
        $env:PORT = if ($env:PORT) { $env:PORT } else { "8000" }
    } else {
        $env:PORT = $Port
    }
    
    if ($LogLevel) {
        $env:LOG_LEVEL = $LogLevel
    } elseif (-not $env:LOG_LEVEL) {
        $env:LOG_LEVEL = "INFO"
    }
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Warning "No .env file found. Using environment variables only."
        Write-Host "Consider creating .env from .env.example with your API keys." -ForegroundColor Yellow
    } else {
        Write-Host "✅ Using .env configuration" -ForegroundColor Green
    }
    
    # Validate critical environment variables
    Write-Host "Validating environment configuration..." -ForegroundColor Yellow
    
    $criticalVars = @("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    $missing = @()
    
    foreach ($var in $criticalVars) {
        if (-not (Get-ChildItem Env:$var -ErrorAction SilentlyContinue)) {
            $missing += $var
        }
    }
    
    if ($missing.Count -gt 0) {
        Write-Warning "Missing critical environment variables:"
        foreach ($var in $missing) {
            Write-Host "  ❌ $var" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "The server will start but may not function properly." -ForegroundColor Yellow
        Write-Host "Please set these variables in your .env file." -ForegroundColor Yellow
        
        # Ask user if they want to continue
        $response = Read-Host "Continue anyway? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            Write-Host "Startup cancelled." -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "✅ Environment configuration looks good" -ForegroundColor Green
    }
    
    # Build uvicorn command
    $uvicornArgs = @(
        "app:app",
        "--host", $Host,
        "--port", $env:PORT,
        "--log-level", $env:LOG_LEVEL.ToLower()
    )
    
    if ($Reload) {
        $uvicornArgs += "--reload"
        Write-Host "🔄 Auto-reload enabled for development" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "Starting server with configuration:" -ForegroundColor Cyan
    Write-Host "  Host: $Host" -ForegroundColor White
    Write-Host "  Port: $($env:PORT)" -ForegroundColor White  
    Write-Host "  Log Level: $($env:LOG_LEVEL)" -ForegroundColor White
    Write-Host "  Reload: $Reload" -ForegroundColor White
    Write-Host ""
    
    Write-Host "🌐 Server will be available at: http://localhost:$($env:PORT)" -ForegroundColor Green
    Write-Host "📖 API documentation: http://localhost:$($env:PORT)/docs" -ForegroundColor Green
    Write-Host "🔧 Health check: http://localhost:$($env:PORT)/health" -ForegroundColor Green
    Write-Host ""
    Write-Host "Press Ctrl+C to stop the server..." -ForegroundColor Yellow
    Write-Host ""
    
    # Start the server
    uvicorn @uvicornArgs
    
} catch {
    Write-Error "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ☠️ Server startup failed: $_"
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "• Check that setup.ps1 completed successfully" -ForegroundColor White
    Write-Host "• Verify .env file has correct API keys" -ForegroundColor White
    Write-Host "• Ensure port $($env:PORT) is not already in use" -ForegroundColor White
    Write-Host "• Check Python package installations" -ForegroundColor White
    Write-Host "• Review logs above for specific error details" -ForegroundColor White
    exit 1
}