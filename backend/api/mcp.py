from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
import logging

from services.mcp_service import MCPService

logger = logging.getLogger(__name__)
router = APIRouter()

class McpConnector(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str] = None
    status: str  # 'enabled', 'disabled', 'degraded', 'unconfigured'
    configured: bool
    required_config: List[str]
    capabilities: Dict[str, List[str]]
    last_health: Optional[Dict[str, Any]] = None

class McpRegistryItem(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str] = None
    required_config: List[str]
    capabilities: Dict[str, List[str]]

class ConnectorHealthResponse(BaseModel):
    success: bool
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None

class ConnectorsListResponse(BaseModel):
    success: bool
    connectors: List[McpConnector]

class RegistryListResponse(BaseModel):
    success: bool
    registry: List[McpRegistryItem]

# Global MCP service instance
mcp_service = MCPService()

@router.get("/connectors", response_model=ConnectorsListResponse)
async def list_connectors():
    """List all available MCP connectors with their status"""
    try:
        connectors = await mcp_service.list_connectors()

        formatted_connectors = []
        for connector_data in connectors:
            connector = McpConnector(
                id=connector_data.get("id"),
                name=connector_data.get("name"),
                version=connector_data.get("version", "1.0.0"),
                description=connector_data.get("description"),
                status=connector_data.get("status", "unconfigured"),
                configured=connector_data.get("configured", False),
                required_config=connector_data.get("required_config", []),
                capabilities=connector_data.get("capabilities", {"actions": [], "tools": []}),
                last_health=connector_data.get("last_health")
            )
            formatted_connectors.append(connector)

        return ConnectorsListResponse(
            success=True,
            connectors=formatted_connectors
        )

    except Exception as e:
        logger.error(f"Failed to list MCP connectors: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list connectors: {str(e)}")

@router.post("/connectors", response_model=McpConnector)
async def create_connector(
    connector_id: str,
    config: Dict[str, Any]
):
    """Create and configure a new MCP connector"""
    try:
        connector_data = await mcp_service.create_connector(connector_id, config)

        return McpConnector(**connector_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create MCP connector: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create connector: {str(e)}")

@router.patch("/connectors/{connector_id}", response_model=McpConnector)
async def update_connector(
    connector_id: str,
    enabled: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None
):
    """Update MCP connector configuration or status"""
    try:
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if config is not None:
            updates["config"] = config

        if not updates:
            raise ValueError("No updates provided")

        connector_data = await mcp_service.update_connector(connector_id, updates)

        return McpConnector(**connector_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update MCP connector {connector_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update connector: {str(e)}")

@router.post("/connectors/{connector_id}/health", response_model=ConnectorHealthResponse)
async def check_connector_health(connector_id: str):
    """Check the health status of a specific MCP connector"""
    try:
        health_result = await mcp_service.check_connector_health(connector_id)

        return ConnectorHealthResponse(
            success=health_result.get("ok", False),
            status=health_result.get("status", "unknown"),
            latency_ms=health_result.get("latency_ms"),
            error=health_result.get("error")
        )

    except Exception as e:
        logger.error(f"Failed to check health for connector {connector_id}: {e}")
        return ConnectorHealthResponse(
            success=False,
            status="error",
            error=str(e)
        )

@router.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: str,
    test_action: str,
    test_params: Optional[Dict[str, Any]] = None
):
    """Test a specific action/tool of an MCP connector"""
    try:
        test_result = await mcp_service.test_connector_action(
            connector_id,
            test_action,
            test_params or {}
        )

        return {
            "success": test_result.get("success", False),
            "connector_id": connector_id,
            "action": test_action,
            "result": test_result.get("result"),
            "error": test_result.get("error"),
            "execution_time_ms": test_result.get("execution_time_ms")
        }

    except Exception as e:
        logger.error(f"Failed to test connector {connector_id} action {test_action}: {e}")
        return {
            "success": False,
            "connector_id": connector_id,
            "action": test_action,
            "error": str(e)
        }

@router.get("/registry", response_model=RegistryListResponse)
async def get_mcp_registry():
    """Get the registry of available MCP connectors"""
    try:
        registry_items = await mcp_service.get_registry()

        formatted_items = []
        for item_data in registry_items:
            item = McpRegistryItem(
                id=item_data.get("id"),
                name=item_data.get("name"),
                version=item_data.get("version", "1.0.0"),
                description=item_data.get("description"),
                required_config=item_data.get("required_config", []),
                capabilities=item_data.get("capabilities", {"actions": [], "tools": []})
            )
            formatted_items.append(item)

        return RegistryListResponse(
            success=True,
            registry=formatted_items
        )

    except Exception as e:
        logger.error(f"Failed to get MCP registry: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get registry: {str(e)}")

@router.delete("/connectors/{connector_id}")
async def delete_connector(connector_id: str):
    """Delete an MCP connector"""
    try:
        success = await mcp_service.delete_connector(connector_id)

        if success:
            return {
                "success": True,
                "connector_id": connector_id,
                "message": "Connector deleted successfully"
            }
        else:
            return {
                "success": False,
                "connector_id": connector_id,
                "message": "Connector not found or deletion failed"
            }

    except Exception as e:
        logger.error(f"Failed to delete connector {connector_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete connector: {str(e)}")

@router.get("/connectors/{connector_id}/tools")
async def get_connector_tools(connector_id: str):
    """Get available tools for a specific connector"""
    try:
        tools = await mcp_service.get_connector_tools(connector_id)

        return {
            "success": True,
            "connector_id": connector_id,
            "tools": tools
        }

    except Exception as e:
        logger.error(f"Failed to get tools for connector {connector_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get connector tools: {str(e)}")