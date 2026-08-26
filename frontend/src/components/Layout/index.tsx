import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TaskBar from './TaskBar';

export default function Layout() {
  return (
    <div className="min-h-screen bg-white">
      <Sidebar />
      <main className="pl-60 pb-12">
        <Outlet />
      </main>
      <TaskBar />
    </div>
  );
}
