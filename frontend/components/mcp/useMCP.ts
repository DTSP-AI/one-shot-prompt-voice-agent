import { useState, useCallback } from 'react';
import {
  MCPConnector,
  MCPRegistryItem,
  ConnectorHealthResponse,
  TestResult,
  ConnectorConfig
} from './types';

export function useMCP() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApiCall = useCallback(async <T>(apiCall: () => Promise<Response>): Promise<T> => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall();
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCatalog = useCallback(async () => {
    return handleApiCall<{ success: boolean; connectors: MCPConnector[] }>(
      () => fetch('/api/v1/mcp/connectors')
    );
  }, [handleApiCall]);

  const fetchRegistry = useCallback(async () => {
    return handleApiCall<{ success: boolean; registry: MCPRegistryItem[] }>(
      () => fetch('/api/v1/mcp/registry')
    );
  }, [handleApiCall]);

  const createOrUpdate = useCallback(async (id: string, config: ConnectorConfig) => {
    return handleApiCall<MCPConnector>(
      () => fetch(`/api/v1/mcp/connectors/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config })
      })
    );
  }, [handleApiCall]);

  const deleteConnector = useCallback(async (id: string) => {
    return handleApiCall<{ success: boolean; message: string }>(
      () => fetch(`/api/v1/mcp/connectors/${id}`, { method: 'DELETE' })
    );
  }, [handleApiCall]);

  const checkHealth = useCallback(async (id: string) => {
    return handleApiCall<ConnectorHealthResponse>(
      () => fetch(`/api/v1/mcp/connectors/${id}/health`, { method: 'POST' })
    );
  }, [handleApiCall]);

  const testAction = useCallback(async (id: string, action: string, params: any = {}) => {
    return handleApiCall<TestResult>(
      () => fetch(`/api/v1/mcp/connectors/${id}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, params })
      })
    );
  }, [handleApiCall]);

  const getConnectorTools = useCallback(async (id: string) => {
    return handleApiCall<{ success: boolean; tools: any[] }>(
      () => fetch(`/api/v1/mcp/connectors/${id}/tools`)
    );
  }, [handleApiCall]);

  return {
    loading,
    error,
    fetchCatalog,
    fetchRegistry,
    createOrUpdate,
    deleteConnector,
    checkHealth,
    testAction,
    getConnectorTools
  };
}