import { useState } from 'react';
import { Trash2, Search, Filter } from 'lucide-react';

interface LogEntry {
  id: string;
  time: string;
  method: string;
  path: string;
  status: number;
  model?: string;
  duration?: number;
}

function Monitor() {
  const [logs] = useState<LogEntry[]>([
    {
      id: '1',
      time: '14:30:25',
      method: 'POST',
      path: '/v1/chat/completions',
      status: 200,
      model: 'glm-4.7',
      duration: 1250,
    },
    {
      id: '2',
      time: '14:29:18',
      method: 'GET',
      path: '/v1/models',
      status: 200,
      duration: 45,
    },
    {
      id: '3',
      time: '14:28:42',
      method: 'POST',
      path: '/v1/messages',
      status: 200,
      model: 'claude-sonnet-4-5',
      duration: 2340,
    },
  ]);
  const [searchTerm, setSearchTerm] = useState('');

  const getStatusColor = (status: number) => {
    if (status < 300) return 'text-green-400';
    if (status < 400) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'GET':
        return 'text-blue-400';
      case 'POST':
        return 'text-green-400';
      case 'PUT':
        return 'text-yellow-400';
      case 'DELETE':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  const handleClearLogs = () => {
    if (confirm('确定要清空所有日志吗？')) {
      // Clear logs
    }
  };

  const filteredLogs = logs.filter(
    (log) =>
      log.path.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.model?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">流量日志</h1>
            <p className="text-gray-400 text-sm mt-1">查看和分析 API 请求日志</p>
          </div>
          <button
            onClick={handleClearLogs}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-sm font-medium transition-all"
          >
            <Trash2 className="w-4 h-4" />
            清空日志
          </button>
        </div>

        {/* Search and Filter */}
        <div className="flex gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="搜索路径或模型..."
              className="w-full pl-10 pr-4 py-2 bg-base-200 border border-base-300 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary text-sm"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-base-200 hover:bg-base-300 text-white rounded-lg text-sm transition-all">
            <Filter className="w-4 h-4" />
            筛选
          </button>
        </div>

        {/* Logs Table */}
        <div className="bg-base-200 rounded-xl border border-base-300 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-base-300/50 text-gray-400">
                <tr>
                  <th className="px-4 py-3 font-medium">时间</th>
                  <th className="px-4 py-3 font-medium">方法</th>
                  <th className="px-4 py-3 font-medium">路径</th>
                  <th className="px-4 py-3 font-medium">状态码</th>
                  <th className="px-4 py-3 font-medium">模型</th>
                  <th className="px-4 py-3 font-medium">耗时</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-base-300">
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      暂无日志记录
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-base-300/30 transition-colors"
                    >
                      <td className="px-4 py-3 text-gray-400">{log.time}</td>
                      <td className="px-4 py-3">
                        <span className={`font-mono ${getMethodColor(log.method)}`}>
                          {log.method}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-white font-mono text-xs">
                        {log.path}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-mono ${getStatusColor(log.status)}`}>
                          {log.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400">{log.model || '-'}</td>
                      <td className="px-4 py-3 text-gray-400">
                        {log.duration ? `${log.duration}ms` : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Monitor;
