'use client';

import { useState } from 'react';
import { MCPConnector, TestResult } from './types';
import { useMCP } from './useMCP';

interface MCPTestPanelProps {
  connector: MCPConnector;
}

export default function MCPTestPanel({ connector }: MCPTestPanelProps) {
  const { testAction, loading } = useMCP();
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [testParams, setTestParams] = useState<string>('{}');
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const availableActions = [
    ...connector.capabilities.actions,
    ...connector.capabilities.tools
  ];

  const handleTest = async () => {
    if (!selectedAction) {
      setError('Please select an action to test');
      return;
    }

    setError(null);
    setTestResult(null);

    try {
      let params = {};
      if (testParams.trim()) {
        params = JSON.parse(testParams);
      }

      const result = await testAction(connector.id, selectedAction, params);
      setTestResult(result);
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError('Invalid JSON in test parameters');
      } else {
        setError(err instanceof Error ? err.message : 'Test failed');
      }
    }
  };

  const formatJson = (obj: any) => {
    try {
      return JSON.stringify(obj, null, 2);
    } catch {
      return String(obj);
    }
  };

  if (!connector.configured) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800 text-sm">
          This connector must be configured before testing actions.
        </p>
      </div>
    );
  }

  if (availableActions.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-gray-600 text-sm">
          No actions or tools available for this connector.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-900">Test Actions</h3>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Action
          </label>
          <select
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          >
            <option value="">Choose an action...</option>
            {availableActions.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Test Parameters (JSON)
          </label>
          <textarea
            value={testParams}
            onChange={(e) => setTestParams(e.target.value)}
            placeholder='{"key": "value"}'
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
            disabled={loading}
          />
          <p className="text-xs text-gray-500 mt-1">
            Enter parameters as JSON. Leave empty for no parameters.
          </p>
        </div>

        <button
          onClick={handleTest}
          disabled={loading || !selectedAction}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Testing...
            </>
          ) : (
            'Run Test'
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
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

      {testResult && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h4 className="text-md font-medium text-gray-900 mb-3">Test Result</h4>

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">Status:</span>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  testResult.success
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {testResult.success ? 'Success' : 'Failed'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">Action:</span>
              <span className="text-sm text-gray-900 font-mono">{testResult.action}</span>
            </div>

            {testResult.execution_time_ms && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-700">Execution Time:</span>
                <span className="text-sm text-gray-900">{testResult.execution_time_ms}ms</span>
              </div>
            )}

            {testResult.error && (
              <div>
                <span className="text-sm font-medium text-red-700 block mb-1">Error:</span>
                <pre className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800 overflow-x-auto">
                  {testResult.error}
                </pre>
              </div>
            )}

            {testResult.result && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">Result:</span>
                <pre className="bg-white border border-gray-200 rounded p-3 text-sm text-gray-900 overflow-x-auto max-h-60 overflow-y-auto">
                  {formatJson(testResult.result)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}