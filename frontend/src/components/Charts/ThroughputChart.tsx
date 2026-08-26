import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';

interface ThroughputData {
  timestamp: string;
  tokens_per_second: number;
  latency_ms: number;
}

interface ThroughputChartProps {
  data: ThroughputData[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-gray-300 rounded-lg p-3 shadow-lg">
        <p className="text-xs text-[#999] mb-2">
          {format(new Date(label), 'HH:mm:ss')}
        </p>
        <div className="space-y-1">
          <p className="text-sm">
            <span className="text-[#999]">Throughput: </span>
            <span className="text-black font-medium">
              {payload[0]?.value?.toFixed(0)} tok/s
            </span>
          </p>
          <p className="text-sm">
            <span className="text-[#999]">Latency: </span>
            <span className="text-[#666] font-medium">
              {payload[1]?.value?.toFixed(1)} ms
            </span>
          </p>
        </div>
      </div>
    );
  }
  return null;
};

export default function ThroughputChart({ data }: ThroughputChartProps) {
  return (
    <div className="bg-white rounded-none border border-[#e5e5e5] p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display font-semibold text-black">Real-time Performance</h3>
          <p className="text-sm text-[#999] mt-0.5">Throughput and latency over time</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-black" />
            <span className="text-xs text-[#999]">Throughput</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-[#C5A47E]" />
            <span className="text-xs text-[#999]">Latency</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#d946ef" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#d946ef" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis 
            dataKey="timestamp"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={{ stroke: "#d1d5db" }}
            tickFormatter={(value) => format(new Date(value), 'HH:mm')}
          />
          <YAxis 
            yAxisId="throughput"
            orientation="left"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={{ stroke: "#d1d5db" }}
          />
          <YAxis 
            yAxisId="latency"
            orientation="right"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={{ stroke: "#d1d5db" }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            yAxisId="throughput"
            type="monotone"
            dataKey="tokens_per_second"
            stroke="#0ea5e9"
            strokeWidth={2}
            fill="url(#throughputGradient)"
          />
          <Area
            yAxisId="latency"
            type="monotone"
            dataKey="latency_ms"
            stroke="#d946ef"
            strokeWidth={2}
            fill="url(#latencyGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
