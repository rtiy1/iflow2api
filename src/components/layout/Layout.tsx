import { Outlet } from 'react-router-dom';
import Navbar from '../navbar/Navbar';

function Layout() {
  return (
    <div className="h-screen flex flex-col bg-base-100">
      <Navbar />
      <main className="flex-1 overflow-hidden flex flex-col relative">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
