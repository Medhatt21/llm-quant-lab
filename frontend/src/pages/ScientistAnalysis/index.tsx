import { useState } from 'react';
import {
  Brain,
  Play,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  BarChart3,
  FlaskConical,
  FileText,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../../components/Layout/Header';
import { useBackgroundTasks } from '../../context/BackgroundTasks';
import type { AnalysisResult, Finding } from '../../types';

const ANALYSIS_QUESTIONS = [
  'Which quantization methods achieve the best perplexity-latency trade-off across different model sizes?',
  'How does group size affect quantization quality for weight-only methods (GPTQ, AWQ, RTN)?',
  'What is the accuracy degradation pattern when reducing bit-width from 8 to 4 to 3 to 2 bits?',
  'How do different hardware platforms (CUDA vs ROCm) compare in inference throughput for quantized models?',
  'Which methods show the most consistent performance across different model architectures (LLaMA vs OPT vs Mistral)?',
];

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const isHigh = confidence >= 0.8;
  const isMed = confidence >= 0.5;

  return (
    <span
      className={clsx(
        'px-2.5 py-1 text-[9px] font-semibold tracking-[0.1em] uppercase',
        isHigh && 'bg-[#f0fdf4] text-[#16a34a]',
        !isHigh && isMed && 'bg-[#fef3c7] text-[#d97706]',
        !isMed && 'bg-[#fef2f2] text-[#dc2626]'
      )}
    >
      {(confidence * 100).toFixed(0)}% confidence
    </span>
  );
}

function FindingCard({ finding, index }: { finding: Finding; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-[#e5e5e5] p-5 transition-all duration-200 hover:shadow-[0_2px_20px_rgba(0,0,0,0.04)]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-4 text-left"
      >
        <div className="flex-shrink-0 mt-0.5 w-8 h-8 bg-[#faf6f0] flex items-center justify-center">
          <span className="font-display text-lg text-[#c5a47e]">{index + 1}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <ConfidenceBadge confidence={finding.confidence} />
            <span className="text-[9px] font-semibold tracking-[0.1em] uppercase px-2.5 py-1 bg-[#f5f5f5] text-[#666]">
              {finding.category}
            </span>
          </div>
          <h4 className="font-display text-base text-black">{finding.title}</h4>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-[#999] flex-shrink-0 mt-1" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[#999] flex-shrink-0 mt-1" />
        )}
      </button>

      {expanded && (
        <div className="mt-4 ml-12 space-y-4 border-t border-[#f0f0f0] pt-4">
          <div>
            <p className="stat-label mb-1.5">Description</p>
            <p className="text-[13px] text-[#333] leading-relaxed">{finding.description}</p>
          </div>
          <div>
            <p className="stat-label mb-1.5">Evidence</p>
            <div className="bg-[#fafafa] border border-[#e5e5e5] p-4">
              <p className="text-[12px] text-[#666] font-mono leading-relaxed">{finding.evidence}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AnalysisResultCard({ result, index }: { result: AnalysisResult; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="bg-white border border-[#e5e5e5] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-6 py-5 text-left hover:bg-[#fafafa] transition-colors"
      >
        <div className="w-10 h-10 bg-black flex items-center justify-center flex-shrink-0">
          <Brain className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-lg text-black">{result.question}</h3>
          <p className="text-[11px] text-[#999] mt-1">
            {result.findings.length} finding{result.findings.length !== 1 ? 's' : ''} · {result.follow_up_experiments.length} follow-up{result.follow_up_experiments.length !== 1 ? 's' : ''}
          </p>
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-[#999] flex-shrink-0" />
        ) : (
          <ChevronRight className="w-5 h-5 text-[#999] flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-6">
          {/* Findings */}
          {result.findings.length > 0 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <Lightbulb className="w-4 h-4 text-[#c5a47e]" />
                <p className="stat-label">Key Findings</p>
                <div className="gold-accent flex-1" />
              </div>
              <div className="space-y-3">
                {result.findings.map((finding, i) => (
                  <FindingCard key={i} finding={finding} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Follow-up experiments */}
          {result.follow_up_experiments.length > 0 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <FlaskConical className="w-4 h-4 text-[#666]" />
                <p className="stat-label">Suggested Follow-up Experiments</p>
                <div className="flex-1 h-px bg-[#e5e5e5]" />
              </div>
              <div className="space-y-3">
                {result.follow_up_experiments.map((exp, i) => (
                  <div key={i} className="border-l-2 border-l-[#c5a47e] bg-white border border-[#e5e5e5] p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={clsx(
                        'text-[9px] font-semibold tracking-[0.1em] uppercase px-2 py-0.5',
                        exp.priority >= 7 ? 'bg-[#fef2f2] text-[#dc2626]' :
                        exp.priority >= 4 ? 'bg-[#fef3c7] text-[#d97706]' :
                        'bg-[#f5f5f5] text-[#666]'
                      )}>
                        Priority {exp.priority}/10
                      </span>
                    </div>
                    <p className="text-[13px] text-black font-medium">{exp.description}</p>
                    <p className="text-[11px] text-[#999] mt-1">{exp.rationale}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw reasoning */}
          {result.raw_reasoning && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <FileText className="w-4 h-4 text-[#666]" />
                <p className="stat-label">Full Reasoning</p>
                <div className="flex-1 h-px bg-[#e5e5e5]" />
              </div>
              <div className="bg-[#fafafa] border border-[#e5e5e5] p-6 max-h-80 overflow-y-auto prose-luxury">
                <div
                  className="text-[13px] text-[#333] whitespace-pre-wrap leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: result.raw_reasoning
                      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
                      .replace(/^### (.+)$/gm, '<h4>$1</h4>')
                      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                      .replace(/`(.+?)`/g, '<code>$1</code>')
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ScientistAnalysis() {
  const [customQuestion, setCustomQuestion] = useState('');
  const { tasks, startScientistSingle, startScientistFull } = useBackgroundTasks();

  const scientistTasks = tasks.filter(
    (t) => t.kind === 'scientist-single' || t.kind === 'scientist-full',
  );
  const runningTasks = scientistTasks.filter((t) => t.status === 'running');
  const isRunning = runningTasks.length > 0;

  const results: AnalysisResult[] = [];
  for (const t of scientistTasks) {
    if (t.status !== 'completed' || !t.result) continue;
    if (t.kind === 'scientist-full' && Array.isArray(t.result)) {
      results.push(...(t.result as AnalysisResult[]));
    } else if (t.kind === 'scientist-single') {
      results.push(t.result as AnalysisResult);
    }
  }
  const errors = scientistTasks.filter((t) => t.status === 'error');

  const handleAsk = (question: string) => {
    startScientistSingle(question);
  };

  return (
    <div className="min-h-screen">
      <Header title="Agentic Scientist" subtitle="Research Intelligence" />

      <div className="p-8 max-w-5xl mx-auto space-y-8">
        {/* Ask a question */}
        <div className="bg-white border border-[#e5e5e5] overflow-hidden">
          <div className="px-6 pt-6 pb-4">
            <div className="flex items-center gap-3 mb-1">
              <Brain className="w-5 h-5 text-black" />
              <p className="section-label">Research Query</p>
            </div>
            <h2 className="font-display text-2xl text-black mt-1">Ask the Scientist</h2>
            <div className="gold-accent mt-3" />
          </div>

          <div className="px-6 pb-6">
            <div className="flex gap-3 mb-5">
              <input
                type="text"
                placeholder="Ask a research question about your quantization experiments..."
                value={customQuestion}
                onChange={(e) => setCustomQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customQuestion.trim()) {
                    handleAsk(customQuestion.trim());
                    setCustomQuestion('');
                  }
                }}
                className="flex-1 px-4 py-3 bg-white border border-[#e5e5e5] text-[13px] text-[#333] placeholder-[#999] focus:outline-none focus:border-black transition-colors"
              />
              <button
                onClick={() => {
                  if (customQuestion.trim()) {
                    handleAsk(customQuestion.trim());
                    setCustomQuestion('');
                  }
                }}
                disabled={!customQuestion.trim()}
                className="px-6 py-3 bg-black hover:bg-[#1a1a1a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors disabled:opacity-30 flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Analyze
              </button>
            </div>

            {/* Quick questions */}
            <div>
              <p className="stat-label mb-3">Quick Questions</p>
              <div className="flex flex-wrap gap-2">
                {ANALYSIS_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleAsk(q)}
                    className="px-3 py-2 bg-[#fafafa] border border-[#e5e5e5] hover:border-[#999] text-[11px] text-[#666] hover:text-black transition-all text-left"
                  >
                    {q.length > 80 ? q.slice(0, 80) + '…' : q}
                  </button>
                ))}
              </div>
            </div>

            {/* Full analysis button */}
            <div className="mt-6 pt-5 border-t border-[#e5e5e5]">
              <button
                onClick={() => startScientistFull()}
                className="flex items-center gap-2 px-6 py-3.5 bg-[#c5a47e] hover:bg-[#b8956a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors"
              >
                <BarChart3 className="w-4 h-4" />
                Run Full Analysis Pipeline
              </button>
              <p className="text-[11px] text-[#999] mt-2">
                Runs all {ANALYSIS_QUESTIONS.length} predefined research questions with tool use.
              </p>
            </div>
          </div>
        </div>

        {/* Running indicator */}
        {isRunning && (
          <div className="bg-white border-l-2 border-l-[#c5a47e] border border-[#e5e5e5] p-5 flex items-center gap-4">
            <div className="spinner-dm" />
            <div>
              <p className="text-[13px] text-black font-medium">
                {runningTasks.length} analysis task{runningTasks.length > 1 ? 's' : ''} running…
              </p>
              <p className="text-[11px] text-[#999] mt-0.5">
                Using SQL queries, statistical analysis, literature search, and more.
                You can navigate away — tasks continue in the background.
              </p>
            </div>
          </div>
        )}

        {/* Errors */}
        {errors.map((t) => (
          <div key={t.id} className="bg-white border-l-2 border-l-[#dc2626] border border-[#e5e5e5] p-5 flex items-center gap-4">
            <AlertTriangle className="w-5 h-5 text-[#dc2626] flex-shrink-0" />
            <div>
              <p className="text-[13px] text-black font-medium">Analysis failed: {t.label}</p>
              <p className="text-[11px] text-[#999] mt-0.5">{t.error}</p>
            </div>
          </div>
        ))}

        {/* Results */}
        {results.length > 0 && (
          <div>
            <div className="flex items-center gap-3 mb-6">
              <CheckCircle2 className="w-5 h-5 text-[#22c55e]" />
              <p className="section-label">Analysis Results</p>
              <span className="font-display text-lg text-black">({results.length})</span>
              <div className="gold-accent-wide flex-1 max-w-[60px]" />
            </div>
            <div className="space-y-4">
              {results.map((result, i) => (
                <AnalysisResultCard key={i} result={result} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {results.length === 0 && !isRunning && errors.length === 0 && (
          <div className="text-center py-20">
            <div className="w-20 h-20 bg-[#f5f5f5] flex items-center justify-center mx-auto mb-6">
              <Brain className="w-10 h-10 text-[#e5e5e5]" />
            </div>
            <h3 className="font-display text-2xl text-black mb-2">No Analysis Results Yet</h3>
            <p className="text-[13px] text-[#999] max-w-md mx-auto">
              Ask the Scientist a question or run the full analysis pipeline to get AI-powered insights
              about your quantization experiments.
            </p>
            <div className="gold-accent mx-auto mt-6" />
          </div>
        )}
      </div>
    </div>
  );
}
