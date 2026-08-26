import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface LayerData {
  layer_index: number;
  layer_name: string;
  pre_quant_norm: number;
  post_quant_norm: number;
  quantization_error: number;
  outlier_ratio?: number;
}

interface LayerStatsChartProps {
  data: LayerData[];
  metric?: 'norm' | 'error' | 'outlier';
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-gray-300 rounded-lg p-3 shadow-lg">
        <p className="font-medium text-black text-sm">{data.layer_name}</p>
        <div className="mt-2 space-y-1 text-xs">
          {payload.map((entry: any) => (
            <p key={entry.dataKey} className="text-[#666]">
              {entry.name}: <span style={{ color: entry.color }}>{entry.value.toFixed(4)}</span>
            </p>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

export default function LayerStatsChart({ data, metric = 'norm' }: LayerStatsChartProps) {
  const chartConfig = {
    norm: {
      title: 'Layer-wise Weight Norms',
      subtitle: 'Pre vs Post quantization L2 norms',
      bars: [
        { key: 'pre_quant_norm', name: 'Pre-Quant', color: '#6b7280' },
        { key: 'post_quant_norm', name: 'Post-Quant', color: '#0ea5e9' },
      ],
    },
    error: {
      title: 'Quantization Error by Layer',
      subtitle: 'Mean squared error after quantization',
      bars: [
        { key: 'quantization_error', name: 'Error', color: '#ef4444' },
      ],
    },
    outlier: {
      title: 'Activation Outlier Ratio',
      subtitle: 'Percentage of activations > 6σ',
      bars: [
        { key: 'outlier_ratio', name: 'Outlier %', color: '#f59e0b' },
      ],
    },
  };

  const config = chartConfig[metric];

  return (
    <div className="bg-white rounded-none border border-[#e5e5e5] p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display font-semibold text-black">{config.title}</h3>
          <p className="text-sm text-[#999] mt-0.5">{config.subtitle}</p>
        </div>
        <div className="flex items-center gap-4">
          {config.bars.map((bar) => (
            <div key={bar.key} className="flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded" 
                style={{ backgroundColor: bar.color }}
              />
              <span className="text-xs text-[#999]">{bar.name}</span>
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis 
            dataKey="layer_index"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={{ stroke: "#d1d5db" }}
            label={{ 
              value: 'Layer Index', 
              position: 'bottom', 
              fill: '#6b7280',
              fontSize: 11
            }}
          />
          <YAxis 
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={{ stroke: "#d1d5db" }}
          />
          <Tooltip content={<CustomTooltip />} />
          
          {metric === 'error' && (
            <ReferenceLine 
              y={0.01} 
              stroke="#ef4444" 
              strokeDasharray="5 5"
              label={{ 
                value: 'Threshold', 
                fill: '#ef4444',
                fontSize: 10,
                position: 'right'
              }}
            />
          )}

          {config.bars.map((bar) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              name={bar.name}
              fill={bar.color}
              radius={[2, 2, 0, 0]}
              maxBarSize={20}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
