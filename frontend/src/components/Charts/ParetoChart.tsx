import { useMemo } from 'react';
import {
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
  ComposedChart,
  ZAxis,
} from 'recharts';
import type { ParetoPoint } from '../../types';

interface ParetoChartProps {
  data: ParetoPoint[];
  xMetric?: 'latency_p50' | 'tokens_per_second' | 'compression_ratio';
  yMetric?: 'perplexity';
}

const methodColors: Record<string, string> = {
  'FP16 Baseline': '#6b7280',
  'AWQ 4-bit': '#0ea5e9',
  'GPTQ 4-bit': '#d946ef',
  'GPTQ 3-bit': '#a855f7',
  'SmoothQuant W8A8': '#22c55e',
  'LLM.int8': '#f59e0b',
};

function findParetoFront(data: ParetoPoint[], xKey: string, yKey: string): ParetoPoint[] {
  const sorted = [...data].sort((a, b) => (a as any)[xKey] - (b as any)[xKey]);
  const pareto: ParetoPoint[] = [];
  let minY = Infinity;

  for (const point of sorted) {
    if ((point as any)[yKey] < minY) {
      pareto.push(point);
      minY = (point as any)[yKey];
    }
  }

  return pareto;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-gray-300 rounded-lg p-3 shadow-lg">
        <p className="font-medium text-black">{data.method}</p>
        <div className="mt-2 space-y-1 text-sm">
          <p className="text-[#666]">
            Perplexity: <span className="text-black">{data.perplexity.toFixed(2)}</span>
          </p>
          <p className="text-[#666]">
            Latency P50: <span className="text-black">{data.latency_p50.toFixed(1)}ms</span>
          </p>
          <p className="text-[#666]">
            Throughput: <span className="text-black">{data.tokens_per_second} tok/s</span>
          </p>
          <p className="text-[#666]">
            Compression: <span className="text-black">{data.compression_ratio.toFixed(2)}x</span>
          </p>
        </div>
      </div>
    );
  }
  return null;
};

export default function ParetoChart({ 
  data, 
  xMetric = 'latency_p50',
  yMetric = 'perplexity' 
}: ParetoChartProps) {
  const paretoFront = useMemo(() => 
    findParetoFront(data, xMetric, yMetric), 
    [data, xMetric, yMetric]
  );

  const xLabel = {
    latency_p50: 'Latency P50 (ms)',
    tokens_per_second: 'Throughput (tokens/s)',
    compression_ratio: 'Compression Ratio',
  }[xMetric];

  return (
    <div className="bg-white rounded-none border border-[#e5e5e5] p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display font-semibold text-black">Pareto Front Analysis</h3>
          <p className="text-sm text-[#999] mt-0.5">Quality vs Performance trade-offs</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-black" style={{ borderStyle: 'dashed' }} />
            <span className="text-xs text-[#999]">Pareto Front</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart margin={{ top: 20, right: 30, bottom: 30, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis 
            dataKey={xMetric}
            type="number"
            tick={{ fill: '#6b7280', fontSize: 12 }}
            axisLine={{ stroke: "#d1d5db" }}
            label={{ 
              value: xLabel, 
              position: 'bottom', 
              fill: '#6b7280',
              fontSize: 12,
              offset: 0
            }}
          />
          <YAxis 
            dataKey={yMetric}
            tick={{ fill: '#6b7280', fontSize: 12 }}
            axisLine={{ stroke: "#d1d5db" }}
            label={{ 
              value: 'Perplexity', 
              angle: -90, 
              position: 'insideLeft',
              fill: '#6b7280',
              fontSize: 12
            }}
          />
          <ZAxis dataKey="compression_ratio" range={[60, 200]} />
          <Tooltip content={<CustomTooltip />} />

          {/* Pareto Front Line */}
          <Line
            data={paretoFront.sort((a, b) => (a as any)[xMetric] - (b as any)[xMetric])}
            type="monotone"
            dataKey={yMetric}
            stroke="#0ea5e9"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />

          {/* Data Points */}
          {data.map((point) => (
            <Scatter
              key={point.method}
              data={[point]}
              fill={methodColors[point.method] || '#6b7280'}
              name={point.method}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 justify-center">
        {data.map((point) => (
          <div key={point.method} className="flex items-center gap-2">
            <div 
              className="w-3 h-3 rounded-full" 
              style={{ backgroundColor: methodColors[point.method] || '#6b7280' }}
            />
            <span className="text-xs text-[#999]">{point.method}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
