import { useEffect } from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import ApiProxy from './pages/ApiProxy';
import Monitor from './pages/Monitor';
import Settings from './pages/Settings';
import { useConfigStore } from './stores/useConfigStore';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: 'accounts',
        element: <Accounts />,
      },
      {
        path: 'api-proxy',
        element: <ApiProxy />,
      },
      {
        path: 'monitor',
        element: <Monitor />,
      },
      {
        path: 'settings',
        element: <Settings />,
      },
    ],
  },
]);

function App() {
  const { loadConfig } = useConfigStore();

  useEffect(() => {
    // Load config on app start
    loadConfig();
  }, [loadConfig]);

  return <RouterProvider router={router} />;
}

export default App;
