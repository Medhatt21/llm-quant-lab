import { AlertTriangle, Terminal, RefreshCw, ExternalLink } from 'lucide-react';

interface APIErrorProps {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
}

export default function APIError({ title = 'Failed to load data', error, onRetry }: APIErrorProps) {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Could not connect to the API server.';

  const isNetworkError =
    message.includes('Network Error') ||
    message.includes('ERR_CONNECTION_REFUSED') ||
    message.includes('fetch');

  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center max-w-lg mx-auto">
      <div className="p-4 bg-[#fef2f2] mb-6">
        <AlertTriangle className="w-8 h-8 text-[#dc2626]" />
      </div>

      <h2 className="font-display text-2xl text-black mb-2">{title}</h2>
      <p className="text-[13px] text-[#666] mb-6">{message}</p>

      {isNetworkError && (
        <div className="w-full bg-white border border-[#e5e5e5] p-6 mb-6 text-left">
          <h3 className="stat-label mb-4 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-black" />
            How to fix
          </h3>
          <ol className="space-y-3 text-[13px] text-[#333]">
            <li className="flex gap-2">
              <span className="text-[#c5a47e] font-mono font-bold shrink-0">1.</span>
              <div>
                Start the backend API server:
                <code className="block mt-1 px-3 py-1.5 bg-[#f5f5f5] border border-[#e5e5e5] text-[#333] font-mono text-[11px]">
                  uvicorn src.api.server:app --reload --port 8080
                </code>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="text-[#c5a47e] font-mono font-bold shrink-0">2.</span>
              <div>
                Ensure your database is running:
                <code className="block mt-1 px-3 py-1.5 bg-[#f5f5f5] border border-[#e5e5e5] text-[#333] font-mono text-[11px]">
                  docker compose up -d postgres
                </code>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="text-[#c5a47e] font-mono font-bold shrink-0">3.</span>
              <div>
                Initialize the schema (first time only):
                <code className="block mt-1 px-3 py-1.5 bg-[#f5f5f5] border border-[#e5e5e5] text-[#333] font-mono text-[11px]">
                  python -m src.main init-db
                </code>
              </div>
            </li>
            <li className="flex gap-2">
              <span className="text-[#c5a47e] font-mono font-bold shrink-0">4.</span>
              <div>
                Set <code className="text-black font-mono text-[11px]">VITE_API_URL</code> in <code className="text-black font-mono text-[11px]">.env</code> if the API is on a different host/port.
              </div>
            </li>
          </ol>
        </div>
      )}

      <div className="flex items-center gap-3">
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-6 py-2.5 bg-black hover:bg-[#1a1a1a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        )}
        <a
          href="http://localhost:8080/api/health"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-5 py-2.5 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-black text-[11px] font-semibold tracking-[0.1em] uppercase transition-colors"
        >
          Check API Health
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
