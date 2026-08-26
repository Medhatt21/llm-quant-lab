import { useState } from 'react';
import { Search, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-[#e5e5e5]">
      <div className="flex items-center justify-between h-16 px-8">
        {/* Left: Title */}
        <div className="flex items-center gap-4">
          <div>
            {subtitle && (
              <p className="text-[10px] font-semibold tracking-[0.2em] uppercase text-[#999]">{subtitle}</p>
            )}
            <h1 className="font-display text-2xl tracking-wide text-black">
              {title}
            </h1>
          </div>
          <div className="gold-accent ml-2 mt-1" />
        </div>

        {/* Center: Search */}
        <div className="flex-1 max-w-xl mx-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
            <input
              type="text"
              placeholder="Search experiments, models, methods..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-[#e5e5e5] text-[13px] text-[#333] placeholder-[#999] focus:outline-none focus:border-black transition-colors"
            />
            <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] text-[#999] bg-[#f5f5f5] border border-[#e5e5e5] font-mono">
              /
            </kbd>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3">
          <Link
            to="/experiments/new"
            className="flex items-center gap-2 px-5 py-2.5 bg-black hover:bg-[#1a1a1a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors duration-300"
          >
            <Plus className="w-4 h-4" />
            New Experiment
          </Link>

          <button className="flex items-center gap-2 p-1 hover:bg-[#f5f5f5] transition-colors">
            <div className="w-8 h-8 bg-black flex items-center justify-center text-white text-[11px] font-semibold tracking-wider">
              U
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}
