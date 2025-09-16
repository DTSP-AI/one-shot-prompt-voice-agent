'use client';

import { useState, useEffect } from 'react';
import { MCPConnector, ConnectorConfig, ConnectorHealthResponse } from './types';
import { useMCP } from './useMCP';
import MCPConfigForm from './MCPConfigForm';
import MCPTestPanel from './MCPTestPanel';

interface MCPConnectorEditorProps {
  connector: MCPConnector;
  onSave: (connector: MCPConnector) => void;
  onDelete: (connectorId: string) => void;
  onClose: () => void;
}

export default function MCPConnectorEditor({
  connector,
  onSave,
  onDelete,
  onClose
}: MCPConnectorEditorProps) {
  const { createOrUpdate, deleteConnector, checkHealth, loading } = useMCP();
  const [config, setConfig] = useState<ConnectorConfig>({});
  const [health, setHealth] = useState<ConnectorHealthResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setHealth(connector.last_health || null);
  }, [connector]);

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updatedConnector = await createOrUpdate(connector.id, config);
      setSuccess('Configuration saved successfully');
      onSave(updatedConnector);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete the "${connector.name}" connector?`)) {
      return;
    }

    setIsDeleting(true);
    setError(null);

    try {
      await deleteConnector(connector.id);
      onDelete(connector.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete connector');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleHealthCheck = async () => {
    setIsCheckingHealth(true);
    setError(null);

    try {
      const healthResult = await checkHealth(connector.id);
      setHealth(healthResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check health');
    } finally {
      setIsCheckingHealth(false);
    }
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

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white">
      <div className="flex justify-between items-start mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-2xl font-bold text-gray-900">{connector.name}</h2>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeColor(
                connector.status
              )}`}
            >
              {connector.status}
            </span>
          </div>
          <p className="text-gray-600">{connector.description}</p>
          <p className="text-sm text-gray-500 mt-1">Version: {connector.version}</p>
        </div>

        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
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

      {success && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <p className="text-sm text-green-800">{success}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div className="bg-gray-50 rounded-lg p-6">
            <MCPConfigForm
              schema={connector.required_config}
              initialConfig={{}}
              onConfigChange={setConfig}
              disabled={loading || isSaving}
            />

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleSave}
                disabled={isSaving || loading}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Saving...
                  </>
                ) : (
                  'Save Configuration'
                )}
              </button>

              <button
                onClick={handleHealthCheck}
                disabled={isCheckingHealth || !connector.configured}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCheckingHealth ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Checking...
                  </>
                ) : (
                  'Check Health'
                )}
              </button>

              <button
                onClick={handleDelete}
                disabled={isDeleting || loading}
                className="inline-flex items-center px-4 py-2 border border-red-300 text-sm font-medium rounded-md shadow-sm text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDeleting ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Deleting...
                  </>
                ) : (
                  'Delete'
                )}
              </button>
            </div>
          </div>

          {health && (
            <div className="bg-gray-50 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Health Status</h3>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700">Status:</span>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      health.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {health.success ? 'Healthy' : 'Unhealthy'}
                  </span>
                </div>

                {health.latency_ms && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">Latency:</span>
                    <span className="text-sm text-gray-900">{health.latency_ms}ms</span>
                  </div>
                )}

                {health.error && (
                  <div>
                    <span className="text-sm font-medium text-red-700 block mb-1">Error:</span>
                    <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
                      {health.error}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-6">
          <MCPTestPanel connector={connector} />
        </div>
      </div>
    </div>
  );
}