'use client';

import { useState, useEffect } from 'react';
import { ConnectorConfig } from './types';

interface MCPConfigFormProps {
  schema: string[];
  initialConfig?: ConnectorConfig;
  onConfigChange: (config: ConnectorConfig) => void;
  disabled?: boolean;
}

export default function MCPConfigForm({
  schema,
  initialConfig = {},
  onConfigChange,
  disabled = false
}: MCPConfigFormProps) {
  const [config, setConfig] = useState<ConnectorConfig>(initialConfig);
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    onConfigChange(config);
  }, [config, onConfigChange]);

  const isSecretField = (fieldName: string) => {
    const secretFields = ['password', 'api_key', 'secret', 'token', 'key'];
    return secretFields.some(secret => fieldName.toLowerCase().includes(secret));
  };

  const handleInputChange = (field: string, value: string) => {
    const newConfig = { ...config, [field]: value };
    setConfig(newConfig);
  };

  const toggleSecretVisibility = (field: string) => {
    setShowSecrets(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
  };

  const formatFieldLabel = (fieldName: string) => {
    return fieldName
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (!schema || schema.length === 0) {
    return (
      <div className="text-gray-500 text-sm">
        No configuration required for this connector.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-900">Configuration</h3>

      {schema.map((field) => {
        const isSecret = isSecretField(field);
        const showValue = !isSecret || showSecrets[field];

        return (
          <div key={field} className="space-y-2">
            <label
              htmlFor={field}
              className="block text-sm font-medium text-gray-700"
            >
              {formatFieldLabel(field)}
              {isSecret && (
                <span className="ml-1 text-xs text-orange-600">(secure)</span>
              )}
            </label>

            <div className="relative">
              <input
                id={field}
                type={showValue ? 'text' : 'password'}
                value={config[field] || ''}
                onChange={(e) => handleInputChange(field, e.target.value)}
                disabled={disabled}
                placeholder={`Enter ${formatFieldLabel(field).toLowerCase()}`}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              />

              {isSecret && (
                <button
                  type="button"
                  onClick={() => toggleSecretVisibility(field)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                  disabled={disabled}
                >
                  {showValue ? (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                    </svg>
                  )}
                </button>
              )}
            </div>

            {isSecret && config[field] && (
              <p className="text-xs text-gray-500">
                {showValue ? 'Value visible' : 'Value hidden for security'}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}