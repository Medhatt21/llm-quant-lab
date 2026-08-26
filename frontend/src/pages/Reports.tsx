import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  FileText,
  Download,
  Eye,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
  Search,
  Link as LinkIcon,
} from 'lucide-react';
import clsx from 'clsx';
import { format, formatDistanceToNow } from 'date-fns';
import Header from '../components/Layout/Header';
import APIError from '../components/APIError';
import LoadingState from '../components/LoadingState';
import { getReports } from '../api/client';

interface Report {
  id: number;
  experiment_id: number;
  experiment_name?: string;
  model_name?: string;
  method?: string;
  pass_fail: 'pass' | 'fail' | 'inconclusive';
  confidence_score?: number;
  report_markdown?: string;
  summary?: string;
  key_findings: string[];
  created_at: string;
}

export default function Reports() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);

  const { data: apiData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: () => getReports({ limit: 50 }),
    retry: 2,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="AI Reports" subtitle="Research Intelligence" />
        <LoadingState message="Loading reports..." />
      </div>
    );
  }

  if (isError || !apiData) {
    return (
      <div className="min-h-screen">
        <Header title="AI Reports" subtitle="Research Intelligence" />
        <APIError title="Could not load reports" error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  const reports: Report[] = apiData.reports.map((r: any) => ({
    ...r,
    summary: r.summary || r.report_markdown?.slice(0, 150) || '',
    key_findings: r.key_findings || [],
    method: r.method || '',
  }));

  const filteredReports = reports.filter((report) => {
    const matchesSearch =
      (report.experiment_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (report.model_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !statusFilter || report.pass_fail === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen">
      <Header title="AI Reports" subtitle="Research Intelligence" />

      <div className="p-8">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
              <input
                type="text"
                placeholder="Search reports..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-80 pl-10 pr-4 py-2.5 bg-white border border-[#e5e5e5] text-[13px] text-[#333] placeholder-[#999] focus:outline-none focus:border-black transition-colors"
              />
            </div>
            <div className="flex items-center gap-1 border border-[#e5e5e5] p-1">
              {([null, 'pass', 'fail', 'inconclusive'] as const).map((val) => (
                <button
                  key={val ?? 'all'}
                  onClick={() => setStatusFilter(val)}
                  className={clsx(
                    'px-3 py-1.5 text-[11px] font-semibold tracking-[0.1em] uppercase transition-colors',
                    statusFilter === val
                      ? 'bg-black text-white'
                      : 'text-[#666] hover:text-black'
                  )}
                >
                  {val ? val.charAt(0).toUpperCase() + val.slice(1) : 'All'}
                </button>
              ))}
            </div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2.5 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-black text-[11px] font-semibold tracking-[0.1em] uppercase transition-colors">
            <Download className="w-4 h-4" /> Export All
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <MiniStat icon={FileText} label="Total Reports" value={reports.length} accent="black" />
          <MiniStat icon={CheckCircle2} label="Passed" value={reports.filter(r => r.pass_fail === 'pass').length} accent="green" />
          <MiniStat icon={XCircle} label="Failed" value={reports.filter(r => r.pass_fail === 'fail').length} accent="red" />
          <MiniStat icon={AlertCircle} label="Inconclusive" value={reports.filter(r => r.pass_fail === 'inconclusive').length} accent="gold" />
        </div>

        {reports.length === 0 && (
          <div className="bg-white border border-[#e5e5e5] py-16 text-center">
            <FileText className="w-12 h-12 text-[#e5e5e5] mx-auto mb-4" />
            <p className="font-display text-xl text-black mb-2">No Reports Yet</p>
            <p className="text-[11px] text-[#999]">Run an experiment and generate a scientist report to see results here.</p>
            <div className="gold-accent mx-auto mt-4" />
          </div>
        )}

        {reports.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Report List */}
            <div className="space-y-3">
              {filteredReports.map((report) => (
                <button
                  key={report.id}
                  onClick={() => setSelectedReport(report)}
                  className={clsx(
                    'w-full p-5 border text-left transition-all',
                    selectedReport?.id === report.id
                      ? 'bg-[#fafafa] border-black'
                      : 'bg-white border-[#e5e5e5] hover:border-[#999]'
                  )}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={clsx(
                        'p-2',
                        report.pass_fail === 'pass' && 'bg-[#f0fdf4]',
                        report.pass_fail === 'fail' && 'bg-[#fef2f2]',
                        report.pass_fail === 'inconclusive' && 'bg-[#faf6f0]'
                      )}>
                        {report.pass_fail === 'pass' && <CheckCircle2 className="w-4 h-4 text-[#22c55e]" />}
                        {report.pass_fail === 'fail' && <XCircle className="w-4 h-4 text-[#dc2626]" />}
                        {report.pass_fail === 'inconclusive' && <AlertCircle className="w-4 h-4 text-[#c5a47e]" />}
                      </div>
                      <div>
                        <h4 className="font-display text-base text-black">{report.experiment_name || `Experiment #${report.experiment_id}`}</h4>
                        <p className="text-[11px] text-[#999] font-mono">{report.model_name}</p>
                      </div>
                    </div>
                    <span className="text-[10px] text-[#999]">{formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}</span>
                  </div>
                  <p className="text-[13px] text-[#666] mb-3 line-clamp-2">{report.summary}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {report.method && <span className="px-2 py-0.5 bg-black text-white text-[9px] font-semibold tracking-[0.1em] uppercase">{report.method}</span>}
                      <span className="text-[10px] text-[#999]">{((report.confidence_score || 0) * 100).toFixed(0)}% confidence</span>
                    </div>
                    <Eye className="w-4 h-4 text-[#999]" />
                  </div>
                </button>
              ))}
              {filteredReports.length === 0 && reports.length > 0 && (
                <div className="text-center py-12">
                  <FileText className="w-10 h-10 text-[#e5e5e5] mx-auto mb-3" />
                  <p className="text-[#999] text-[11px] tracking-[0.1em] uppercase">No reports match your filters</p>
                </div>
              )}
            </div>

            {/* Report Detail Panel */}
            <div className="bg-white border border-[#e5e5e5] p-6 sticky top-20 self-start">
              {selectedReport ? (
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <Sparkles className="w-5 h-5 text-[#c5a47e]" />
                      <h3 className="font-display text-xl text-black">AI Analysis</h3>
                    </div>
                    <span className={clsx(
                      'px-3 py-1 text-[10px] font-semibold tracking-[0.1em] uppercase',
                      selectedReport.pass_fail === 'pass' && 'bg-[#f0fdf4] text-[#16a34a]',
                      selectedReport.pass_fail === 'fail' && 'bg-[#fef2f2] text-[#dc2626]',
                      selectedReport.pass_fail === 'inconclusive' && 'bg-[#faf6f0] text-[#c5a47e]'
                    )}>
                      {selectedReport.pass_fail.toUpperCase()}
                    </span>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <p className="stat-label mb-2">Summary</p>
                      <p className="text-[13px] text-black leading-relaxed">{selectedReport.summary}</p>
                    </div>

                    {selectedReport.report_markdown && (
                      <div>
                        <p className="stat-label mb-2">Full Report</p>
                        <div className="bg-[#fafafa] border border-[#e5e5e5] p-5 max-h-96 overflow-y-auto prose-luxury">
                          <div
                            className="text-[13px] text-[#333] whitespace-pre-wrap leading-relaxed"
                            dangerouslySetInnerHTML={{
                              __html: selectedReport.report_markdown
                                .replace(/^## (.+)$/gm, '<h3>$1</h3>')
                                .replace(/^### (.+)$/gm, '<h4>$1</h4>')
                                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                                .replace(/`(.+?)`/g, '<code>$1</code>')
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {selectedReport.key_findings.length > 0 && (
                      <div>
                        <p className="stat-label mb-3">Key Findings</p>
                        <div className="space-y-2">
                          {selectedReport.key_findings.map((finding, idx) => (
                            <div key={idx} className="flex items-center gap-3 p-3 bg-[#fafafa] border border-[#e5e5e5]">
                              <div className="w-6 h-6 bg-[#faf6f0] flex items-center justify-center flex-shrink-0">
                                <span className="font-display text-sm text-[#c5a47e]">{idx + 1}</span>
                              </div>
                              <span className="text-[13px] text-[#333]">{finding}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="pt-4 border-t border-[#e5e5e5]">
                      <div className="grid grid-cols-2 gap-4 text-[13px]">
                        <div>
                          <p className="text-[#999]">Experiment</p>
                          <Link to={`/experiments/${selectedReport.experiment_id}`} className="text-black hover:text-[#c5a47e] flex items-center gap-1 transition-colors">
                            {selectedReport.experiment_name || `#${selectedReport.experiment_id}`}
                            <LinkIcon className="w-3 h-3" />
                          </Link>
                        </div>
                        <div>
                          <p className="text-[#999]">Model</p>
                          <p className="text-black font-mono text-[11px]">{selectedReport.model_name}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-[#999]">Generated</p>
                          <p className="text-black">{format(new Date(selectedReport.created_at), 'PPpp')}</p>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <Link
                        to={`/experiments/${selectedReport.experiment_id}`}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-black hover:bg-[#1a1a1a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors"
                      >
                        <Eye className="w-4 h-4" /> View Experiment
                      </Link>
                      <button className="px-4 py-2.5 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-black transition-colors">
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-96 text-center">
                  <FileText className="w-12 h-12 text-[#e5e5e5] mb-4" />
                  <p className="font-display text-lg text-black mb-1">Select a Report</p>
                  <p className="text-[11px] text-[#999]">Choose a report from the list to view details</p>
                  <div className="gold-accent mt-4" />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MiniStat({ icon: Icon, label, value, accent }: { icon: typeof FileText; label: string; value: number; accent: 'black' | 'green' | 'red' | 'gold' }) {
  const borders = {
    black: 'border-l-black',
    green: 'border-l-[#22c55e]',
    red: 'border-l-[#dc2626]',
    gold: 'border-l-[#c5a47e]',
  };

  return (
    <div className={clsx('bg-white border border-[#e5e5e5] border-l-2 p-5', borders[accent])}>
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-[#999]" />
        <div>
          <p className="font-display text-2xl text-black">{value}</p>
          <p className="text-[10px] font-semibold tracking-[0.15em] uppercase text-[#666]">{label}</p>
        </div>
      </div>
    </div>
  );
}
