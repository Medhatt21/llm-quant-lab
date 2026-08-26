import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  ArrowLeft, 
  ChevronRight,
  Cpu,
  Database,
  Layers,
  Play,
  Settings,
  Sparkles,
  Check,
  Info
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../../components/Layout/Header';
import APIError from '../../components/APIError';
import LoadingState from '../../components/LoadingState';
import { getQuantMethods, createExperiment, launchExperiment } from '../../api/client';

type Step = 'model' | 'method' | 'config' | 'review';

const steps: { id: Step; label: string; icon: typeof Cpu }[] = [
  { id: 'model', label: 'Select Model', icon: Cpu },
  { id: 'method', label: 'Quantization Method', icon: Layers },
  { id: 'config', label: 'Configuration', icon: Settings },
  { id: 'review', label: 'Review & Run', icon: Play },
];

const popularModels = [
  { name: 'facebook/opt-125m', size: '125M', description: 'Small OPT model, great for testing' },
  { name: 'facebook/opt-1.3b', size: '1.3B', description: 'Medium OPT model' },
  { name: 'meta-llama/Llama-2-7b-hf', size: '7B', description: 'Llama 2 base model' },
  { name: 'mistralai/Mistral-7B-v0.1', size: '7B', description: 'Mistral 7B base' },
  { name: 'microsoft/phi-2', size: '2.7B', description: 'Microsoft Phi-2' },
  { name: 'Qwen/Qwen-1_8B', size: '1.8B', description: 'Qwen 1.8B model' },
];

const calibrationDatasets = [
  { name: 'wikitext2', description: 'WikiText-2 language modeling' },
  { name: 'c4', description: 'Colossal Clean Crawled Corpus' },
  { name: 'ptb', description: 'Penn Treebank' },
  { name: 'pile', description: 'The Pile dataset' },
];

export default function NewExperiment() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState<Step>('model');
  const [config, setConfig] = useState({
    model: '',
    customModel: '',
    method: '',
    bitWidth: 4,
    groupSize: 128,
    perChannel: true,
    symmetric: true,
    calibDataset: 'wikitext2',
    calibSize: 128,
    calibSeqLength: 2048,
    evalDatasets: ['wikitext2'],
    captureActivations: true,
    name: '',
    notes: '',
    tags: [] as string[],
  });

  const { data: quantMethods, isLoading: methodsLoading, isError: methodsError, error: methodsFetchError, refetch: refetchMethods } = useQuery({
    queryKey: ['quant-methods'],
    queryFn: getQuantMethods,
    retry: 2,
  });

  const createMutation = useMutation({
    mutationFn: async (config: Parameters<typeof createExperiment>[0]) => {
      const result = await createExperiment(config);
      // Automatically launch the experiment after creation
      try {
        await launchExperiment(result.experiment_id);
      } catch {
        // Launch failure is non-fatal -- experiment is still created
        console.warn('Experiment created but launch failed. You can launch manually.');
      }
      return result;
    },
    onSuccess: (data) => { navigate(`/experiments/${data.experiment_id}`); },
    onError: (err) => { alert(`Experiment creation failed: ${err instanceof Error ? err.message : err}`); },
  });

  const currentStepIndex = steps.findIndex(s => s.id === currentStep);
  const selectedModel = config.model || config.customModel;

  const handleNext = () => { const next = currentStepIndex + 1; if (next < steps.length) setCurrentStep(steps[next].id); };
  const handleBack = () => { const prev = currentStepIndex - 1; if (prev >= 0) setCurrentStep(steps[prev].id); };

  const handleSubmit = () => {
    createMutation.mutate({
      model_path: selectedModel,
      quant_methods: [config.method],
      bit_width: config.bitWidth,
      group_size: config.groupSize,
      symmetric: config.symmetric,
      calib_dataset: config.calibDataset,
      calib_size: config.calibSize,
      calib_seq_length: config.calibSeqLength,
      eval_datasets: config.evalDatasets,
      name: config.name || undefined,
      notes: config.notes || undefined,
      tags: config.tags.length > 0 ? config.tags : undefined,
    });
  };

  return (
    <div className="min-h-screen">
      <Header title="New Experiment" subtitle="Configure and run a quantization experiment" />

      <div className="p-6">
        <Link to="/experiments" className="inline-flex items-center gap-2 text-[11px] font-semibold tracking-[0.1em] uppercase text-[#666] hover:text-black transition-colors mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Experiments
        </Link>

        {/* Progress Steps */}
        <div className="flex items-center justify-center mb-8">
          {steps.map((step, idx) => (
            <div key={step.id} className="flex items-center">
              <button onClick={() => idx <= currentStepIndex && setCurrentStep(step.id)}
                className={clsx('flex items-center gap-2 px-4 py-2 rounded-none transition-all',
                  currentStep === step.id && 'bg-[#f5f5f5] text-black',
                  idx < currentStepIndex && 'text-[#22c55e] hover:bg-[#f5f5f5]',
                  idx > currentStepIndex && 'text-[#999] cursor-not-allowed'
                )} disabled={idx > currentStepIndex}>
                <div className={clsx('w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  currentStep === step.id && 'bg-black text-white',
                  idx < currentStepIndex && 'bg-[#22c55e] text-white',
                  idx > currentStepIndex && 'bg-[#f5f5f5] text-[#999]'
                )}>{idx < currentStepIndex ? <Check className="w-4 h-4" /> : idx + 1}</div>
                <span className="hidden md:inline">{step.label}</span>
              </button>
              {idx < steps.length - 1 && <ChevronRight className="w-5 h-5 text-gray-300 mx-2" />}
            </div>
          ))}
        </div>

        <div className="max-w-4xl mx-auto">
          {/* Step 1: Model Selection */}
          {currentStep === 'model' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Cpu className="w-5 h-5 text-black" /> Select Model</h3>
                <div className="mb-6">
                  <label className="block text-sm text-[#999] mb-2">Custom Model Path (HuggingFace)</label>
                  <input type="text" placeholder="e.g., meta-llama/Llama-2-7b-hf" value={config.customModel}
                    onChange={(e) => setConfig({ ...config, customModel: e.target.value, model: '' })}
                    className="w-full px-4 py-3 bg-white border border-[#e5e5e5] rounded-none text-black placeholder-[#999] focus:outline-none focus:border-black" />
                </div>
                <div className="relative"><div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#e5e5e5]" /></div><div className="relative flex justify-center"><span className="px-4 bg-white text-sm text-[#999]">or choose a popular model</span></div></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                  {popularModels.map((model) => {
                    const isSelected = config.model === model.name;
                    return (
                      <button
                        key={model.name}
                        type="button"
                        onClick={() => setConfig((c) => ({ ...c, model: model.name, customModel: '' }))}
                        className={clsx(
                          'p-4 rounded-none border-2 text-left transition-all relative',
                          isSelected ? 'model-option-selected' : 'bg-[#fafafa] border-[#e5e5e5] hover:border-[#999] hover:bg-[#f0f0f0]'
                        )}
                        aria-pressed={isSelected}
                      >
                        {isSelected && (
                          <span className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 bg-black text-white text-xs font-semibold rounded">
                            <Check className="w-3 h-3" strokeWidth={3} />
                            Selected
                          </span>
                        )}
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-sm text-black">{model.name}</span>
                          <span className="px-2 py-0.5 bg-gray-200 text-[#666] text-xs rounded">{model.size}</span>
                        </div>
                        <p className="text-xs text-[#999] mt-1">{model.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Method Selection */}
          {currentStep === 'method' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Layers className="w-5 h-5 text-[#c5a47e]" /> Quantization Method</h3>
                {methodsLoading && <LoadingState message="Loading available methods..." />}
                {methodsError && <APIError title="Could not load quantization methods" error={methodsFetchError} onRetry={() => refetchMethods()} />}
                {quantMethods && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {quantMethods.map((method) => (
                      <button key={method.name} onClick={() => method.available && setConfig({ ...config, method: method.name })} disabled={!method.available}
                        className={clsx('p-5 rounded-none border-2 text-left transition-all',
                          config.method === method.name
                            ? 'bg-[#f0e6d4] border-[#C5A47E] border-l-[6px] border-l-[#C5A47E] shadow-[0_0_0_2px_rgba(197,164,126,0.3)]'
                            : method.available ? 'bg-[#fafafa] border-[#e5e5e5] hover:border-[#999]' : 'bg-white border-[#e5e5e5] opacity-50 cursor-not-allowed')}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold text-black uppercase">{method.name}</span>
                          {!method.available && <span className="px-2 py-0.5 bg-gray-200 text-[#999] text-xs rounded">Coming Soon</span>}
                        </div>
                        <p className="text-sm text-[#999] mb-3">{method.description}</p>
                        <div className="flex items-center gap-4 text-xs">
                          <span className="text-[#999]">{method.category.replace('_', ' ')}</span>
                          <span className="text-[#999]">{method.supported_bit_widths.join(', ')}-bit</span>
                          {method.requires_calibration && <span className="text-[#C5A47E]">requires calibration</span>}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Configuration */}
          {currentStep === 'config' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Settings className="w-5 h-5 text-[#2D8A4E]" /> Quantization Settings</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm text-[#999] mb-2">Bit Width</label>
                    <div className="flex gap-2">{[2, 3, 4, 8].map((bits) => (
                      <button key={bits} onClick={() => setConfig({ ...config, bitWidth: bits })}
                        className={clsx('flex-1 py-2 rounded-none text-sm font-medium transition-all', config.bitWidth === bits ? 'bg-black text-white' : 'bg-[#f5f5f5] text-[#666] hover:bg-[#e5e5e5]')}>{bits}-bit</button>
                    ))}</div>
                  </div>
                  <div>
                    <label className="block text-sm text-[#999] mb-2">Group Size</label>
                    <select value={config.groupSize} onChange={(e) => setConfig({ ...config, groupSize: Number(e.target.value) })}
                      className="w-full px-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-black focus:outline-none focus:border-black">
                      <option value={32}>32</option><option value={64}>64</option><option value={128}>128</option><option value={256}>256</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={config.perChannel} onChange={(e) => setConfig({ ...config, perChannel: e.target.checked })} className="w-4 h-4 rounded border-[#e5e5e5] bg-white text-black" /><span className="text-sm text-[#666]">Per-Channel</span></label>
                    <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={config.symmetric} onChange={(e) => setConfig({ ...config, symmetric: e.target.checked })} className="w-4 h-4 rounded border-[#e5e5e5] bg-white text-black" /><span className="text-sm text-[#666]">Symmetric</span></label>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Database className="w-5 h-5 text-[#C5A47E]" /> Calibration Data</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm text-[#999] mb-2">Dataset</label>
                    <div className="grid grid-cols-2 gap-2">{calibrationDatasets.map((ds) => (
                      <button key={ds.name} onClick={() => setConfig({ ...config, calibDataset: ds.name })}
                        className={clsx('p-3 rounded-none border-2 text-left transition-all',
                          config.calibDataset === ds.name
                            ? 'bg-[#f0e6d4] border-[#C5A47E] border-l-[6px] border-l-[#C5A47E]'
                            : 'bg-[#fafafa] border-[#e5e5e5] hover:border-[#999]')}>
                        <span className="text-sm text-black">{ds.name}</span><p className="text-xs text-[#999] mt-0.5">{ds.description}</p>
                      </button>
                    ))}</div>
                  </div>
                  <div>
                    <label className="block text-sm text-[#999] mb-2">Calibration Samples</label>
                    <input type="number" value={config.calibSize} onChange={(e) => setConfig({ ...config, calibSize: Number(e.target.value) })} min={8} max={512} step={8}
                      className="w-full px-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-black focus:outline-none focus:border-black" />
                    <p className="text-xs text-[#999] mt-1">Recommended: 128 for most models</p>
                  </div>
                  <div>
                    <label className="block text-sm text-[#999] mb-2">Sequence Length</label>
                    <select value={config.calibSeqLength} onChange={(e) => setConfig({ ...config, calibSeqLength: Number(e.target.value) })}
                      className="w-full px-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-black focus:outline-none focus:border-black">
                      <option value={512}>512</option><option value={1024}>1024</option><option value={2048}>2048</option><option value={4096}>4096</option>
                    </select>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Sparkles className="w-5 h-5 text-[#c5a47e]" /> Advanced Options</h3>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" checked={config.captureActivations} onChange={(e) => setConfig({ ...config, captureActivations: e.target.checked })} className="w-4 h-4 rounded border-[#e5e5e5] bg-white text-black" />
                  <div><span className="text-sm text-black">Capture Activation Statistics</span><p className="text-xs text-[#999]">Enable detailed layer-wise analysis</p></div>
                </label>
              </div>
            </div>
          )}

          {/* Step 4: Review */}
          {currentStep === 'review' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#e5e5e5] p-6">
                <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2"><Play className="w-5 h-5 text-[#2D8A4E]" /> Review Configuration</h3>
                <div className="space-y-4">
                  <div><label className="block text-sm text-[#999] mb-2">Experiment Name</label>
                    <input type="text" placeholder={`${config.method.toUpperCase()} ${config.bitWidth}-bit on ${selectedModel.split('/').pop()}`} value={config.name} onChange={(e) => setConfig({ ...config, name: e.target.value })}
                      className="w-full px-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-black placeholder-[#999] focus:outline-none focus:border-black" /></div>
                  <div><label className="block text-sm text-[#999] mb-2">Notes (optional)</label>
                    <textarea placeholder="Add any notes about this experiment..." value={config.notes} onChange={(e) => setConfig({ ...config, notes: e.target.value })} rows={3}
                      className="w-full px-4 py-2 bg-white border border-[#e5e5e5] rounded-none text-black placeholder-[#999] focus:outline-none focus:border-black resize-none" /></div>
                </div>
                <div className="mt-6 p-4 bg-[#fafafa] rounded-none">
                  <h4 className="text-sm font-medium text-black mb-3">Configuration Summary</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><p className="text-[#999]">Model</p><p className="text-black font-mono text-xs truncate">{selectedModel}</p></div>
                    <div><p className="text-[#999]">Method</p><p className="text-black uppercase">{config.method}</p></div>
                    <div><p className="text-[#999]">Bit Width</p><p className="text-black">{config.bitWidth}-bit</p></div>
                    <div><p className="text-[#999]">Group Size</p><p className="text-black">{config.groupSize}</p></div>
                    <div><p className="text-[#999]">Calibration</p><p className="text-black">{config.calibDataset}</p></div>
                    <div><p className="text-[#999]">Samples</p><p className="text-black">{config.calibSize}</p></div>
                    <div><p className="text-[#999]">Seq Length</p><p className="text-black">{config.calibSeqLength}</p></div>
                    <div><p className="text-[#999]">Symmetric</p><p className="text-black">{config.symmetric ? 'Yes' : 'No'}</p></div>
                  </div>
                </div>
                {createMutation.isError && (
                  <div className="mt-4 p-4 bg-[#fdf2f2] border border-[#e5c5c5] rounded-none text-sm text-[#c53030]">
                    Experiment creation failed: {createMutation.error instanceof Error ? createMutation.error.message : 'Unknown error'}. Ensure the API server is running.
                  </div>
                )}
                <div className="mt-4 p-4 bg-[#fafafa] border border-[#e5e5e5] rounded-none">
                  <div className="flex items-start gap-3"><Info className="w-5 h-5 text-black flex-shrink-0 mt-0.5" />
                    <div className="text-sm"><p className="text-black font-medium">Ready to run</p><p className="text-[#999] mt-1">The experiment will be submitted to the backend API for execution.</p></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8">
            <button onClick={handleBack} disabled={currentStepIndex === 0}
              className={clsx('px-6 py-2 rounded-none text-sm font-medium transition-colors', currentStepIndex === 0 ? 'text-[#999] cursor-not-allowed' : 'text-[#666] hover:text-black hover:bg-[#f5f5f5]')}>Back</button>
            {currentStep === 'review' ? (
              <button onClick={handleSubmit} disabled={!selectedModel || !config.method || createMutation.isPending}
                className="flex items-center gap-2 px-6 py-2.5 bg-black hover:bg-[#1a1a1a] disabled:bg-[#e5e5e5] disabled:text-[#999] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors">
                <Play className="w-4 h-4" /> {createMutation.isPending ? 'Submitting...' : 'Run Experiment'}
              </button>
            ) : (
              <button onClick={handleNext} disabled={(currentStep === 'model' && !selectedModel) || (currentStep === 'method' && !config.method)}
                className="flex items-center gap-2 px-6 py-2.5 bg-black hover:bg-[#1a1a1a] disabled:bg-[#e5e5e5] disabled:text-[#999] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors">Continue <ChevronRight className="w-4 h-4" /></button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
