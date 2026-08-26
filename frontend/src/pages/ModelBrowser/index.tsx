import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Download,
  Heart,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  Filter,
  Cpu,
  Tag,
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../../components/Layout/Header';
import { searchModels } from '../../api/client';
import type { ModelInfo } from '../../types';

export default function ModelBrowser() {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [compatibleOnly, setCompatibleOnly] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null);

  const handleSearch = (value: string) => {
    setSearchQuery(value);
    const timeout = setTimeout(() => setDebouncedQuery(value), 300);
    return () => clearTimeout(timeout);
  };

  const modelsQuery = useQuery({
    queryKey: ['models-search', debouncedQuery, compatibleOnly],
    queryFn: () => searchModels({ query: debouncedQuery || 'llama', limit: 30, compatible_only: compatibleOnly }),
    enabled: true,
  });

  const formatDownloads = (n: number): string => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return String(n);
  };

  return (
    <div className="min-h-screen">
      <Header title="Model Browser" subtitle="Search HuggingFace models with LightCompress compatibility" />
      <div className="p-6">
        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#999]" />
            <input
              type="text"
              placeholder="Search models (e.g. llama, opt-125m, mistral-7b)..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white border border-[#e5e5e5] text-black placeholder-[#999] focus:outline-none focus:border-black text-sm"
            />
          </div>
          <button
            onClick={() => setCompatibleOnly(!compatibleOnly)}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 border text-sm font-medium transition-all',
              compatibleOnly
                ? 'bg-[#2D8A4E]/10 border-[#2D8A4E]/30 text-[#2D8A4E]'
                : 'bg-white border-[#e5e5e5] text-[#666] hover:text-black'
            )}
          >
            <Filter className="w-4 h-4" />
            LightCompress Only
          </button>
        </div>

        {modelsQuery.isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-[#C5A47E]" />
            <span className="ml-3 text-[#999]">Searching HuggingFace...</span>
          </div>
        ) : modelsQuery.isError ? (
          <div className="text-center py-20">
            <p className="text-[#999]">Failed to search models. Is the API server running?</p>
            <p className="text-xs text-[#ccc] mt-2">{String(modelsQuery.error)}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {modelsQuery.data?.map((model) => (
              <div
                key={model.hf_id}
                onClick={() => setSelectedModel(model)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedModel(model); } }}
                aria-pressed={selectedModel?.hf_id === model.hf_id}
                className={clsx(
                  'p-4 cursor-pointer transition-all rounded-sm outline-none',
                  selectedModel?.hf_id === model.hf_id
                    ? 'bg-[#d4d4d4] border-2 border-black border-l-[6px] border-l-black shadow-[0_0_0_3px_rgba(0,0,0,0.25)]'
                    : 'bg-white border-2 border-[#e5e5e5] hover:border-[#999] hover:bg-[#f5f5f5]'
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-black truncate" title={model.hf_id}>
                      {model.hf_id}
                    </h3>
                    <p className="text-xs text-[#999] mt-0.5">{model.architecture}</p>
                  </div>
                  {model.is_llmc_compatible ? (
                    <div className="flex items-center gap-1 px-2 py-0.5 bg-[#2D8A4E]/10 border border-[#2D8A4E]/20">
                      <CheckCircle2 className="w-3 h-3 text-[#2D8A4E]" />
                      <span className="text-xs text-[#2D8A4E] font-medium">LC</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 px-2 py-0.5 bg-[#f5f5f5]">
                      <XCircle className="w-3 h-3 text-[#999]" />
                      <span className="text-xs text-[#999]">N/A</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-[#999]">
                  <div className="flex items-center gap-1">
                    <Download className="w-3.5 h-3.5" />
                    {formatDownloads(model.downloads)}
                  </div>
                  <div className="flex items-center gap-1">
                    <Heart className="w-3.5 h-3.5" />
                    {formatDownloads(model.likes)}
                  </div>
                  {model.size_category !== 'unknown' && (
                    <div className="flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5" />
                      {model.size_category}
                    </div>
                  )}
                </div>
                {model.llmc_type && (
                  <div className="mt-3 flex items-center gap-2">
                    <Tag className="w-3.5 h-3.5 text-[#C5A47E]" />
                    <span className="text-xs text-[#C5A47E] font-mono">LC type: {model.llmc_type}</span>
                  </div>
                )}
                {model.tags.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {model.tags.slice(0, 5).map((tag) => (
                      <span key={tag} className="px-2 py-0.5 bg-[#f5f5f5] text-xs text-[#999]">
                        {tag}
                      </span>
                    ))}
                    {model.tags.length > 5 && (
                      <span className="px-2 py-0.5 text-xs text-[#999]">+{model.tags.length - 5}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {modelsQuery.data?.length === 0 && !modelsQuery.isLoading && (
          <div className="text-center py-20">
            <Search className="w-12 h-12 text-[#ccc] mx-auto mb-4" />
            <p className="text-[#999]">No models found for &ldquo;{debouncedQuery}&rdquo;</p>
          </div>
        )}
      </div>

      {selectedModel && (
        <div className="fixed right-0 top-0 h-screen w-96 bg-white border-l border-[#e5e5e5] p-6 overflow-y-auto z-50 shadow-2xl">
          <div className="flex items-start justify-between mb-6">
            <h2 className="font-display font-bold text-black text-lg">{selectedModel.hf_id.split('/').pop()}</h2>
            <button onClick={() => setSelectedModel(null)} className="text-[#999] hover:text-black">
              <XCircle className="w-5 h-5" />
            </button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-[#999] uppercase tracking-wider">Full ID</label>
              <p className="text-sm text-black font-mono">{selectedModel.hf_id}</p>
            </div>
            <div>
              <label className="text-xs text-[#999] uppercase tracking-wider">Architecture</label>
              <p className="text-sm text-[#333]">{selectedModel.architecture}</p>
            </div>
            <div>
              <label className="text-xs text-[#999] uppercase tracking-wider">LightCompress Compatibility</label>
              <div className="mt-1">
                {selectedModel.is_llmc_compatible ? (
                  <div className="flex items-center gap-2 text-[#2D8A4E]">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-medium">Compatible (type: {selectedModel.llmc_type})</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-[#999]">
                    <XCircle className="w-5 h-5" />
                    <span className="text-sm">Not directly compatible</span>
                  </div>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-[#999] uppercase tracking-wider">Downloads</label>
                <p className="text-sm text-black font-semibold">{formatDownloads(selectedModel.downloads)}</p>
              </div>
              <div>
                <label className="text-xs text-[#999] uppercase tracking-wider">Likes</label>
                <p className="text-sm text-black font-semibold">{formatDownloads(selectedModel.likes)}</p>
              </div>
            </div>
            {selectedModel.pipeline_tag && (
              <div>
                <label className="text-xs text-[#999] uppercase tracking-wider">Pipeline</label>
                <p className="text-sm text-[#333]">{selectedModel.pipeline_tag}</p>
              </div>
            )}
            <div>
              <label className="text-xs text-[#999] uppercase tracking-wider">Tags</label>
              <div className="mt-1 flex flex-wrap gap-1">
                {selectedModel.tags.map((tag) => (
                  <span key={tag} className="px-2 py-0.5 bg-[#f5f5f5] text-xs text-[#666]">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div className="pt-4 border-t border-[#e5e5e5] space-y-2">
              <a
                href={`https://huggingface.co/${selectedModel.hf_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-white border border-[#e5e5e5] text-sm text-[#666] hover:text-black transition-colors w-full"
              >
                <ExternalLink className="w-4 h-4" />
                View on HuggingFace
              </a>
              {selectedModel.is_llmc_compatible && (
                <a
                  href={`/experiments/new?model=${encodeURIComponent(selectedModel.hf_id)}`}
                  className="flex items-center justify-center gap-2 px-4 py-2 bg-black hover:bg-[#333] text-sm text-white font-medium tracking-wide uppercase transition-colors w-full"
                >
                  Run Experiment
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
