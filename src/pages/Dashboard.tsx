import { useEffect, useState } from 'react';
import {
  Power,
  Activity,
  CheckCircle,
  Clock,
  Cpu,
  HardDrive,
  Play,
  Square,
  ExternalLink,
} from 'lucide-react';
import { useConfigStore } from '../stores/useConfigStore';

function Dashboard() {
  const { config, status, startService, stopService } = useConfigStore();
  const [stats, setStats] = useState({
    total: 0,
    success: 0,
    error: 0,
    successRate: 100,
  });
  const [systemInfo, setSystemInfo] = useState({
    cpu: 0,
    memory: 0,
    uptime: '00:00:00',
  });
  const [logs] = useState<string[]>([]);

  // Simulate system monitoring and stats
  useEffect(() => {
    const interval = setInterval(() => {
      setSystemInfo({
        cpu: Math.random() * 30 + 10,
        memory: Math.random() * 40 + 20,
        uptime: '00:12:34',
      });
      // Simulate stats update
      setStats(prev => ({
        ...prev,
        total: prev.total + Math.floor(Math.random() * 3),
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, [setStats]);

  const handleToggleService = async () => {
    if (status.running) {
      await stopService();
    } else {
      await startService(config?.port || 8000);
    }
  };

  const openAdminPanel = () => {
    window.open(`http://localhost:${status.port}/admin`, '_blank');
  };


  const StatusBadge = ({ running }: { running: boolean }) => (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
        running
          ? 'bg-green-500/20 text-green-400'
          : 'bg-red-500/20 text-red-400'
      }`}
    >
      {running ? (
        <>
          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
          运行中
        </>
      ) : (
        <>
          <span className="w-1.5 h-1.5 bg-red-400 rounded-full" />
          已停止
        </>
      )}
    </span>
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">仪表盘</h1>
          <p className="text-gray-400 text-sm mt-1">服务状态和系统概览</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Service Status */}
          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Power className="w-5 h-5 text-blue-400" />
              </div>
              <StatusBadge running={status.running} />
            </div>
            <div className="text-2xl font-bold text-white">
              {status.running ? `端口 ${status.port}` : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-1">服务状态</div>
          </div>

          {/* Total Requests */}
          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Activity className="w-5 h-5 text-purple-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-xs text-gray-500 mt-1">总请求数</div>
          </div>

          {/* Success Rate */}
          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-white">{stats.successRate}%</div>
            <div className="text-xs text-gray-500 mt-1">成功率</div>
          </div>

          {/* Uptime */}
          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-yellow-500/20 rounded-lg">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-white">{systemInfo.uptime}</div>
            <div className="text-xs text-gray-500 mt-1">运行时间</div>
          </div>
        </div>

        {/* System Resources */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-cyan-500/20 rounded-lg">
                <Cpu className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-cyan-400">
              {systemInfo.cpu.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-500 mt-1">CPU 使用率</div>
          </div>

          <div className="bg-base-200 rounded-xl p-5 border border-base-300">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-pink-500/20 rounded-lg">
                <HardDrive className="w-5 h-5 text-pink-400" />
              </div>
            </div>
            <div className="text-2xl font-bold text-pink-400">
              {systemInfo.memory.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-500 mt-1">内存使用率</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-base-200 rounded-xl p-5 border border-base-300">
          <h3 className="text-sm font-semibold text-white mb-4">快捷操作</h3>
          <div className="flex gap-3">
            <button
              onClick={handleToggleService}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                status.running
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : 'bg-primary hover:bg-primary/90 text-white'
              }`}
            >
              {status.running ? (
                <>
                  <Square className="w-4 h-4" />
                  停止服务
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  启动服务
                </>
              )}
            </button>

            <button
              onClick={openAdminPanel}
              disabled={!status.running}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm bg-base-300 hover:bg-base-300/80 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              <ExternalLink className="w-4 h-4" />
              打开管理面板
            </button>
          </div>
        </div>

        {/* Logs */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="px-5 py-3 border-b border-base-300 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">运行日志</h3>
            <button className="text-xs text-gray-400 hover:text-white transition-colors">
              清空日志
            </button>
          </div>
          <div className="p-4 h-48 overflow-y-auto font-mono text-xs">
            {logs.length === 0 ? (
              <div className="text-gray-500 text-center py-8">
                暂无日志
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="text-gray-400 py-0.5">
                  {log}
                </div>
              ))
            )}
            <div className="text-gray-500 py-0.5">
              [{new Date().toLocaleTimeString()}] INFO: Ready
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
