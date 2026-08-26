import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard,
  FlaskConical,
  BarChart3,
  Settings,
  FileText,
  Layers,
  BookOpen,
  Brain,
  Network,
  Search,
  Activity,
} from 'lucide-react';
import clsx from 'clsx';
import { getEnvironment } from '../../api/client';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Experiments', href: '/experiments', icon: FlaskConical },
  { name: 'Models', href: '/models', icon: Search },
  { name: 'Knowledge Graph', href: '/knowledge-graph', icon: Network },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Scientist', href: '/scientist', icon: Brain },
  { name: 'Methods', href: '/methods', icon: Layers },
  { name: 'Reports', href: '/reports', icon: FileText },
];

const secondaryNav = [
  { name: 'Reproduction', href: '/reproduction', icon: FlaskConical },
  { name: 'Papers', href: '/papers', icon: BookOpen },
  { name: 'Health Check', href: '/health', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const { data: envInfo } = useQuery({
    queryKey: ['environment'],
    queryFn: getEnvironment,
    retry: 1,
    staleTime: 60_000,
  });

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-60 bg-white border-r border-[#e5e5e5] flex flex-col">
      {/* Branding */}
      <div className="px-6 py-6 border-b border-[#e5e5e5]">
        <h1 className="font-display text-xl tracking-wide text-black">
          LLM Quant Lab
        </h1>
        <p className="text-[10px] font-medium tracking-[0.2em] text-[#999] uppercase mt-1">
          Quantization Research
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col overflow-y-auto py-4">
        <div className="space-y-0.5">
          {navigation.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href));

            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-5 py-2.5 text-[11px] font-medium tracking-[0.1em] uppercase transition-all duration-200 border-l-2',
                  isActive
                    ? 'text-black border-l-black bg-[#f5f5f5]'
                    : 'text-[#666] hover:text-black hover:bg-[#f5f5f5] border-l-transparent'
                )}
              >
                <item.icon
                  className={clsx(
                    'w-4 h-4',
                    isActive ? 'text-black' : 'text-[#999]'
                  )}
                />
                {item.name}
              </Link>
            );
          })}
        </div>

        {/* Divider */}
        <div className="my-4 mx-5 border-t border-[#e5e5e5]" />

        {/* Secondary Navigation */}
        <div className="space-y-0.5">
          {secondaryNav.map((item) => {
            const isActive = location.pathname === item.href;

            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-5 py-2.5 text-[11px] font-medium tracking-[0.1em] uppercase transition-all duration-200 border-l-2',
                  isActive
                    ? 'text-black border-l-black bg-[#f5f5f5]'
                    : 'text-[#666] hover:text-black hover:bg-[#f5f5f5] border-l-transparent'
                )}
              >
                <item.icon
                  className={clsx(
                    'w-4 h-4',
                    isActive ? 'text-black' : 'text-[#999]'
                  )}
                />
                {item.name}
              </Link>
            );
          })}
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* System Status */}
        <div className="mx-4 mb-4 p-4 border border-[#e5e5e5] bg-[#fafafa]">
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                'w-2 h-2 rounded-full',
                envInfo ? 'bg-[#22c55e]' : 'bg-[#dc2626]'
              )}
            />
            <span className="text-[10px] font-semibold tracking-[0.15em] uppercase text-[#666]">
              {envInfo ? 'API Online' : 'API Offline'}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-[#999] truncate">
            {envInfo?.gpu_name ? `GPU: ${envInfo.gpu_name}` : 'GPU: N/A'}
            {envInfo?.gpu_count && envInfo.gpu_count > 0 && (
              <span className="text-[#ccc]"> &times;{envInfo.gpu_count}</span>
            )}
          </div>
          {envInfo?.rocm_version && (
            <div className="mt-1 text-[11px] text-[#999]">
              ROCm {envInfo.rocm_version.split('-')[0]}
            </div>
          )}
          {envInfo?.cuda_version && (
            <div className="mt-1 text-[11px] text-[#999]">
              CUDA {envInfo.cuda_version}
            </div>
          )}
        </div>
      </nav>
    </aside>
  );
}
