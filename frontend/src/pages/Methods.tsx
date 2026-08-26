import { useQuery } from '@tanstack/react-query';
import { 
  Layers, 
  ExternalLink, 
  CheckCircle2, 
  Clock,
  BookOpen,
  Zap,
  HardDrive
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../components/Layout/Header';
import APIError from '../components/APIError';
import LoadingState from '../components/LoadingState';
import { getQuantMethods } from '../api/client';

const methodDetails: Record<string, {
  paper: string;
  paperUrl: string;
  pros: string[];
  cons: string[];
  bestFor: string[];
  complexity: 'low' | 'medium' | 'high';
}> = {
  awq: {
    paper: 'AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration',
    paperUrl: 'https://arxiv.org/abs/2306.00978',
    pros: [
      'Excellent accuracy preservation at 4-bit',
      'No retraining required',
      'Fast inference with optimized kernels',
      'Works well with various model sizes',
    ],
    cons: [
      'Limited to 4-bit quantization',
      'Requires calibration data',
      'May not work well with very small models',
    ],
    bestFor: ['Production deployment', 'Memory-constrained environments', 'Large language models'],
    complexity: 'medium',
  },
  gptq: {
    paper: 'GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers',
    paperUrl: 'https://arxiv.org/abs/2210.17323',
    pros: [
      'Supports multiple bit widths (2-8 bit)',
      'High accuracy with proper calibration',
      'Well-established method with wide support',
      'Good for extreme compression (2-3 bit)',
    ],
    cons: [
      'Slower quantization process',
      'Requires careful hyperparameter tuning',
      'Higher memory during quantization',
    ],
    bestFor: ['Research experiments', 'Extreme compression', 'Accuracy-critical applications'],
    complexity: 'high',
  },
  smoothquant: {
    paper: 'SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models',
    paperUrl: 'https://arxiv.org/abs/2211.10438',
    pros: [
      'Quantizes both weights and activations',
      'Near-lossless W8A8 quantization',
      'Hardware-friendly INT8 operations',
      'Good for inference acceleration',
    ],
    cons: [
      'Limited to 8-bit quantization',
      'Requires activation statistics',
      'Less compression than weight-only methods',
    ],
    bestFor: ['Hardware acceleration', 'INT8 inference', 'Balanced quality-speed tradeoff'],
    complexity: 'medium',
  },
  llm_int8: {
    paper: 'LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale',
    paperUrl: 'https://arxiv.org/abs/2208.07339',
    pros: [
      'Handles outlier features automatically',
      'No calibration data needed',
      'Preserves model quality well',
      'Easy to use with bitsandbytes',
    ],
    cons: [
      'Mixed-precision overhead',
      'Slower than pure INT8',
      'Only 8-bit quantization',
    ],
    bestFor: ['Quick deployment', 'Models with outliers', 'Ease of use'],
    complexity: 'low',
  },
  rtn: {
    paper: 'Round-To-Nearest Baseline Quantization',
    paperUrl: '',
    pros: [
      'Simplest quantization baseline',
      'No calibration data required',
      'Extremely fast quantization',
      'Useful as a lower-bound reference',
    ],
    cons: [
      'Lowest accuracy among all methods',
      'No error compensation',
      'Significant quality degradation at low bits',
    ],
    bestFor: ['Baseline comparison', 'Quick testing', 'Upper-bound compression speed'],
    complexity: 'low',
  },
  hqq: {
    paper: 'Half-Quadratic Quantization (HQQ)',
    paperUrl: 'https://arxiv.org/abs/2309.15531',
    pros: [
      'No calibration data needed',
      'Fast optimization-based quantization',
      'Good accuracy at 4-bit and below',
    ],
    cons: [
      'Less established than GPTQ/AWQ',
      'May require tuning optimization steps',
    ],
    bestFor: ['Calibration-free quantization', 'Quick experimentation', 'Low-bit research'],
    complexity: 'low',
  },
  spqr: {
    paper: 'SpQR: A Sparse-Quantized Representation for Near-Lossless LLM Weight Compression',
    paperUrl: 'https://arxiv.org/abs/2306.03078',
    pros: [
      'Near-lossless compression via outlier isolation',
      'Sparse representation for sensitive weights',
      'Good accuracy at 3-4 bit',
    ],
    cons: [
      'Requires calibration data',
      'More complex storage format',
      'Slower inference without custom kernels',
    ],
    bestFor: ['Near-lossless compression', 'Outlier-heavy models', 'Research on weight sensitivity'],
    complexity: 'high',
  },
  owq: {
    paper: 'OWQ: Outlier-Aware Weight Quantization',
    paperUrl: 'https://arxiv.org/abs/2306.02272',
    pros: [
      'Handles weight outliers explicitly',
      'Improved accuracy over basic methods',
      'Compatible with GPTQ-style quantization',
    ],
    cons: [
      'Requires calibration data',
      'Limited bit width support (3-4 bit)',
    ],
    bestFor: ['Models with weight outliers', 'Improved 3-4 bit accuracy', 'Research'],
    complexity: 'medium',
  },
  dgq: {
    paper: 'DGQ: Distribution-Guided Quantization',
    paperUrl: '',
    pros: [
      'Distribution-aware quantization',
      'Better handling of non-uniform weight distributions',
    ],
    cons: [
      'Requires calibration data',
      'Limited to 4-bit',
    ],
    bestFor: ['Distribution-aware compression', 'Research on weight distributions'],
    complexity: 'medium',
  },
  'os+': {
    paper: 'Outlier Suppression+: Accurate Quantization of Large Language Models by Equivalent and Optimal Shifting and Scaling',
    paperUrl: 'https://arxiv.org/abs/2304.09145',
    pros: [
      'Improved outlier handling over SmoothQuant',
      'W8A8 quantization with better accuracy',
      'Automatic channel-wise shifting and scaling',
    ],
    cons: [
      'Limited to 8-bit quantization',
      'Requires calibration data',
    ],
    bestFor: ['W8A8 inference', 'Improved INT8 accuracy', 'Outlier suppression research'],
    complexity: 'medium',
  },
  quarot: {
    paper: 'QuaRot: Outlier-Free 4-Bit Inference in Rotated LLMs',
    paperUrl: 'https://arxiv.org/abs/2404.00456',
    pros: [
      'Eliminates outliers via rotation',
      'Supports both weight and activation quantization',
      'State-of-the-art W4A4 results',
    ],
    cons: [
      'Requires Hadamard rotation preprocessing',
      'More complex setup',
      'Requires calibration data',
    ],
    bestFor: ['W4A4 quantization', 'Outlier elimination', 'Cutting-edge research'],
    complexity: 'high',
  },
  normtweaking: {
    paper: 'NormTweaking: High-performance Low-bit Quantization via Norm Tweaking',
    paperUrl: 'https://arxiv.org/abs/2309.02784',
    pros: [
      'Lightweight norm adjustment post-quantization',
      'Improves accuracy with minimal overhead',
    ],
    cons: [
      'Requires calibration data',
      'Best used as a refinement step',
    ],
    bestFor: ['Post-quantization refinement', 'Improving existing quantized models'],
    complexity: 'medium',
  },
  tesseraq: {
    paper: 'TesseraQ: Ultra Low-Bit LLM Post-Training Quantization with Block Reconstruction',
    paperUrl: 'https://arxiv.org/abs/2402.01187',
    pros: [
      'Excellent at ultra-low bit (2-3 bit)',
      'Block-wise reconstruction for better accuracy',
      'Mixed-precision support',
    ],
    cons: [
      'Requires calibration data',
      'Longer quantization time',
      'Research-stage method',
    ],
    bestFor: ['Ultra-low bit quantization', '2-3 bit research', 'Mixed-precision experiments'],
    complexity: 'high',
  },
  kvquant: {
    paper: 'KVQuant: Towards 10 Million Context Length LLM Inference with KV Cache Quantization',
    paperUrl: 'https://arxiv.org/abs/2401.18079',
    pros: [
      'Reduces KV cache memory significantly',
      'Enables longer context lengths',
      'Complementary to weight quantization',
    ],
    cons: [
      'Specific to inference optimization',
      'May affect generation quality',
      'Implementation complexity',
    ],
    bestFor: ['Long context inference', 'Memory optimization', 'Stacked with weight quant'],
    complexity: 'high',
  },
  omniquant: {
    paper: 'OmniQuant: Omnidirectionally Calibrated Quantization for Large Language Models',
    paperUrl: 'https://arxiv.org/abs/2308.13137',
    pros: [
      'Learnable weight clipping',
      'Equivalent transformation optimization',
      'State-of-the-art at low bit widths',
    ],
    cons: [
      'Requires training/optimization',
      'More complex setup',
      'Longer quantization time',
    ],
    bestFor: ['Best accuracy at low bits', 'Research', 'When quality is paramount'],
    complexity: 'high',
  },
  zeroquant: {
    paper: 'ZeroQuant: Efficient and Affordable Post-Training Quantization for Large-Scale Transformers',
    paperUrl: 'https://arxiv.org/abs/2206.01861',
    pros: [
      'Group-wise quantization for weights',
      'Token-wise quantization for activations',
      'Hardware-friendly design',
    ],
    cons: [
      'Limited to 4/8-bit quantization',
      'Requires custom kernels for best performance',
    ],
    bestFor: ['Inference acceleration', 'Production deployment', 'Balanced quality-speed'],
    complexity: 'medium',
  },
  paretoq: {
    paper: 'ParetoQ: Improving Scaling Laws in Extremely Low-bit LLM Quantization',
    paperUrl: 'https://arxiv.org/abs/2404.01562',
    pros: [
      'Pushes boundaries at 1-2 bit quantization',
      'Improves Pareto frontier of quality vs compression',
      'Novel training-aware approach',
    ],
    cons: [
      'Requires quantization-aware training',
      'Computationally expensive',
      'Experimental/research stage',
    ],
    bestFor: ['Extreme compression research', 'Ultra-low bit experiments', 'Pareto frontier analysis'],
    complexity: 'high',
  },
  bitnet: {
    paper: 'BitNet b1.58: Scaling 1-bit Transformers for Large Language Models',
    paperUrl: 'https://arxiv.org/abs/2402.17764',
    pros: [
      'Ternary weights (-1, 0, 1) — extreme compression',
      'No floating-point multiply needed',
      'Massive energy and memory savings',
    ],
    cons: [
      'Requires training from scratch',
      'Cannot be applied post-training',
      'Limited model support',
    ],
    bestFor: ['New model training', '1-bit research', 'Edge deployment'],
    complexity: 'high',
  },
};

export default function Methods() {
  const { data: quantMethods, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['quant-methods'],
    queryFn: getQuantMethods,
    retry: 2,
  });

  if (isLoading) return <div className="min-h-screen"><Header title="Quantization Methods" subtitle="Available techniques for model compression" /><LoadingState message="Loading methods..." /></div>;
  if (isError || !quantMethods) return <div className="min-h-screen"><Header title="Quantization Methods" subtitle="Available techniques for model compression" /><APIError title="Could not load quantization methods" error={error} onRetry={() => refetch()} /></div>;

  return (
    <div className="min-h-screen">
      <Header 
        title="Quantization Methods" 
        subtitle="Available techniques for model compression"
      />

      <div className="p-6 space-y-6">
        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <OverviewCard
            icon={Layers}
            title="Weight-Only"
            description="Quantize model weights while keeping activations in FP16"
            count={quantMethods.filter(m => m.category === 'weight_only').length}
            color="quantum"
          />
          <OverviewCard
            icon={Zap}
            title="Weight + Activation"
            description="Quantize both weights and activations for faster inference"
            count={quantMethods.filter(m => m.category === 'weight_activation').length}
            color="neural"
          />
          <OverviewCard
            icon={HardDrive}
            title="KV Cache"
            description="Quantize key-value cache for memory efficiency"
            count={quantMethods.filter(m => m.category === 'kv_cache').length}
            color="matrix"
          />
        </div>

        {/* Method Cards */}
        <div className="space-y-6">
          {quantMethods.map((method) => {
            const details = methodDetails[method.name];
            
            return (
              <div 
                key={method.name}
                className={clsx(
                  'bg-white border-0 border overflow-hidden',
                  method.available ? 'border-[#e5e5e5]' : 'border-[#e5e5e5]/50 opacity-60'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5e5]">
                  <div className="flex items-center gap-4">
                    <div className={clsx(
                      'w-12 h-12 border-0 flex items-center justify-center',
                      method.category === 'weight_only' && 'bg-[#f5f5f5]',
                      method.category === 'weight_activation' && 'bg-[#f5f5f5]',
                      method.category === 'kv_cache' && 'bg-[#f5f5f5]',
                    )}>
                      <span className={clsx(
                        'text-lg font-bold',
                        method.category === 'weight_only' && 'text-black',
                        method.category === 'weight_activation' && 'text-[#C5A47E]',
                        method.category === 'kv_cache' && 'text-[#666]',
                      )}>
                        {method.name.slice(0, 2).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <h3 className="font-display font-semibold text-black text-lg uppercase">
                        {method.name}
                      </h3>
                      <p className="text-sm text-[#999]">{method.description}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    {method.available ? (
                      <span className="flex items-center gap-1.5 px-3 py-1 bg-[#2D8A4E]/10 text-[#2D8A4E] text-sm">
                        <CheckCircle2 className="w-4 h-4" />
                        Available
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 px-3 py-1 bg-[#f5f5f5] text-[#999] text-sm">
                        <Clock className="w-4 h-4" />
                        Coming Soon
                      </span>
                    )}
                    
                    {details && (
                      <a
                        href={details.paperUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 px-3 py-1 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-[#666] hover:text-black text-sm transition-colors"
                      >
                        <BookOpen className="w-4 h-4" />
                        Paper
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>

                {/* Body */}
                <div className="p-6">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Specs */}
                    <div className="space-y-4">
                      <h4 className="text-sm font-medium text-[#999] uppercase tracking-wider">Specifications</h4>
                      <div className="space-y-3">
                        <div className="flex justify-between">
                          <span className="text-[#999]">Category</span>
                          <span className="text-black capitalize">{method.category.replace('_', ' ')}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#999]">Bit Widths</span>
                          <span className="text-black">{method.supported_bit_widths.join(', ')}-bit</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#999]">Calibration</span>
                          <span className="text-black">{method.requires_calibration ? 'Required' : 'Not needed'}</span>
                        </div>
                        {details && (
                          <div className="flex justify-between">
                            <span className="text-[#999]">Complexity</span>
                            <span className={clsx(
                              details.complexity === 'low' && 'text-[#2D8A4E]',
                              details.complexity === 'medium' && 'text-[#C5A47E]',
                              details.complexity === 'high' && 'text-[#C53030]',
                            )}>
                              {details.complexity.charAt(0).toUpperCase() + details.complexity.slice(1)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Pros & Cons */}
                    {details && (
                      <>
                        <div className="space-y-4">
                          <h4 className="text-sm font-medium text-[#999] uppercase tracking-wider">Advantages</h4>
                          <ul className="space-y-2">
                            {details.pros.map((pro, idx) => (
                              <li key={idx} className="flex items-start gap-2 text-sm">
                                <CheckCircle2 className="w-4 h-4 text-[#2D8A4E] flex-shrink-0 mt-0.5" />
                                <span className="text-[#666]">{pro}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div className="space-y-4">
                          <h4 className="text-sm font-medium text-[#999] uppercase tracking-wider">Best For</h4>
                          <div className="flex flex-wrap gap-2">
                            {details.bestFor.map((use, idx) => (
                              <span
                                key={idx}
                                className="px-3 py-1.5 bg-[#f5f5f5] text-[#666] text-sm"
                              >
                                {use}
                              </span>
                            ))}
                          </div>
                          
                          <h4 className="text-sm font-medium text-[#999] uppercase tracking-wider mt-4">Limitations</h4>
                          <ul className="space-y-1">
                            {details.cons.slice(0, 2).map((con, idx) => (
                              <li key={idx} className="text-sm text-[#999]">
                                • {con}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Compatibility Matrix */}
        <div className="bg-white border-0 border border-[#e5e5e5] p-6">
          <h3 className="font-display font-semibold text-black mb-4">Method Stacking Compatibility</h3>
          <p className="text-sm text-[#999] mb-6">
            Some quantization methods can be combined for additional compression. Green indicates compatible combinations.
          </p>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs text-[#999]"></th>
                  {quantMethods.filter(m => m.available).map(m => (
                    <th key={m.name} className="px-4 py-2 text-center text-xs text-[#999] uppercase">
                      {m.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {quantMethods.filter(m => m.available).map(row => (
                  <tr key={row.name}>
                    <td className="px-4 py-2 text-xs text-[#999] uppercase">{row.name}</td>
                    {quantMethods.filter(m => m.available).map(col => {
                      const compatible = 
                        row.name === col.name ? null :
                        (row.category !== col.category) ? true : false;
                      
                      return (
                        <td key={col.name} className="px-4 py-2 text-center">
                          {compatible === null ? (
                            <span className="text-[#ccc]">—</span>
                          ) : compatible ? (
                            <span className="inline-block w-6 h-6 rounded bg-[#2D8A4E]/10 text-[#2D8A4E]">✓</span>
                          ) : (
                            <span className="inline-block w-6 h-6 rounded bg-[#C53030]/10 text-[#C53030]">✗</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

interface OverviewCardProps {
  icon: typeof Layers;
  title: string;
  description: string;
  count: number;
  color: 'quantum' | 'neural' | 'matrix';
}

function OverviewCard({ icon: Icon, title, description, count, color }: OverviewCardProps) {
  const colors = {
    quantum: 'bg-[#fafafa] text-black border-black/20',
    neural: 'bg-[#fafafa] text-[#C5A47E] border-[#C5A47E]/30',
    matrix: 'bg-[#fafafa] text-[#666] border-[#e5e5e5]',
  };

  return (
    <div className={`p-5 border-0 border ${colors[color]}`}>
      <div className="flex items-center gap-3 mb-3">
        <Icon className="w-6 h-6" />
        <span className="text-2xl font-bold text-black">{count}</span>
      </div>
      <h3 className="font-medium text-black">{title}</h3>
      <p className="text-sm text-[#999] mt-1">{description}</p>
    </div>
  );
}
