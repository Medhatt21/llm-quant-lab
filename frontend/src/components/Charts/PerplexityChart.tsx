import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface DataPoint {
  method: string;
  bit_width: number;
  perplexity: number;
}

interface PerplexityChartProps {
  data: DataPoint[];
  baselinePerplexity?: number;
}

const methodColors: Record<string, string> = {
  AWQ: '#0ea5e9',
  GPTQ: '#d946ef',
  SmoothQuant: '#22c55e',
  'LLM.int8': '#f59e0b',
  RTN: '#6b7280',
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-gray-300 rounded-lg p-3 shadow-lg">
        <p className="font-medium text-black">{data.method}</p>
        <div className="mt-2 space-y-1 text-sm">
          <p className="text-[#666]">
            Bit Width: <span className="text-black">{data.bit_width}</span>
          </p>
          <p className="text-[#666]">
            Perplexity: <span className="text-black">{data.perplexity.toFixed(2)}</span>
          </p>
        </div>
      </div>
    );
  }
  return null;
};

export default function PerplexityChart({ data, baselinePerplexity }: PerplexityChartProps) {
  // Group data by method
  const methodGroups = data.reduce((acc, point) => {
    if (!acc[point.method]) {
      acc[point.method] = [];
    }
    acc[point.method].push(point);
    return acc;
  }, {} as Record<string, DataPoint[]>);

  return (
    <div className="bg-white rounded-none border border-[#e5e5e5] p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display font-semibold text-black">Perplexity vs Bit Width</h3>
          <p className="text-sm text-[#999] mt-0.5">Lower perplexity = better quality</p>
        </div>
        <div className="flex items-center gap-4">
          {Object.entries(methodColors).slice(0, 4).map(([method, color]) => (
            <div key={method} className="flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-[#999]">{method}</span>
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis 
            dataKey="bit_width" 
            type="number"
            domain={[1, 17]}
            ticks={[2, 3, 4, 8, 16]}
            tick={{ fill: '#6b7280', fontSize: 12 }}
            axisLine={{ stroke: "#d1d5db" }}
            label={{ 
              value: 'Bit Width', 
              position: 'bottom', 
              fill: '#6b7280',
              fontSize: 12
            }}
          />
          <YAxis 
            dataKey="perplexity"
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
          <Tooltip content={<CustomTooltip />} />
          
          {baselinePerplexity && (
            <ReferenceLine 
              y={baselinePerplexity} 
              stroke="#4a4a5c" 
              strokeDasharray="5 5"
              label={{ 
                value: 'FP16 Baseline', 
                fill: '#6b7280',
                fontSize: 11,
                position: 'right'
              }}
            />
          )}

          {Object.entries(methodGroups).map(([method, points]) => (
            <Scatter
              key={method}
              name={method}
              data={points}
              fill={methodColors[method] || '#6b7280'}
              shape="circle"
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
