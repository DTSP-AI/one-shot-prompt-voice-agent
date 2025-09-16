export interface MCPConnector {
  id: string;
  name: string;
  version: string;
  description?: string;
  status: 'enabled' | 'disabled' | 'degraded' | 'unconfigured';
  configured: boolean;
  required_config: string[];
  capabilities: {
    actions: string[];
    tools: string[];
  };
  last_health?: {
    success: boolean;
    status: string;
    latency_ms?: number;
    error?: string;
  };
}

export interface MCPRegistryItem {
  id: string;
  name: string;
  version: string;
  description?: string;
  required_config: string[];
  capabilities: {
    actions: string[];
    tools: string[];
  };
}

export interface ConnectorHealthResponse {
  success: boolean;
  status: string;
  latency_ms?: number;
  error?: string;
}

export interface ConnectorsListResponse {
  success: boolean;
  connectors: MCPConnector[];
}

export interface RegistryListResponse {
  success: boolean;
  registry: MCPRegistryItem[];
}

export interface TestResult {
  success: boolean;
  connector_id: string;
  action: string;
  result?: any;
  error?: string;
  execution_time_ms?: number;
}

export interface ConnectorConfig {
  [key: string]: string;
}