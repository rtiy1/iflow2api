import { useState, useEffect } from 'react';
import {
  Globe,
  Moon,
  Trash2,
  Info,
  Github,
} from 'lucide-react';
import { useConfigStore } from '../stores/useConfigStore';

function Settings() {
  const { config, saveConfig, loadConfig } = useConfigStore();
  const [cacheSize, setCacheSize] = useState('0 MB');

  useEffect(() => {
    loadConfig();
  }, []);

  const handleLanguageChange = (lang: string) => {
    if (config) {
      saveConfig({ ...config, language: lang });
    }
  };

  const handleClearCache = () => {
    if (confirm('确定要清除缓存吗？')) {
      localStorage.removeItem('iflow2api_logs');
      setCacheSize('0 MB');
      alert('缓存已清除');
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">设置</h1>
          <p className="text-gray-400 text-sm mt-1">管理应用偏好和系统选项</p>
        </div>

        {/* Appearance */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Moon className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">外观</h3>
                <p className="text-xs text-gray-400">自定义界面主题和显示</p>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-4">
            {/* Theme */}
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-white">深色模式</div>
                <div className="text-xs text-gray-500">使用深色主题保护眼睛</div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config?.theme === 'dark'}
                  onChange={(e) => {
                    if (config) {
                      saveConfig({ ...config, theme: e.target.checked ? 'dark' : 'light' });
                      document.documentElement.classList.toggle('dark');
                    }
                  }}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-base-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>
          </div>
        </div>

        {/* Language */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Globe className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">语言</h3>
                <p className="text-xs text-gray-400">选择界面显示语言</p>
              </div>
            </div>
          </div>

          <div className="p-6">
            <select
              value={config?.language || 'zh-CN'}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="w-full max-w-xs px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white focus:outline-none focus:border-primary text-sm"
            >
              <option value="zh-CN">简体中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>

        {/* Cache Management */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <Trash2 className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">缓存管理</h3>
                <p className="text-xs text-gray-400">清除本地缓存数据</p>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-white">本地缓存</div>
                <div className="text-xs text-gray-500">缓存大小: {cacheSize}</div>
              </div>
              <button
                onClick={handleClearCache}
                className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-sm font-medium transition-all"
              >
                <Trash2 className="w-4 h-4" />
                清除缓存
              </button>
            </div>
          </div>
        </div>

        {/* About */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-500/20 rounded-lg">
                <Info className="w-5 h-5 text-gray-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">关于</h3>
                <p className="text-xs text-gray-400">应用信息和版本</p>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">版本</span>
              <span className="text-sm text-white">v1.0.0</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">构建时间</span>
              <span className="text-sm text-white">2025-02-06</span>
            </div>
            <div className="pt-4 border-t border-base-300">
              <a
                href="https://github.com/yourusername/iflow2api"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors"
              >
                <Github className="w-4 h-4" />
                GitHub 仓库
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
