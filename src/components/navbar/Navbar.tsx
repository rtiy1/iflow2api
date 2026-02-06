import { LayoutDashboard, Users, Network, Activity, Settings } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { useConfigStore } from '../../stores/useConfigStore';

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { path: '/', label: '仪表盘', icon: LayoutDashboard },
  { path: '/accounts', label: '账号管理', icon: Users },
  { path: '/api-proxy', label: 'API 反代', icon: Network },
  { path: '/monitor', label: '流量日志', icon: Activity },
  { path: '/settings', label: '设置', icon: Settings },
];

function isActive(pathname: string, path: string): boolean {
  if (path === '/') {
    return pathname === '/';
  }
  return pathname.startsWith(path);
}

function Navbar() {
  const location = useLocation();
  const { config, saveConfig } = useConfigStore();

  const toggleTheme = () => {
    const newTheme = config?.theme === 'light' ? 'dark' : 'light';
    if (config) {
      saveConfig({ ...config, theme: newTheme });
    }
    document.documentElement.classList.toggle('dark');
  };

  return (
    <nav className="sticky top-0 z-50 bg-base-200 border-b border-base-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-16 gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg">⚡</span>
            </div>
            <span className="text-lg font-bold text-white">iFlow2API</span>
          </div>

          {/* Navigation Menu */}
          <div className="flex-1 flex justify-center">
            <nav className="flex items-center gap-1 bg-base-300 rounded-full p-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={() => `
                    px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap
                    ${isActive(location.pathname, item.path)
                      ? 'bg-gray-800 text-white shadow-sm dark:bg-white dark:text-gray-900'
                      : 'text-gray-400 hover:text-white hover:bg-base-200'
                    }
                  `}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-base-300 transition-colors"
            title="切换主题"
          >
            {config?.theme === 'light' ? (
              <span className="text-xl">🌙</span>
            ) : (
              <span className="text-xl">☀️</span>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
