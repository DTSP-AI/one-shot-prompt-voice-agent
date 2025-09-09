param(
    [string]$OutputPath = "./dist",
    [switch]$IncludeVenv = $false,
    [switch]$CreateZip = $false
)

Write-Host "📦 Packaging LiveKit LangGraph Voice Agent..." -ForegroundColor Green

try {
    # Create output directory
    if (Test-Path $OutputPath) {
        Write-Host "Cleaning existing output directory..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $OutputPath
    }
    New-Item -ItemType Directory -Path $OutputPath | Out-Null
    
    Write-Host "✅ Created output directory: $OutputPath" -ForegroundColor Green
    
    # Define what to include
    $includeItems = @(
        "agents/",
        "tools/", 
        "scripts/",
        "app.py",
        "requirements.txt",
        "pyproject.toml",
        ".env.example"
    )
    
    # Define what to exclude
    $excludePatterns = @(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".pytest_cache",
        "htmlcov/",
        ".coverage",
        "*.log"
    )
    
    Write-Host "Copying application files..." -ForegroundColor Yellow
    
    # Copy included items
    foreach ($item in $includeItems) {
        if (Test-Path $item) {
            $destPath = Join-Path $OutputPath $item
            
            if (Test-Path $item -PathType Container) {
                # It's a directory
                Write-Host "  📁 $item" -ForegroundColor White
                Copy-Item -Recurse $item $destPath
            } else {
                # It's a file
                Write-Host "  📄 $item" -ForegroundColor White
                Copy-Item $item $destPath
            }
        } else {
            Write-Warning "⚠️  Item not found: $item"
        }
    }
    
    # Clean up excluded patterns
    Write-Host "Cleaning up excluded files..." -ForegroundColor Yellow
    foreach ($pattern in $excludePatterns) {
        $itemsToRemove = Get-ChildItem -Path $OutputPath -Recurse -Name $pattern -Force 2>$null
        foreach ($item in $itemsToRemove) {
            $fullPath = Join-Path $OutputPath $item
            if (Test-Path $fullPath) {
                Remove-Item -Recurse -Force $fullPath
                Write-Host "  🗑️  Removed: $item" -ForegroundColor Gray
            }
        }
    }
    
    # Include virtual environment if requested
    if ($IncludeVenv -and (Test-Path ".venv")) {
        Write-Host "Including virtual environment..." -ForegroundColor Yellow
        Copy-Item -Recurse ".venv" (Join-Path $OutputPath ".venv")
        Write-Host "  ✅ Virtual environment included" -ForegroundColor Green
    }
    
    # Create Dockerfile in output
    Write-Host "Creating Dockerfile..." -ForegroundColor Yellow
    $dockerfileContent = @"
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Start the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"@
    
    Set-Content -Path (Join-Path $OutputPath "Dockerfile") -Value $dockerfileContent
    Write-Host "  ✅ Dockerfile created" -ForegroundColor Green
    
    # Create deployment README
    Write-Host "Creating deployment README..." -ForegroundColor Yellow
    $readmeContent = @"
# LiveKit LangGraph Voice Agent - Deployment Package

This package contains the complete backend application ready for deployment.

## Contents

- `agents/` - Agent implementation (supervisor, orchestrator, coder, qa, deployer)
- `tools/` - Integration tools (LiveKit, Deepgram, ElevenLabs, Mem0, etc.)
- `scripts/` - PowerShell scripts for setup and management
- `app.py` - FastAPI application entry point
- `requirements.txt` - Python dependencies
- `pyproject.toml` - Project configuration
- `.env.example` - Environment variables template
- `Dockerfile` - Container build instructions

## Quick Start

### Local Deployment

1. Copy `.env.example` to `.env` and configure your API keys
2. Run setup script: `.\scripts\setup.ps1`
3. Start the server: `.\scripts\run-local.ps1`

### Docker Deployment

```bash
# Build the image
docker build -t voice-agent .

# Run with environment file
docker run -p 8000:8000 --env-file .env voice-agent
```

### Environment Variables Required

- `LIVEKIT_URL` - Your LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret
- `DEEPGRAM_API_KEY` - Deepgram API key for STT
- `ELEVENLABS_API_KEY` - ElevenLabs API key for TTS

See `.env.example` for complete list.

## Health Check

Once running, check health at: `http://localhost:8000/health`

## API Documentation

Interactive API docs available at: `http://localhost:8000/docs`

Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@
    
    Set-Content -Path (Join-Path $OutputPath "README-DEPLOYMENT.md") -Value $readmeContent
    Write-Host "  ✅ Deployment README created" -ForegroundColor Green
    
    # Create version info
    Write-Host "Creating version info..." -ForegroundColor Yellow
    $versionInfo = @{
        build_date = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        git_commit = if (Get-Command git -ErrorAction SilentlyContinue) { 
            git rev-parse --short HEAD 2>$null 
        } else { "unknown" }
        packaged_by = $env:USERNAME
        platform = "Windows"
        python_version = & python --version 2>&1
    }
    
    $versionInfo | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $OutputPath "version.json")
    Write-Host "  ✅ Version info created" -ForegroundColor Green
    
    # Get package size
    $packageSize = (Get-ChildItem -Recurse $OutputPath | Measure-Object -Property Length -Sum).Sum / 1MB
    
    Write-Host ""
    Write-Host "📊 Package Summary:" -ForegroundColor Cyan
    Write-Host "  Location: $OutputPath" -ForegroundColor White
    Write-Host "  Size: $([math]::Round($packageSize, 2)) MB" -ForegroundColor White
    Write-Host "  Files: $((Get-ChildItem -Recurse $OutputPath).Count)" -ForegroundColor White
    Write-Host "  Includes venv: $IncludeVenv" -ForegroundColor White
    
    # Create zip if requested
    if ($CreateZip) {
        Write-Host ""
        Write-Host "Creating zip archive..." -ForegroundColor Yellow
        $zipPath = "$OutputPath.zip"
        
        if (Test-Path $zipPath) {
            Remove-Item $zipPath
        }
        
        Compress-Archive -Path "$OutputPath\*" -DestinationPath $zipPath
        $zipSize = (Get-Item $zipPath).Length / 1MB
        
        Write-Host "  ✅ Zip created: $zipPath" -ForegroundColor Green
        Write-Host "  📊 Zip size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "🎉 Packaging completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "• Copy package to target deployment environment" -ForegroundColor White
    Write-Host "• Configure .env file with production API keys" -ForegroundColor White
    Write-Host "• Follow README-DEPLOYMENT.md instructions" -ForegroundColor White
    if ($CreateZip) {
        Write-Host "• Upload $zipPath.zip for deployment" -ForegroundColor White
    }
    
} catch {
    Write-Error "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ☠️ Packaging failed: $_"
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "• Check file permissions in source directory" -ForegroundColor White
    Write-Host "• Ensure no files are locked by other processes" -ForegroundColor White
    Write-Host "• Verify sufficient disk space in output location" -ForegroundColor White
    exit 1
}