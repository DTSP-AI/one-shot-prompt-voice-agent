param(
    [string]$TestPath = "tests/",
    [switch]$Coverage = $false,
    [switch]$Verbose = $false,
    [string]$Pattern = $null
)

Write-Host "🧪 Running LiveKit LangGraph Voice Agent Tests..." -ForegroundColor Green

try {
    # Check if virtual environment exists
    if (-not (Test-Path ".venv")) { 
        throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
    }
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\.venv\Scripts\Activate.ps1
    
    # Verify pytest is installed
    pip show pytest | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pytest not installed. Run .\scripts\setup.ps1 to install dependencies."
    }
    
    # Build pytest arguments
    $pytestArgs = @()
    
    # Add coverage if requested
    if ($Coverage) {
        Write-Host "📊 Coverage reporting enabled" -ForegroundColor Cyan
        $pytestArgs += "--cov=agents", "--cov=tools", "--cov-report=term-missing", "--cov-report=html"
    }
    
    # Add verbose if requested
    if ($Verbose) {
        $pytestArgs += "-v"
    } else {
        $pytestArgs += "-q"
    }
    
    # Add pattern filter if specified
    if ($Pattern) {
        Write-Host "🔍 Running tests matching pattern: $Pattern" -ForegroundColor Cyan
        $pytestArgs += "-k", $Pattern
    }
    
    # Add test path
    if (Test-Path $TestPath) {
        $pytestArgs += $TestPath
    } else {
        throw "Test path '$TestPath' not found"
    }
    
    # Display test configuration
    Write-Host ""
    Write-Host "Test Configuration:" -ForegroundColor Cyan
    Write-Host "  Path: $TestPath" -ForegroundColor White
    Write-Host "  Coverage: $Coverage" -ForegroundColor White
    Write-Host "  Verbose: $Verbose" -ForegroundColor White
    if ($Pattern) {
        Write-Host "  Pattern: $Pattern" -ForegroundColor White
    }
    Write-Host ""
    
    # Run pre-test validation
    Write-Host "Running pre-test validation..." -ForegroundColor Yellow
    
    # Check if test files exist
    $testFiles = Get-ChildItem -Path $TestPath -Filter "test_*.py" -Recurse
    if ($testFiles.Count -eq 0) {
        Write-Warning "No test files found in $TestPath"
    } else {
        Write-Host "✅ Found $($testFiles.Count) test files" -ForegroundColor Green
    }
    
    # Basic import test
    $importTest = & python -c "
try:
    import agents.state
    import agents.graph
    import tools.livekit_io
    print('✅ Core modules import successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"
    
    if ($LASTEXITCODE -ne 0) {
        throw "Module import validation failed"
    }
    
    Write-Host ""
    Write-Host "🏃‍♂️ Running tests..." -ForegroundColor Green
    Write-Host "=" * 60
    
    # Run pytest
    pytest @pytestArgs
    $testExitCode = $LASTEXITCODE
    
    Write-Host "=" * 60
    
    if ($testExitCode -eq 0) {
        Write-Host ""
        Write-Host "🎉 All tests passed!" -ForegroundColor Green
        
        if ($Coverage) {
            Write-Host ""
            Write-Host "📊 Coverage report generated:" -ForegroundColor Cyan
            Write-Host "  Terminal: See output above" -ForegroundColor White
            Write-Host "  HTML: htmlcov/index.html" -ForegroundColor White
        }
        
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "• Review any warnings in test output" -ForegroundColor White
        Write-Host "• Run with --coverage to check test coverage" -ForegroundColor White
        Write-Host "• Run .\scripts\run-local.ps1 to start the server" -ForegroundColor White
        
    } elseif ($testExitCode -eq 1) {
        Write-Host ""
        Write-Error "❌ Some tests failed"
        Write-Host ""
        Write-Host "Troubleshooting:" -ForegroundColor Yellow
        Write-Host "• Review failed test output above" -ForegroundColor White
        Write-Host "• Check test dependencies and mocks" -ForegroundColor White
        Write-Host "• Verify .env configuration if tests require it" -ForegroundColor White
        Write-Host "• Run specific test: pytest tests/test_specific.py::test_function" -ForegroundColor White
        
    } elseif ($testExitCode -eq 2) {
        Write-Error "❌ Test execution interrupted or configuration error"
    } elseif ($testExitCode -eq 3) {
        Write-Error "❌ Internal error occurred during test execution"
    } elseif ($testExitCode -eq 4) {
        Write-Error "❌ pytest command line usage error"
    } elseif ($testExitCode -eq 5) {
        Write-Warning "⚠️ No tests were collected"
    } else {
        Write-Error "❌ Unexpected test failure (exit code: $testExitCode)"
    }
    
    exit $testExitCode
    
} catch {
    Write-Error "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ☠️ Test execution failed: $_"
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "• Ensure setup.ps1 completed successfully" -ForegroundColor White
    Write-Host "• Check that virtual environment is properly configured" -ForegroundColor White
    Write-Host "• Verify test files exist in $TestPath" -ForegroundColor White
    Write-Host "• Check Python and pytest installations" -ForegroundColor White
    exit 1
}