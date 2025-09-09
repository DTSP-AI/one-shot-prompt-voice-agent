# Azure-ready (OFF) — do not run
# 
# This script is prepared for Azure Container Apps deployment but is currently disabled.
# Uncomment and configure the parameters below before use.
# 
# Write-Host "Azure Container Apps deployment (DISABLED)" -ForegroundColor Red
# Write-Host "This deployment option is currently turned OFF as specified." -ForegroundColor Yellow
# Write-Host "To enable: uncomment the script below and configure your Azure parameters." -ForegroundColor Yellow
# exit 0

<#
param(
    [string]$ResourceGroup = "voice-agent-rg",
    [string]$Location = "eastus",
    [string]$AppName = "voice-agent-app",
    [string]$Environment = "voice-agent-env",
    [string]$ContainerRegistry = "voiceagentregistry",
    [string]$ImageTag = "latest"
)

Write-Host "🚀 Deploying LiveKit LangGraph Voice Agent to Azure Container Apps..." -ForegroundColor Green

try {
    # Check Azure CLI
    Write-Host "Checking Azure CLI..." -ForegroundColor Yellow
    az --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI not found. Please install Azure CLI first."
    }
    
    # Check login status
    Write-Host "Checking Azure login status..." -ForegroundColor Yellow
    $account = az account show --query "user.name" -o tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $account) {
        Write-Host "Not logged into Azure. Please login..." -ForegroundColor Yellow
        az login
        if ($LASTEXITCODE -ne 0) {
            throw "Azure login failed"
        }
    } else {
        Write-Host "✅ Logged in as: $account" -ForegroundColor Green
    }
    
    # Create resource group
    Write-Host "Creating resource group: $ResourceGroup..." -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create resource group"
    }
    Write-Host "✅ Resource group created" -ForegroundColor Green
    
    # Create container registry
    Write-Host "Creating Azure Container Registry: $ContainerRegistry..." -ForegroundColor Yellow
    az acr create --resource-group $ResourceGroup --name $ContainerRegistry --sku Basic --admin-enabled true --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create container registry"
    }
    Write-Host "✅ Container registry created" -ForegroundColor Green
    
    # Build and push container image
    Write-Host "Building and pushing container image..." -ForegroundColor Yellow
    $registryServer = az acr show --name $ContainerRegistry --query "loginServer" -o tsv
    
    # Build with ACR Build
    az acr build --registry $ContainerRegistry --image "voice-agent:$ImageTag" . --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build container image"
    }
    Write-Host "✅ Container image built and pushed" -ForegroundColor Green
    
    # Create Container Apps environment
    Write-Host "Creating Container Apps environment: $Environment..." -ForegroundColor Yellow
    az containerapp env create --name $Environment --resource-group $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Container Apps environment"
    }
    Write-Host "✅ Container Apps environment created" -ForegroundColor Green
    
    # Get registry credentials
    Write-Host "Getting registry credentials..." -ForegroundColor Yellow
    $registryUsername = az acr credential show --name $ContainerRegistry --query "username" -o tsv
    $registryPassword = az acr credential show --name $ContainerRegistry --query "passwords[0].value" -o tsv
    
    # Create container app
    Write-Host "Creating container app: $AppName..." -ForegroundColor Yellow
    
    $containerAppConfig = @"
{
  "properties": {
    "managedEnvironmentId": "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$ResourceGroup/providers/Microsoft.App/managedEnvironments/$Environment",
    "configuration": {
      "secrets": [
        {
          "name": "registry-password",
          "value": "$registryPassword"
        },
        {
          "name": "livekit-api-key",
          "value": "your-livekit-api-key-here"
        },
        {
          "name": "livekit-api-secret", 
          "value": "your-livekit-api-secret-here"
        },
        {
          "name": "deepgram-api-key",
          "value": "your-deepgram-api-key-here"
        },
        {
          "name": "elevenlabs-api-key",
          "value": "your-elevenlabs-api-key-here"
        }
      ],
      "registries": [
        {
          "server": "$registryServer",
          "username": "$registryUsername",
          "passwordSecretRef": "registry-password"
        }
      ],
      "ingress": {
        "external": true,
        "targetPort": 8000,
        "allowInsecure": false,
        "traffic": [
          {
            "weight": 100,
            "latestRevision": true
          }
        ]
      }
    },
    "template": {
      "containers": [
        {
          "image": "$registryServer/voice-agent:$ImageTag",
          "name": "voice-agent",
          "resources": {
            "cpu": 1.0,
            "memory": "2Gi"
          },
          "env": [
            {
              "name": "LIVEKIT_API_KEY",
              "secretRef": "livekit-api-key"
            },
            {
              "name": "LIVEKIT_API_SECRET",
              "secretRef": "livekit-api-secret"
            },
            {
              "name": "DEEPGRAM_API_KEY",
              "secretRef": "deepgram-api-key"
            },
            {
              "name": "ELEVENLABS_API_KEY",
              "secretRef": "elevenlabs-api-key"
            },
            {
              "name": "PORT",
              "value": "8000"
            },
            {
              "name": "LOG_LEVEL",
              "value": "INFO"
            }
          ]
        }
      ],
      "scale": {
        "minReplicas": 1,
        "maxReplicas": 10,
        "rules": [
          {
            "name": "http-scaling",
            "http": {
              "metadata": {
                "concurrentRequests": "50"
              }
            }
          }
        ]
      }
    }
  }
}
"@
    
    # Save config to temp file
    $tempConfigFile = [System.IO.Path]::GetTempFileName() + ".json"
    $containerAppConfig | Set-Content -Path $tempConfigFile
    
    try {
        # Create the container app
        az containerapp create --name $AppName --resource-group $ResourceGroup --yaml $tempConfigFile --output none
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create container app"
        }
    } finally {
        # Clean up temp file
        if (Test-Path $tempConfigFile) {
            Remove-Item $tempConfigFile
        }
    }
    
    Write-Host "✅ Container app created" -ForegroundColor Green
    
    # Get the app URL
    Write-Host "Getting application URL..." -ForegroundColor Yellow
    $appUrl = az containerapp show --name $AppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    $fullUrl = "https://$appUrl"
    
    Write-Host ""
    Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Application Details:" -ForegroundColor Cyan
    Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
    Write-Host "  Container App: $AppName" -ForegroundColor White
    Write-Host "  Registry: $ContainerRegistry" -ForegroundColor White
    Write-Host "  URL: $fullUrl" -ForegroundColor White
    Write-Host ""
    Write-Host "Health Check: $fullUrl/health" -ForegroundColor Green
    Write-Host "API Docs: $fullUrl/docs" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Update the secrets with your actual API keys!" -ForegroundColor Red
    Write-Host "Use: az containerapp secret set --name $AppName --resource-group $ResourceGroup --secrets key=value" -ForegroundColor Yellow
    
} catch {
    Write-Error "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ☠️ Azure deployment failed: $_"
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "• Ensure Azure CLI is installed and updated" -ForegroundColor White
    Write-Host "• Verify you have sufficient Azure permissions" -ForegroundColor White
    Write-Host "• Check Azure subscription limits" -ForegroundColor White
    Write-Host "• Verify resource names are available and valid" -ForegroundColor White
    Write-Host "• Review Azure activity logs for detailed errors" -ForegroundColor White
    exit 1
}
#>