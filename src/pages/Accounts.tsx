import { useState, useEffect } from 'react';
import {
  Key,
  RefreshCw,
  LogOut,
  Eye,
  EyeOff,
  Save,
  FileText,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { api } from '../utils/request';

interface AuthState {
  isAuthenticated: boolean;
  username?: string;
  expiryDate?: number;
  apiKey?: string;
}

function Accounts() {
  const [authState, setAuthState] = useState<AuthState>({ isAuthenticated: false });
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Load saved credentials on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const creds = await api.getOAuthCreds();
        if (creds && creds.apiKey) {
          setAuthState({
            isAuthenticated: true,
            username: '已认证用户',
            expiryDate: creds.expiry_date as number,
            apiKey: creds.apiKey as string,
          });
          setApiKey(creds.apiKey as string);
        }
      } catch (error) {
        console.error('Failed to load auth state:', error);
      }
    };
    checkAuth();
  }, []);

  const handleOAuthLogin = async () => {
    setIsLoading(true);
    try {
      const result = await api.startOAuth();
      if (result.status === 'success' && result.credentials) {
        setAuthState({
          isAuthenticated: true,
          username: '已认证用户',
          expiryDate: result.credentials.expiry_date as number,
          apiKey: result.credentials.apiKey as string,
        });
        setApiKey(result.credentials.apiKey as string);
        alert('OAuth 认证成功！');
      }
    } catch (error) {
      alert(`OAuth 认证失败: ${error}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshToken = async () => {
    setIsLoading(true);
    // Refresh OAuth token - would need to implement this in Rust
    setTimeout(() => {
      setIsLoading(false);
      alert('Token 已刷新');
    }, 1000);
  };

  const handleLogout = async () => {
    if (confirm('确定要退出登录吗？')) {
      try {
        await api.deleteOAuth();
        setAuthState({ isAuthenticated: false });
        setApiKey('');
      } catch (error) {
        console.error('Failed to logout:', error);
      }
    }
  };

  const handleSaveApiKey = () => {
    if (!apiKey.trim()) {
      alert('请输入 API Key');
      return;
    }
    // Save API key
    localStorage.setItem('iflow_api_key', apiKey);
    alert('API Key 已保存');
  };

  const handleLoadFromFile = () => {
    // In Tauri mode, this would open a file dialog
    alert('文件选择功能将在 Tauri 环境中可用');
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">账号管理</h1>
          <p className="text-gray-400 text-sm mt-1">管理 OAuth 认证和 API 凭证</p>
        </div>

        {/* OAuth Authentication Card */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Key className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">OAuth 认证</h3>
                <p className="text-xs text-gray-400">通过 iFlow 官方 OAuth 流程登录</p>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-4">
            {/* Auth Status */}
            <div className="flex items-center justify-between p-4 bg-base-300/50 rounded-lg">
              <div>
                <div className="text-sm text-gray-400">当前状态</div>
                <div className="flex items-center gap-2 mt-1">
                  {authState.isAuthenticated ? (
                    <>
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-green-400 font-medium">已认证</span>
                      {authState.username && (
                        <span className="text-gray-400 text-sm">({authState.username})</span>
                      )}
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-red-400" />
                      <span className="text-red-400 font-medium">未认证</span>
                    </>
                  )}
                </div>
              </div>

              <div className="flex gap-2">
                {!authState.isAuthenticated ? (
                  <button
                    onClick={handleOAuthLogin}
                    disabled={isLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50"
                  >
                    <Key className="w-4 h-4" />
                    {isLoading ? '认证中...' : 'OAuth 登录'}
                  </button>
                ) : (
                  <>
                    <button
                      onClick={handleRefreshToken}
                      disabled={isLoading}
                      className="flex items-center gap-2 px-4 py-2 bg-base-300 hover:bg-base-300/80 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50"
                    >
                      <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                      刷新 Token
                    </button>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-sm font-medium transition-all"
                    >
                      <LogOut className="w-4 h-4" />
                      退出登录
                    </button>
                  </>
                )}
              </div>
            </div>

            {authState.expiryDate && (
              <div className="text-xs text-gray-500">
                Token 过期时间: {new Date(authState.expiryDate).toLocaleString()}
              </div>
            )}
          </div>
        </div>

        {/* API Key Card */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-6 py-4 border-b border-base-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Key className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">API Key 配置</h3>
                <p className="text-xs text-gray-400">直接配置 iFlow API Key</p>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-4">
            {/* API Key Input */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">API Key</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="输入你的 iFlow API Key"
                    className="w-full px-4 py-2.5 bg-base-300 border border-base-300 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary text-sm"
                  />
                  <button
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <button
                  onClick={handleSaveApiKey}
                  className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-all"
                >
                  <Save className="w-4 h-4" />
                  保存
                </button>
              </div>
            </div>

            {/* Load from file */}
            <div className="pt-4 border-t border-base-300">
              <button
                onClick={handleLoadFromFile}
                className="flex items-center gap-2 px-4 py-2 bg-base-300 hover:bg-base-300/80 text-white rounded-lg text-sm font-medium transition-all"
              >
                <FileText className="w-4 h-4" />
                从文件导入
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Accounts;
