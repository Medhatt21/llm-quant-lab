import type { LucideIcon } from 'lucide-react';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: 'default' | 'quantum' | 'neural' | 'matrix';
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'default',
}: StatCardProps) {
  const accentColors = {
    default: 'border-l-[#e5e5e5]',
    quantum: 'border-l-black',
    neural: 'border-l-[#c5a47e]',
    matrix: 'border-l-[#666]',
  };

  return (
    <div
      className={clsx(
        'bg-white border border-[#e5e5e5] border-l-2 p-6 transition-all duration-300 hover:shadow-[0_2px_20px_rgba(0,0,0,0.06)]',
        accentColors[variant]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.15em] uppercase text-[#666]">
            {title}
          </p>
          <p className="mt-2 font-display text-4xl font-medium text-black">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {subtitle && (
            <p className="mt-1.5 text-[11px] text-[#999]">{subtitle}</p>
          )}
          {trend && (
            <div
              className={clsx(
                'mt-2 inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold',
                trend.isPositive ? 'text-[#22c55e]' : 'text-[#dc2626]'
              )}
            >
              <span>{trend.isPositive ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
            </div>
          )}
        </div>
        <div className="p-3 bg-[#f5f5f5]">
          <Icon className="w-5 h-5 text-[#999]" />
        </div>
      </div>
    </div>
  );
}
