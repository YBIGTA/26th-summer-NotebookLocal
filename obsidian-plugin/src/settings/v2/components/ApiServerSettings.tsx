import React, { useState } from "react";
import { getSettings, updateSetting } from "@/settings/model";
import { useAtomValue } from "jotai";
import { settingsAtom } from "@/settings/model";
import { SettingItem } from "@/components/ui/setting-item";
import { SettingSwitch } from "@/components/ui/setting-switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient, updateApiClientSettings } from "@/api/ApiClient";

export default function ApiServerSettings() {
  const settings = useAtomValue(settingsAtom);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionMessage, setConnectionMessage] = useState<string>('');

  const handleServerUrlChange = (value: string) => {
    updateSetting("serverUrl", value);
    updateApiClientSettings();
  };

  const handleUseApiServerChange = (value: boolean) => {
    updateSetting("useApiServer", value);
    if (value) {
      updateApiClientSettings();
    }
  };

  const handleStreamingChange = (value: boolean) => {
    updateSetting("enableStreaming", value);
  };

  const testConnection = async () => {
    setConnectionStatus('testing');
    setConnectionMessage('Testing connection...');
    
    try {
      updateApiClientSettings(); // Make sure we're using the latest URL
      const isConnected = await apiClient.testConnection();
      
      if (isConnected) {
        setConnectionStatus('success');
        setConnectionMessage('✅ Connected successfully!');
        
        // Also test if we can get index status
        try {
          const indexStatus = await apiClient.getIndexStatus();
          setConnectionMessage(`✅ Connected! Found ${indexStatus.total_documents} documents, ${indexStatus.total_chunks} chunks.`);
        } catch (e) {
          setConnectionMessage('✅ Connected to server, but RAG endpoints may not be available.');
        }
      } else {
        setConnectionStatus('error');
        setConnectionMessage('❌ Cannot connect to server. Check the URL and make sure your FastAPI server is running.');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionMessage(`❌ Connection failed: ${error.message}`);
    }
    
    // Clear message after 5 seconds
    setTimeout(() => {
      setConnectionStatus('idle');
      setConnectionMessage('');
    }, 5000);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">API Server Configuration</h3>
      <p className="text-sm text-muted-foreground">
        Configure the plugin to use an external FastAPI RAG server instead of built-in processing.
        This provides better performance, Korean PDF support, and modular architecture.
      </p>

      <SettingItem
        name="Use API Server"
        description="Enable API server mode to route all processing to your FastAPI RAG server"
      >
        <SettingSwitch
          value={settings.useApiServer}
          onChange={handleUseApiServerChange}
        />
      </SettingItem>

      {settings.useApiServer && (
        <>
          <SettingItem
            name="Server URL"
            description="The base URL of your FastAPI RAG server (e.g., http://localhost:8000)"
          >
            <div className="flex gap-2 items-center">
              <Input
                value={settings.serverUrl}
                onChange={(e) => handleServerUrlChange(e.target.value)}
                placeholder="http://localhost:8000"
                className="flex-1"
              />
              <Button
                onClick={testConnection}
                disabled={connectionStatus === 'testing'}
                size="sm"
                variant="outline"
              >
                {connectionStatus === 'testing' ? 'Testing...' : 'Test'}
              </Button>
            </div>
            {connectionMessage && (
              <div className={`text-sm mt-2 ${
                connectionStatus === 'success' ? 'text-green-600' : 
                connectionStatus === 'error' ? 'text-red-600' : 
                'text-blue-600'
              }`}>
                {connectionMessage}
              </div>
            )}
          </SettingItem>

          <SettingItem
            name="Enable Streaming"
            description="Enable real-time streaming responses from the server (recommended)"
          >
            <SettingSwitch
              value={settings.enableStreaming}
              onChange={handleStreamingChange}
            />
          </SettingItem>

          <div className="bg-blue-50 dark:bg-blue-950/20 p-4 rounded-lg">
            <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-2">
              🚀 Server Setup Instructions
            </h4>
            <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
              <p>1. Make sure your FastAPI RAG server is running:</p>
              <code className="bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded text-xs">
                uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
              </code>
              <p>2. Upload PDFs to the server to build your knowledge base</p>
              <p>3. Test the connection above to verify everything is working</p>
              <p>4. The plugin will now route all Q&A through your server!</p>
            </div>
          </div>

          {!settings.useApiServer && (
            <div className="bg-amber-50 dark:bg-amber-950/20 p-4 rounded-lg">
              <h4 className="font-semibold text-amber-800 dark:text-amber-200 mb-2">
                ⚠️ Local Processing Mode
              </h4>
              <p className="text-sm text-amber-700 dark:text-amber-300">
                Currently using built-in processing. Enable API Server mode above to use your FastAPI RAG server 
                with Korean PDF support and improved performance.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}