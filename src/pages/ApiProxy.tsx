import { useState, useEffect } from 'react';
import {
  Settings,
  Cpu,
  Save,
  RotateCcw,
} from 'lucide-react';
import { useConfigStore } from '../stores/useConfigStore';

interface CollapsibleCardProps {
  title: string;
  icon: React.ReactNode;
  enabled?: boolean;
  onToggle?: (enabled: boolean) => void;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

function CollapsibleCard({
  title,
  icon,
  enabled,
  onToggle,
  children,
  defaultExpanded = false,
}: CollapsibleCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden transition-all duration-200 hover:border-base-300/80">
      <div
        className="px-5 py-4 flex items-center justify-between cursor-pointer bg-base-200/50 hover:bg-base-300/30 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="text-gray-400">{icon}</div>
          <span className="font-medium text-sm text-white">{title}</span>
          {enabled !== undefined && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                enabled
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-gray-500/20 text-gray-400'
              }`}
            >
              {enabled ? '已启用' : '已禁用'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-4">
          {enabled !== undefined && onToggle && (
            <div onClick={(e) => e.stopPropagation()}>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => onToggle(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-base-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>
          )}

          <button
            className={`p-1 rounded-lg hover:bg-base-300 transition-all duration-200 ${
              isExpanded ? 'rotate-180' : ''
            }`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-gray-400"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      <div
        className={`transition-all duration-300 ease-in-out border-t border-base-300 ${
          isExpanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden'
        }`}
      >
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function ApiProxy() {
  const { config, status, startService, stopService, saveConfig } = useConfigStore();
  const [localConfig, setLocalConfig] = useState({
    port: 8000,
    baseUrl: 'https://apis.iflow.cn/v1',
    retry: 3,
    timeout: 60,
  });

  // Load config on mount
  useEffect(() => {
    if (config) {
      setLocalConfig({
        port: config.port,
        baseUrl: config.baseUrl,
        retry: config.retry,
        timeout: config.timeout,
      });
    }
  }, [config]);

  const handleServiceToggle = async (enabled: boolean) => {
    if (enabled) {
      await startService(localConfig.port);
    } else {
      await stopService();
    }
  };

  const handleSaveConfig = () => {
    if (config) {
      saveConfig({
        ...config,
        ...localConfig,
      });
    }
    alert('配置已保存');
  };

  const handleResetConfig = () => {
    setLocalConfig({
      port: 8000,
      baseUrl: 'https://apis.iflow.cn/v1',
      retry: 3,
      timeout: 60,
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">API 反代</h1>
          <p className="text-gray-400 text-sm mt-1">配置代理服务和连接设置</p>
        </div>

        {/* Basic Settings Card */}
        <CollapsibleCard
          title="基本设置"
          icon={<Settings className="w-5 h-5" />}
          enabled={status.running}
          onToggle={handleServiceToggle}
          defaultExpanded={true}
        >
          <div className="space-y-4">
            {/* Port Setting */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                监听端口
                <span className="text-xs text-gray-500 ml-2">范围: 1024-65535</span>
              </label>
              <input
                type="number"
                value={localConfig.port}
                onChange={(e) =>
                  setLocalConfig({ ...localConfig, port: parseInt(e.target.value) })
                }
                min={1024}
                max={65535}
                disabled={status.running}
                className="w-full max-w-xs px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white focus:outline-none focus:border-primary text-sm disabled:opacity-50"
              />
            </div>

            {/* Base URL */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">上游 API 地址</label>
              <input
                type="text"
                value={localConfig.baseUrl}
                onChange={(e) =>
                  setLocalConfig({ ...localConfig, baseUrl: e.target.value })
                }
                placeholder="https://apis.iflow.cn/v1"
                className="w-full px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white focus:outline-none focus:border-primary text-sm"
              />
            </div>
          </div>
        </CollapsibleCard>

        {/* Advanced Settings Card */}
        <CollapsibleCard
          title="高级设置"
          icon={<Cpu className="w-5 h-5" />}
          defaultExpanded={false}
        >
          <div className="space-y-4">
            {/* Retry Count */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                重试次数
                <span className="text-xs text-gray-500 ml-2">请求失败时的自动重试次数</span>
              </label>
              <input
                type="number"
                value={localConfig.retry}
                onChange={(e) =>
                  setLocalConfig({ ...localConfig, retry: parseInt(e.target.value) })
                }
                min={0}
                max={10}
                className="w-full max-w-xs px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white focus:outline-none focus:border-primary text-sm"
              />
            </div>

            {/* Timeout */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                超时时间 (秒)
              </label>
              <input
                type="number"
                value={localConfig.timeout}
                onChange={(e) =>
                  setLocalConfig({ ...localConfig, timeout: parseInt(e.target.value) })
                }
                min={10}
                max={300}
                className="w-full max-w-xs px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white focus:outline-none focus:border-primary text-sm"
              />
            </div>
          </div>
        </CollapsibleCard>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handleSaveConfig}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-all"
          >
            <Save className="w-4 h-4" />
            保存配置
          </button>

          <button
            onClick={handleResetConfig}
            className="flex items-center gap-2 px-5 py-2.5 bg-base-300 hover:bg-base-300/80 text-white rounded-lg text-sm font-medium transition-all"
          >
            <RotateCcw className="w-4 h-4" />
            重置默认
          </button>
        </div>
      </div>
    </div>
  );
}

export default ApiProxy;
