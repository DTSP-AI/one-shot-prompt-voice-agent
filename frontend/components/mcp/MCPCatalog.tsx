'use client';

import { useState, useEffect } from 'react';
import { MCPConnector, MCPRegistryItem } from './types';
import { useMCP } from './useMCP';
import MCPConnectorEditor from './MCPConnectorEditor';

export default function MCPCatalog() {
  const { fetchCatalog, fetchRegistry, loading } = useMCP();
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [registry, setRegistry] = useState<MCPRegistryItem[]>([]);
  const [selectedConnector, setSelectedConnector] = useState<MCPConnector | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setError(null);
      const [catalogResponse, registryResponse] = await Promise.all([
        fetchCatalog(),
        fetchRegistry()
      ]);

      if (catalogResponse.success) {
        const sortedConnectors = catalogResponse.connectors.sort((a, b) => {
          const statusOrder = { enabled: 0, degraded: 1, disabled: 2, unconfigured: 3 };
          const aOrder = statusOrder[a.status] ?? 4;
          const bOrder = statusOrder[b.status] ?? 4;
          if (aOrder !== bOrder) return aOrder - bOrder;
          return a.name.localeCompare(b.name);
        });
        setConnectors(sortedConnectors);
      }

      if (registryResponse.success) {
        setRegistry(registryResponse.registry);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP data');
    }
  };

  const handleConnectorSelect = (connector: MCPConnector) => {
    setSelectedConnector(connector);
  };

  const handleConnectorSave = (updatedConnector: MCPConnector) => {
    setConnectors(prev =>
      prev.map(c => c.id === updatedConnector.id ? updatedConnector : c)
    );
    setSelectedConnector(updatedConnector);
  };

  const handleConnectorDelete = (connectorId: string) => {
    setConnectors(prev => prev.filter(c => c.id !== connectorId));
    setSelectedConnector(null);
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'enabled':
        return 'bg-green-100 text-green-800';
      case 'degraded':
        return 'bg-yellow-100 text-yellow-800';
      case 'disabled':
        return 'bg-gray-100 text-gray-800';
      case 'unconfigured':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'enabled':
        return (
          <svg className="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        );
      case 'degraded':
        return (
          <svg className="h-5 w-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        );
      case 'disabled':
        return (
          <svg className="h-5 w-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
          </svg>
        );
      case 'unconfigured':
        return (
          <svg className="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        );
      default:
        return null;
    }
  };

  if (selectedConnector) {
    return (
      <MCPConnectorEditor
        connector={selectedConnector}
        onSave={handleConnectorSave}
        onDelete={handleConnectorDelete}
        onClose={() => setSelectedConnector(null)}
      />
    );
  }

  if (loading && connectors.length === 0) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="flex items-center space-x-3">
          <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-lg text-gray-600">Loading MCP connectors...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">MCP Connectors</h1>
          <p className="text-gray-600 mt-2">
            Manage and configure your Model Context Protocol connectors
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {loading ? (
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : (
            <svg className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {connectors.map((connector) => (
          <div
            key={connector.id}
            className="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => handleConnectorSelect(connector)}
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(connector.status)}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {connector.name}
                    </h3>
                    <p className="text-sm text-gray-500">v{connector.version}</p>
                  </div>
                </div>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeColor(
                    connector.status
                  )}`}
                >
                  {connector.status}
                </span>
              </div>

              <p className="text-gray-600 text-sm mb-4 overflow-hidden h-10">
                {connector.description || 'No description available'}
              </p>

              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Configuration:</span>
                  <span className={connector.configured ? 'text-green-600' : 'text-red-600'}>
                    {connector.configured ? 'Configured' : 'Not configured'}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Actions:</span>
                  <span className="text-gray-900">
                    {connector.capabilities.actions.length}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Tools:</span>
                  <span className="text-gray-900">
                    {connector.capabilities.tools.length}
                  </span>
                </div>

                {connector.last_health && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Last Health:</span>
                    <span
                      className={
                        connector.last_health.success ? 'text-green-600' : 'text-red-600'
                      }
                    >
                      {connector.last_health.success ? 'Healthy' : 'Unhealthy'}
                      {connector.last_health.latency_ms && (
                        <span className="text-gray-500 ml-1">
                          ({connector.last_health.latency_ms}ms)
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <button className="w-full text-center text-sm text-blue-600 hover:text-blue-800 font-medium">
                  Configure & Test →
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {connectors.length === 0 && !loading && (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No connectors available</h3>
          <p className="mt-1 text-sm text-gray-500">
            There are no MCP connectors configured in the system.
          </p>
        </div>
      )}
    </div>
  );
}