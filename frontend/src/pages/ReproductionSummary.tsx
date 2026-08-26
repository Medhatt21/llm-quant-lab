import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getReproductionSummary } from '../api/client';
import type { ReproductionSummaryData } from '../api/client';
import Header from '../components/Layout/Header';
import LoadingState from '../components/LoadingState';

type Comparison = NonNullable<ReproductionSummaryData['comparisons']>[number];

function VerdictBadge({ verdict }: { verdict: string }) {
  const cls =
    verdict === 'matching' ? 'bg-green-100 text-green-800' :
    verdict === 'close' ? 'bg-yellow-100 text-yellow-800' :
    verdict === 'better' ? 'bg-green-200 text-green-900' :
    verdict === 'worse' ? 'bg-red-100 text-red-800' :
    'bg-gray-100 text-gray-500';
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{verdict}</span>;
}

function FilterSelect({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

export default function ReproductionSummary() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['reproduction-summary', 'v2'],
    queryFn: () => getReproductionSummary({ v2Only: true }),
    refetchInterval: 30_000,
  });

  const [metricFilter, setMetricFilter] = useState('');
  const [methodFilter, setMethodFilter] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('');
  const [paperFilter, setPaperFilter] = useState('');
  const [datasetFilter, setDatasetFilter] = useState('');
  const [showNoRef, setShowNoRef] = useState(true);

  const comparisons = data?.comparisons ?? [];
  const experiments = data?.experiments ?? [];

  const filterOptions = useMemo(() => {
    const metrics = new Set<string>();
    const methods = new Set<string>();
    const verdicts = new Set<string>();
    const papers = new Set<string>();
    const datasets = new Set<string>();
    for (const c of comparisons) {
      if (c.metric) metrics.add(c.metric);
      if (c.method) methods.add(c.method);
      if (c.verdict) verdicts.add(c.verdict);
      if (c.paper_id) papers.add(c.paper_id);
      if (c.dataset) datasets.add(c.dataset);
    }
    return {
      metrics: [...metrics].sort(),
      methods: [...methods].sort(),
      verdicts: [...verdicts].sort(),
      papers: [...papers].sort(),
      datasets: [...datasets].sort(),
    };
  }, [comparisons]);

  const filtered = useMemo(() => {
    return comparisons.filter((c) => {
      if (metricFilter && c.metric !== metricFilter) return false;
      if (methodFilter && c.method !== methodFilter) return false;
      if (verdictFilter && c.verdict !== verdictFilter) return false;
      if (paperFilter && c.paper_id !== paperFilter) return false;
      if (datasetFilter && c.dataset !== datasetFilter) return false;
      if (!showNoRef && c.verdict === 'no_paper_ref') return false;
      return true;
    });
  }, [comparisons, metricFilter, methodFilter, verdictFilter, paperFilter, datasetFilter, showNoRef]);

  const filteredVerdicts = useMemo(() => {
    const counts = { matching: 0, close: 0, better: 0, worse: 0, no_paper_ref: 0 };
    for (const c of filtered) {
      const v = c.verdict as keyof typeof counts;
      if (v in counts) counts[v]++;
    }
    return counts;
  }, [filtered]);

  const hasActiveFilter = !!(metricFilter || methodFilter || verdictFilter || paperFilter || datasetFilter);

  if (isLoading) return <LoadingState message="Loading reproduction summary..." />;
  if (error) {
    return (
      <div>
        <Header title="Reproduction Summary" />
        <div className="p-6 text-red-600">
          Failed to load reproduction data. Make sure the API is running.
        </div>
      </div>
    );
  }

  const statusCounts = data?.status_counts ?? {};
  const total = statusCounts.total ?? 0;
  const completed = statusCounts.completed ?? 0;
  const failed = statusCounts.failed ?? 0;
  const running = statusCounts.running ?? 0;
  const pending = statusCounts.pending ?? 0;

  const v2Min = data?.reproduction_v2_min_id;

  return (
    <div>
      <Header title="Reproduction summary (v2)" />
      <p className="px-6 pt-2 text-sm text-gray-600">
        Showing experiments from reproduction v2: tag <code className="bg-gray-100 px-1 rounded">reproduction-v2</code>
        {v2Min != null ? (
          <> or experiment id ≥ <code className="bg-gray-100 px-1 rounded">{v2Min}</code></>
        ) : null}
        .
      </p>

      <div className="p-6 space-y-6">
        {/* Status cards */}
        <section>
          <h2 className="text-lg font-semibold text-black mb-3">Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-gray-100 rounded-lg p-3">
              <div className="text-2xl font-bold text-black">{total}</div>
              <div className="text-sm text-gray-600">Total</div>
            </div>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="text-2xl font-bold text-green-700">{completed}</div>
              <div className="text-sm text-gray-600">Completed</div>
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <div className="text-2xl font-bold text-red-700">{failed}</div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="text-2xl font-bold text-blue-700">{running}</div>
              <div className="text-sm text-gray-600">Running</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-2xl font-bold text-gray-700">{pending}</div>
              <div className="text-sm text-gray-600">Pending</div>
            </div>
          </div>
        </section>

        {/* Verdict summary — recomputed from filtered comparisons */}
        <section>
          <h2 className="text-lg font-semibold text-black mb-3">
            Verdicts
            {hasActiveFilter && <span className="ml-2 text-xs font-normal text-gray-500">(filtered)</span>}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {([
              { key: 'matching', label: 'Matching', border: 'border-gray-200', bg: '', text: 'text-black' },
              { key: 'close', label: 'Close', border: 'border-yellow-200', bg: 'bg-yellow-50', text: 'text-yellow-700' },
              { key: 'better', label: 'Better', border: 'border-green-200', bg: 'bg-green-50', text: 'text-green-700' },
              { key: 'worse', label: 'Worse', border: 'border-red-200', bg: 'bg-red-50', text: 'text-red-700' },
              { key: 'no_paper_ref', label: 'No Paper Ref', border: 'border-gray-200', bg: 'bg-gray-50', text: 'text-gray-500' },
            ] as const).map(({ key, label, border, bg, text }) => (
              <button
                key={key}
                onClick={() => setVerdictFilter(verdictFilter === key ? '' : key)}
                className={`rounded-lg p-3 border ${border} ${bg} text-left transition-shadow ${
                  verdictFilter === key ? 'ring-2 ring-indigo-500 shadow-md' : 'hover:shadow-sm'
                }`}
              >
                <div className={`text-xl font-bold ${text}`}>
                  {filteredVerdicts[key]}
                </div>
                <div className="text-sm text-gray-600">{label}</div>
              </button>
            ))}
          </div>
        </section>

        {/* Filters */}
        <section className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <div className="flex flex-wrap items-end gap-4">
            <FilterSelect label="Metric" value={metricFilter} options={filterOptions.metrics} onChange={setMetricFilter} />
            <FilterSelect label="Method" value={methodFilter} options={filterOptions.methods} onChange={setMethodFilter} />
            <FilterSelect label="Dataset" value={datasetFilter} options={filterOptions.datasets} onChange={setDatasetFilter} />
            <FilterSelect label="Paper" value={paperFilter} options={filterOptions.papers} onChange={setPaperFilter} />
            <FilterSelect label="Verdict" value={verdictFilter} options={filterOptions.verdicts} onChange={setVerdictFilter} />
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">No-ref rows</label>
              <button
                onClick={() => setShowNoRef(!showNoRef)}
                className={`border rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  showNoRef
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                    : 'bg-white border-gray-300 text-gray-500'
                }`}
              >
                {showNoRef ? 'Showing' : 'Hidden'}
              </button>
            </div>
            {hasActiveFilter && (
              <button
                onClick={() => { setMetricFilter(''); setMethodFilter(''); setVerdictFilter(''); setPaperFilter(''); setDatasetFilter(''); }}
                className="text-xs text-indigo-600 hover:text-indigo-800 underline self-end pb-2"
              >
                Clear all filters
              </button>
            )}
          </div>
        </section>

        {/* Comparisons table */}
        <section>
          <h2 className="text-lg font-semibold text-black mb-3">
            Comparisons ({filtered.length}
            {hasActiveFilter && <span className="text-gray-500 font-normal"> of {comparisons.length}</span>})
          </h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">ID</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Model</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Method</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-600">Bits</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Dataset</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Metric</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600">Paper</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600">Ours</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-600">Diff %</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Verdict</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filtered.slice(0, 200).map((c: Comparison, i: number) => (
                  <tr key={i} className={c.verdict === 'no_paper_ref' ? 'bg-gray-50/50' : ''}>
                    <td className="px-4 py-2 text-sm text-gray-900 font-mono">{c.experiment_id}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 max-w-[200px] truncate" title={c.model}>
                      {c.model?.split('/').pop() ?? ''}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900">{c.method ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 text-center">{(c as any).bit_width ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{c.dataset}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{c.metric}</td>
                    <td className="px-4 py-2 text-sm text-right text-gray-900">
                      {c.paper_value != null ? c.paper_value.toFixed(2) : '—'}
                    </td>
                    <td className="px-4 py-2 text-sm text-right text-gray-900 font-medium">
                      {c.our_value != null ? (c.our_value > 10000 ? c.our_value.toExponential(2) : c.our_value.toFixed(4)) : '—'}
                    </td>
                    <td className="px-4 py-2 text-sm text-right text-gray-900">
                      {c.diff_pct != null ? `${c.diff_pct > 0 ? '+' : ''}${c.diff_pct.toFixed(2)}%` : '—'}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <VerdictBadge verdict={c.verdict} />
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-500">
                      No comparisons match the selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {filtered.length > 200 && (
              <div className="px-4 py-2 text-sm text-gray-500 bg-gray-50">
                Showing 200 of {filtered.length} comparisons
              </div>
            )}
          </div>
        </section>

        {/* Experiments table */}
        <section>
          <h2 className="text-lg font-semibold text-black mb-3">Experiments ({experiments.length})</h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">ID</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Model</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Method</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-600">Bits</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Paper</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">Status</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-600">Metrics</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-600">W&B</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {experiments.map((e) => (
                  <tr key={e.id}>
                    <td className="px-4 py-2 text-sm text-gray-900 font-mono">{e.id}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 max-w-[200px] truncate" title={e.model}>
                      {e.model?.split('/').pop() ?? e.name ?? ''}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900">{e.method ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 text-center">{(e as any).bit_width ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{e.paper_id ?? '—'}</td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        e.status === 'completed' ? 'bg-green-100 text-green-800' :
                        e.status === 'failed' ? 'bg-red-100 text-red-800' :
                        e.status === 'running' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {e.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900 text-center">{e.metric_count}</td>
                    <td className="px-4 py-2 text-sm">
                      {e.wandb_url ? (
                        <a href={e.wandb_url} target="_blank" rel="noopener noreferrer"
                          className="text-indigo-600 hover:text-indigo-800 underline text-xs">
                          view
                        </a>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
