import { useQuery } from '@tanstack/react-query';
import {
  FileText,
  BookOpen,
  ExternalLink,
  Download,
  Search,
  Tag,
  Calendar,
  Users,
  FlaskConical,
} from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';
import Header from '../components/Layout/Header';
import LoadingState from '../components/LoadingState';
import { getPapers, getPaperReproductionSpecs, type PaperReproductionSpec } from '../api/client';

interface PaperNote {
  id?: string;
  paper_id?: string;
  title?: string;
  core_idea?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  arxiv_id?: string;
  method_names?: string[];
  tags?: string[];
}

export default function Papers() {
  const [searchQuery, setSearchQuery] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['papers'],
    queryFn: getPapers,
    retry: 2,
  });

  const { data: reproductionData } = useQuery({
    queryKey: ['papers-reproduction'],
    queryFn: getPaperReproductionSpecs,
    retry: 1,
  });
  const reproductionSpecs: PaperReproductionSpec[] = reproductionData?.specs ?? [];

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Papers & Literature" subtitle="Quantization research papers and notes" />
        <LoadingState message="Loading papers..." />
      </div>
    );
  }

  const papers = data?.papers ?? [];
  const notes = data?.notes ?? [];

  const filteredPapers = papers.filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredNotes = notes.filter((n) =>
    (n.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (n.core_idea || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (n.method_names || []).some((m: string) => m.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="min-h-screen">
      <Header title="Papers & Literature" subtitle="Quantization research papers and notes" />

      <div className="p-6 space-y-6">
        {/* Search */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
            <input
              type="text"
              placeholder="Search papers, methods..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-sm text-black placeholder-gray-400 focus:outline-none focus:border-black"
            />
          </div>
          <div className="text-sm text-[#999]">
            {papers.length} PDFs &middot; {notes.length} notes
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border-0 border border-[#e5e5e5] p-5 shadow-none">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[#f5f5f5]">
                <FileText className="w-5 h-5 text-black" />
              </div>
              <div>
                <p className="text-2xl font-bold text-black">{papers.length}</p>
                <p className="text-xs text-[#999]">PDF Papers</p>
              </div>
            </div>
          </div>
          <div className="bg-white border-0 border border-[#e5e5e5] p-5 shadow-none">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[#f5f5f5]">
                <BookOpen className="w-5 h-5 text-[#C5A47E]" />
              </div>
              <div>
                <p className="text-2xl font-bold text-black">{notes.length}</p>
                <p className="text-xs text-[#999]">Structured Notes</p>
              </div>
            </div>
          </div>
          <div className="bg-white border-0 border border-[#e5e5e5] p-5 shadow-none">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[#f5f5f5]">
                <Tag className="w-5 h-5 text-[#666]" />
              </div>
              <div>
                <p className="text-2xl font-bold text-black">
                  {new Set(notes.flatMap((n: PaperNote) => n.method_names || [])).size}
                </p>
                <p className="text-xs text-[#999]">Methods Covered</p>
              </div>
            </div>
          </div>
        </div>

        {/* Exact reproduction guide: one guide per paper with model, settings, and paper results */}
        <div>
          <h3 className="text-lg font-semibold text-black mb-2 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-[#C5A47E]" />
            Exact reproduction guide
          </h3>
          <p className="text-sm text-[#666] mb-4">
            One guide per paper: pick the <strong>model</strong>, set the <strong>hyperparameters</strong>, run the experiment, then compare your metric to the <strong>paper result</strong> below.
          </p>

          {reproductionSpecs.length === 0 ? (
            <div className="bg-white border border-[#e5e5e5] p-6 text-center text-[#666] text-sm">
              Reproduction specs load from the API. If the server is running, ensure <code className="font-mono bg-[#f5f5f5] px-1 py-0.5">/api/papers/reproduction</code> is available. Fallback: see <code className="font-mono bg-[#f5f5f5] px-1 py-0.5">papers/reproduction_hyperparameters.md</code>.
            </div>
          ) : (
            <div className="space-y-8">
              {reproductionSpecs.map((spec) => (
                <div key={spec.paper_id} className="bg-white border border-[#e5e5e5] overflow-hidden">
                  <div className="border-b border-[#e5e5e5] bg-[#fafafa] px-5 py-3">
                    <a
                      href={`https://arxiv.org/abs/${spec.arxiv_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-black hover:underline inline-flex items-center gap-1"
                    >
                      {spec.title} <ExternalLink className="w-4 h-4" />
                    </a>
                    <span className="text-xs text-[#999] ml-2">arXiv:{spec.arxiv_id}</span>
                  </div>
                  <div className="p-5 space-y-4">
                    <div>
                      <h4 className="text-xs font-semibold text-[#666] uppercase tracking-wider mb-2">Exact steps</h4>
                      <ol className="list-decimal list-inside space-y-1 text-sm text-[#333]">
                        <li><strong>Model:</strong> Use one of {spec.models.slice(0, 3).map((m) => m.split('/').pop() ?? m).join(', ')}{spec.models.length > 3 ? ` (or ${spec.models.length - 3} more)` : ''} — e.g. <code className="font-mono text-xs bg-[#f5f5f5] px-1 py-0.5">{spec.models[0]}</code></li>
                        <li><strong>Method:</strong> <code className="font-mono text-xs bg-[#f5f5f5] px-1 py-0.5">{spec.methods[0]}</code> · Bits: {spec.bit_widths.join(', ')}</li>
                        <li><strong>Calibration:</strong> dataset <code className="font-mono text-xs bg-[#f5f5f5] px-1 py-0.5">{spec.default_calib_dataset}</code>, {spec.default_calib_samples} samples, seq length {spec.default_calib_seq_len}</li>
                        <li><strong>Hyperparameters:</strong> {Object.entries(spec.config).map(([k, v]) => `${k}=${String(v)}`).join(', ')}</li>
                        <li><strong>Eval:</strong> Run on {spec.datasets.join(', ')} and compare to the <strong>Paper result</strong> column below.</li>
                      </ol>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-[#666] uppercase tracking-wider mb-2">How to set these parameters (in New Experiment)</h4>
                      <p className="text-sm text-[#666] mb-2">Set the following in the experiment form. Where the paper specifies a value, it is noted.</p>
                      <table className="w-full max-w-xl border border-[#e5e5e5] text-sm">
                        <thead>
                          <tr className="bg-[#f5f5f5]">
                            <th className="text-left py-2 px-3 border-b border-[#e5e5e5]">Parameter</th>
                            <th className="text-left py-2 px-3 border-b border-[#e5e5e5]">Set to</th>
                            <th className="text-left py-2 px-3 border-b border-[#e5e5e5]">In paper?</th>
                          </tr>
                        </thead>
                        <tbody className="text-[#333]">
                          <tr className="border-b border-[#e5e5e5]">
                            <td className="py-2 px-3 font-mono text-xs">group_size</td>
                            <td className="py-2 px-3">{spec.default_group_size != null ? spec.default_group_size : 'Per-channel (leave empty or use per-channel)'}</td>
                            <td className="py-2 px-3">{spec.default_group_size != null ? 'Yes (e.g. GPTQ Table 2: 128)' : 'Yes (SmoothQuant: per-channel weight)'}</td>
                          </tr>
                          <tr className="border-b border-[#e5e5e5]">
                            <td className="py-2 px-3 font-mono text-xs">symmetric</td>
                            <td className="py-2 px-3">{(spec.default_symmetric ?? true) ? 'Yes' : 'No'}</td>
                            <td className="py-2 px-3">Not always stated; use for reproducibility</td>
                          </tr>
                          <tr className="border-b border-[#e5e5e5]">
                            <td className="py-2 px-3 font-mono text-xs">Calibration samples</td>
                            <td className="py-2 px-3">{spec.default_calib_samples}</td>
                            <td className="py-2 px-3">Yes (paper setup)</td>
                          </tr>
                          <tr className="border-b border-[#e5e5e5]">
                            <td className="py-2 px-3 font-mono text-xs">Sequence length</td>
                            <td className="py-2 px-3">{spec.default_calib_seq_len}</td>
                            <td className="py-2 px-3">Yes (standard 2048 in papers)</td>
                          </tr>
                          <tr>
                            <td className="py-2 px-3 font-mono text-xs">Per-channel vs per-group</td>
                            <td className="py-2 px-3">{spec.default_group_size != null ? `Per-group (group_size=${spec.default_group_size})` : 'Per-channel'}</td>
                            <td className="py-2 px-3">{spec.default_group_size != null ? 'Yes (GPTQ: group size 128)' : 'Yes (SmoothQuant: per-channel)'}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[900px] table-dm">
                        <thead>
                          <tr>
                            <th>Model</th>
                            <th>Method</th>
                            <th>Bits</th>
                            <th>Calib dataset</th>
                            <th>Calib samples</th>
                            <th>Seq len</th>
                            <th>Key hyperparameters</th>
                            <th>Eval dataset</th>
                            <th>Metric</th>
                            <th>Paper result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {spec.results.map((r, i) => (
                            <tr key={`${r.model}-${r.method}-${r.bit_width}-${r.dataset}-${i}`}>
                              <td className="font-mono text-xs">{r.model}</td>
                              <td><code className="text-xs bg-[#f5f5f5] px-1 py-0.5">{r.method}</code></td>
                              <td>{r.bit_width}</td>
                              <td>{spec.default_calib_dataset}</td>
                              <td>{spec.default_calib_samples}</td>
                              <td>{spec.default_calib_seq_len}</td>
                              <td className="text-xs">{Object.entries(spec.config).map(([k, v]) => `${k}=${String(v)}`).join(', ')}</td>
                              <td>{r.dataset}</td>
                              <td>{r.metric_name}</td>
                              <td className="font-semibold text-black">{typeof r.value === 'number' && r.value % 1 !== 0 ? r.value.toFixed(2) : r.value}{r.table_ref ? ` (${r.table_ref})` : ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {spec.notes && (
                      <pre className="text-xs text-[#666] bg-[#f5f5f5] p-3 whitespace-pre-wrap border border-[#e5e5e5]">{spec.notes}</pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Paper Notes (structured) */}
        {filteredNotes.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold text-black mb-4">Structured Notes</h3>
            <div className="space-y-4">
              {filteredNotes.map((note: PaperNote) => (
                <div
                  key={note.id || note.paper_id}
                  className="bg-white border-0 border border-[#e5e5e5] p-5 shadow-none hover:border-[#999] transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-semibold text-black text-base">
                        {note.title || note.id}
                      </h4>
                      <div className="flex items-center gap-4 mt-1 text-sm text-[#999]">
                        {note.authors && note.authors.length > 0 && (
                          <span className="flex items-center gap-1">
                            <Users className="w-3.5 h-3.5" />
                            {note.authors.slice(0, 3).join(', ')}
                            {note.authors.length > 3 && ' et al.'}
                          </span>
                        )}
                        {note.year && (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5" />
                            {note.year}
                          </span>
                        )}
                        {note.venue && <span>{note.venue}</span>}
                      </div>
                    </div>
                    {note.arxiv_id && (
                      <a
                        href={`https://arxiv.org/abs/${note.arxiv_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 px-3 py-1 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-[#333] text-sm rounded-none transition-colors"
                      >
                        arXiv <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                  {note.core_idea && (
                    <p className="mt-3 text-sm text-[#666] leading-relaxed">
                      {note.core_idea.length > 300
                        ? note.core_idea.slice(0, 300) + '...'
                        : note.core_idea}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(note.method_names || []).map((m: string) => (
                      <span
                        key={m}
                        className="px-2 py-0.5 bg-[#C5A47E]/10 text-[#C5A47E] text-xs font-medium"
                      >
                        {m}
                      </span>
                    ))}
                    {(note.tags || []).map((t: string) => (
                      <span
                        key={t}
                        className="px-2 py-0.5 bg-[#f5f5f5] text-[#666] text-xs"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PDF Papers list */}
        <div>
          <h3 className="text-lg font-semibold text-black mb-4">PDF Library</h3>
          {filteredPapers.length === 0 ? (
            <div className="bg-white border-0 border border-[#e5e5e5] p-12 text-center shadow-none">
              <FileText className="w-12 h-12 text-[#ccc] mx-auto mb-4" />
              <p className="text-[#999] mb-2">
                {searchQuery ? 'No papers match your search.' : 'No PDF papers found.'}
              </p>
              <p className="text-sm text-[#999]">
                Add PDFs to <code className="font-mono bg-[#f5f5f5] px-1.5 py-0.5 rounded">papers/_literature/</code>
              </p>
            </div>
          ) : (
            <div className="bg-white border-0 border border-[#e5e5e5] overflow-hidden shadow-none">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#e5e5e5]">
                    <th className="px-5 py-3 text-left text-xs font-medium text-[#999] uppercase tracking-wider">
                      Paper
                    </th>
                    <th className="px-5 py-3 text-right text-xs font-medium text-[#999] uppercase tracking-wider">
                      Size
                    </th>
                    <th className="w-16 px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#e5e5e5]">
                  {filteredPapers.map((paper) => (
                    <tr key={paper.filename} className="hover:bg-[#fafafa] transition-colors">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-none bg-[#f5f5f5]">
                            <FileText className="w-4 h-4 text-[#C53030]" />
                          </div>
                          <div>
                            <p className={clsx('text-sm font-medium text-black')}>
                              {paper.title}
                            </p>
                            <p className="text-xs text-[#999] font-mono mt-0.5">
                              {paper.filename}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <span className="text-sm text-[#999]">{paper.size_mb} MB</span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button className="p-1.5 text-[#999] hover:text-[#666] hover:bg-[#f5f5f5] rounded-none transition-colors">
                          <Download className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
