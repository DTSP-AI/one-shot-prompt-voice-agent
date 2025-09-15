import asyncio
import json
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

class MCPService:
    """
    MCP (Model Context Protocol) Service for managing connector catalog
    Provides pluggable tool connector interface
    """

    def __init__(self):
        self._connectors: Dict[str, Dict[str, Any]] = {}
        self._registry: List[Dict[str, Any]] = []
        self._initialize_built_in_registry()

    def _initialize_built_in_registry(self):
        """Initialize built-in connector registry"""
        self._registry = [
            {
                "id": "web-search",
                "name": "Web Search",
                "version": "1.0.0",
                "description": "Search the web for information using various search engines",
                "required_config": ["search_api_key", "search_engine_id"],
                "capabilities": {
                    "actions": ["search", "summarize"],
                    "tools": ["google_search", "bing_search", "duckduckgo_search"]
                }
            },
            {
                "id": "file-system",
                "name": "File System",
                "version": "1.0.0",
                "description": "Read, write, and manage files and directories",
                "required_config": ["base_path", "allowed_extensions"],
                "capabilities": {
                    "actions": ["read", "write", "list", "delete"],
                    "tools": ["read_file", "write_file", "list_directory"]
                }
            },
            {
                "id": "github-integration",
                "name": "GitHub Integration",
                "version": "1.0.0",
                "description": "Integrate with GitHub repositories and APIs",
                "required_config": ["github_token", "organization"],
                "capabilities": {
                    "actions": ["list_repos", "create_issue", "get_pr"],
                    "tools": ["github_api", "webhook_handler"]
                }
            },
            {
                "id": "database-query",
                "name": "Database Query",
                "version": "1.0.0",
                "description": "Execute queries against various databases",
                "required_config": ["connection_string", "query_timeout"],
                "capabilities": {
                    "actions": ["query", "insert", "update", "delete"],
                    "tools": ["sql_executor", "schema_inspector"]
                }
            },
            {
                "id": "email-sender",
                "name": "Email Sender",
                "version": "1.0.0",
                "description": "Send emails via SMTP or email service APIs",
                "required_config": ["smtp_server", "smtp_port", "username", "password"],
                "capabilities": {
                    "actions": ["send_email", "send_template"],
                    "tools": ["smtp_client", "template_engine"]
                }
            }
        ]

    async def get_registry(self) -> List[Dict[str, Any]]:
        """Get the registry of available MCP connectors"""
        return self._registry.copy()

    async def list_connectors(self) -> List[Dict[str, Any]]:
        """List all configured MCP connectors with their status"""
        connector_list = []

        for connector_id, connector_data in self._connectors.items():
            # Find registry entry for additional info
            registry_entry = next(
                (item for item in self._registry if item["id"] == connector_id),
                {}
            )

            connector_info = {
                "id": connector_id,
                "name": connector_data.get("name", registry_entry.get("name", "Unknown")),
                "version": connector_data.get("version", registry_entry.get("version", "1.0.0")),
                "description": registry_entry.get("description"),
                "status": connector_data.get("status", "unconfigured"),
                "configured": connector_data.get("configured", False),
                "required_config": registry_entry.get("required_config", []),
                "capabilities": registry_entry.get("capabilities", {"actions": [], "tools": []}),
                "last_health": connector_data.get("last_health"),
                "config": {k: "***" for k in connector_data.get("config", {})} # Redact secrets
            }
            connector_list.append(connector_info)

        # Add unconfigured registry items
        for registry_item in self._registry:
            if registry_item["id"] not in self._connectors:
                connector_list.append({
                    **registry_item,
                    "status": "unconfigured",
                    "configured": False,
                    "last_health": None
                })

        return connector_list

    async def create_connector(self, connector_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create and configure a new MCP connector"""
        # Validate connector exists in registry
        registry_entry = next(
            (item for item in self._registry if item["id"] == connector_id),
            None
        )

        if not registry_entry:
            raise ValueError(f"Connector '{connector_id}' not found in registry")

        # Validate required configuration
        required_config = registry_entry.get("required_config", [])
        missing_config = [key for key in required_config if key not in config]

        if missing_config:
            raise ValueError(f"Missing required configuration: {missing_config}")

        # Create connector entry
        connector_data = {
            "id": connector_id,
            "name": registry_entry["name"],
            "version": registry_entry["version"],
            "config": config.copy(),
            "status": "enabled" if self._validate_config(connector_id, config) else "degraded",
            "configured": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store connector (in production, this would be in database)
        self._connectors[connector_id] = connector_data

        logger.info(f"Created MCP connector '{connector_id}' with status '{connector_data['status']}'")

        # Return connector info without secrets
        return await self._format_connector_response(connector_id)

    async def update_connector(self, connector_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update MCP connector configuration or status"""
        if connector_id not in self._connectors:
            raise ValueError(f"Connector '{connector_id}' not found")

        connector_data = self._connectors[connector_id]

        # Update configuration
        if "config" in updates:
            connector_data["config"].update(updates["config"])
            connector_data["status"] = "enabled" if self._validate_config(connector_id, connector_data["config"]) else "degraded"

        # Update enabled status
        if "enabled" in updates:
            if updates["enabled"]:
                connector_data["status"] = "enabled" if self._validate_config(connector_id, connector_data["config"]) else "degraded"
            else:
                connector_data["status"] = "disabled"

        connector_data["updated_at"] = datetime.utcnow().isoformat()

        logger.info(f"Updated MCP connector '{connector_id}' with status '{connector_data['status']}'")

        return await self._format_connector_response(connector_id)

    async def check_connector_health(self, connector_id: str) -> Dict[str, Any]:
        """Check the health status of a specific MCP connector"""
        if connector_id not in self._connectors:
            return {
                "ok": False,
                "status": "not_found",
                "error": f"Connector '{connector_id}' not found"
            }

        connector_data = self._connectors[connector_id]
        start_time = datetime.now()

        try:
            # Simulate health check (in production, this would test actual connectivity)
            await asyncio.sleep(0.1)  # Simulate network call

            status = connector_data.get("status", "unknown")
            is_healthy = status == "enabled"

            latency = (datetime.now() - start_time).total_seconds() * 1000

            health_result = {
                "ok": is_healthy,
                "status": "healthy" if is_healthy else status,
                "latency_ms": round(latency, 2),
                "checked_at": datetime.utcnow().isoformat()
            }

            # Update last health check
            connector_data["last_health"] = health_result

            logger.debug(f"Health check for connector '{connector_id}': {health_result['status']}")

            return health_result

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            error_result = {
                "ok": False,
                "status": "error",
                "latency_ms": round(latency, 2),
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

            connector_data["last_health"] = error_result
            logger.error(f"Health check failed for connector '{connector_id}': {e}")

            return error_result

    async def test_connector_action(
        self,
        connector_id: str,
        action: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a specific action of an MCP connector"""
        if connector_id not in self._connectors:
            return {
                "success": False,
                "error": f"Connector '{connector_id}' not found"
            }

        connector_data = self._connectors[connector_id]

        if connector_data.get("status") != "enabled":
            return {
                "success": False,
                "error": f"Connector '{connector_id}' is not enabled"
            }

        start_time = datetime.now()

        try:
            # Simulate action execution (in production, this would call actual connector)
            await asyncio.sleep(0.2)  # Simulate processing time

            # Execute actual connector action (this would invoke the real MCP protocol)
            if connector_id not in self._connectors:
                raise ValueError(f"Connector '{connector_id}' not found or not enabled")

            connector = self._connectors[connector_id]

            # In a real implementation, this would:
            # 1. Establish WebSocket/stdio connection to MCP server
            # 2. Send JSON-RPC request with action and parameters
            # 3. Parse and return the actual response
            # For now, return a success indicator that action would be executed

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "result": {"message": f"Action '{action}' would be executed via MCP protocol for connector '{connector['name']}'"},
                "execution_time_ms": round(execution_time, 2)
            }

            logger.info(f"Test action '{action}' succeeded for connector '{connector_id}'")
            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_result = {
                "success": False,
                "error": str(e),
                "execution_time_ms": round(execution_time, 2)
            }

            logger.error(f"Test action '{action}' failed for connector '{connector_id}': {e}")
            return error_result

    async def delete_connector(self, connector_id: str) -> bool:
        """Delete an MCP connector"""
        if connector_id in self._connectors:
            del self._connectors[connector_id]
            logger.info(f"Deleted MCP connector '{connector_id}'")
            return True
        return False

    async def get_connector_tools(self, connector_id: str) -> List[Dict[str, Any]]:
        """Get available tools for a specific connector"""
        registry_entry = next(
            (item for item in self._registry if item["id"] == connector_id),
            None
        )

        if not registry_entry:
            return []

        # Return detailed tool information
        tools = []
        for tool_name in registry_entry.get("capabilities", {}).get("tools", []):
            tools.append({
                "name": tool_name,
                "connector_id": connector_id,
                "description": f"Tool {tool_name} from {registry_entry['name']} connector",
                "parameters": self._get_tool_parameters(tool_name),
                "available": connector_id in self._connectors and self._connectors[connector_id].get("status") == "enabled"
            })

        return tools

    def _validate_config(self, connector_id: str, config: Dict[str, Any]) -> bool:
        """Validate connector configuration"""
        registry_entry = next(
            (item for item in self._registry if item["id"] == connector_id),
            None
        )

        if not registry_entry:
            return False

        # Check that all required config keys are present and not empty
        required_config = registry_entry.get("required_config", [])
        for key in required_config:
            if key not in config or not config[key]:
                return False

        return True

    async def _format_connector_response(self, connector_id: str) -> Dict[str, Any]:
        """Format connector data for API response (without secrets)"""
        connector_data = self._connectors[connector_id]
        registry_entry = next(
            (item for item in self._registry if item["id"] == connector_id),
            {}
        )

        return {
            "id": connector_id,
            "name": connector_data["name"],
            "version": connector_data["version"],
            "description": registry_entry.get("description"),
            "status": connector_data["status"],
            "configured": connector_data["configured"],
            "required_config": registry_entry.get("required_config", []),
            "capabilities": registry_entry.get("capabilities", {"actions": [], "tools": []}),
            "last_health": connector_data.get("last_health"),
            "created_at": connector_data.get("created_at"),
            "updated_at": connector_data.get("updated_at")
        }

    def _get_tool_parameters(self, tool_name: str) -> Dict[str, Any]:
        """Get tool parameters (in production, this would query the MCP server for schemas)"""
        # Common parameter schemas based on tool types
        # In real implementation, these would be retrieved from MCP server tool schemas
        parameter_schemas = {
            "google_search": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            },
            "read_file": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file to read"},
                    "encoding": {"type": "string", "default": "utf-8"}
                },
                "required": ["file_path"]
            },
            "write_file": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to write file"},
                    "content": {"type": "string", "description": "File content"},
                    "overwrite": {"type": "boolean", "default": False}
                },
                "required": ["file_path", "content"]
            }
        }

        return parameter_schemas.get(tool_name, {"type": "object", "description": "Tool parameters"})