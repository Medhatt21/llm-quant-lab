# LLM Quant Lab Experiments

This directory contains Jupyter notebooks for reproducing and extending quantization research papers.

**Algorithm reference:** See [papers/quantization_algorithms_table.md](../papers/quantization_algorithms_table.md) for a table of quantization algorithms with type (QAT/PTQ), scope, bits, calibration, description, and **benchmarking datasets**.

## Getting Started

### 1. Configure Environment

Edit `.env` in the project root:

```bash
# Required: Get your HuggingFace token at https://huggingface.co/settings/tokens
HF_TOKEN=hf_your_actual_token_here

# Optional but recommended: Weights & Biases for experiment tracking
# Get your key at https://wandb.ai/authorize
WANDB_API_KEY=your_wandb_key_here

# Optional: Scientist LLM for AI-generated reports
SCIENTIST_LLM_API_KEY=your_openai_or_other_key_here
```

### 2. Start Services

```bash
# Start PostgreSQL database (required for experiment tracking)
docker-compose up -d db

# Or start all services
docker-compose up -d
```

### 3. Run Notebooks

Start with the setup notebook to verify your environment:

```bash
jupyter lab experiments/00_setup_and_quickstart.ipynb
```

## Notebooks

| Notebook | Description | Paper |
|----------|-------------|-------|
| `00_setup_and_quickstart.ipynb` | Environment setup and verification | - |
| `01_gptq_paper_reproduction.ipynb` | GPTQ 4-bit/3-bit weight quantization | [arXiv:2210.17323](https://arxiv.org/abs/2210.17323) |
| `02_smoothquant_paper_reproduction.ipynb` | SmoothQuant W8A8 quantization | [arXiv:2211.10438](https://arxiv.org/abs/2211.10438) |

## Paper Reference Results

### GPTQ (Table 2 - WikiText-2 Perplexity)

| Model | FP16 | GPTQ 4-bit | GPTQ 3-bit | RTN 4-bit |
|-------|------|------------|------------|-----------|
| OPT-125M | 27.65 | 31.12 | 53.97 | 48.17 |
| OPT-350M | 22.00 | 24.24 | 36.00 | 36.33 |
| OPT-1.3B | 14.63 | 15.47 | 20.93 | 23.54 |
| OPT-6.7B | 10.86 | 11.39 | 12.70 | 14.89 |

**Key GPTQ Settings:**
- `actorder=True` - Process columns by Hessian diagonal importance
- `percdamp=0.01` - Hessian damping factor
- `group_size=128` - For 4-bit quantization

### SmoothQuant (Table 1 - WikiText-2 Perplexity)

| Model | FP16 | SmoothQuant W8A8 | Naive W8A8 |
|-------|------|------------------|------------|
| OPT-125M | 27.65 | 27.94 | - |
| OPT-1.3B | 14.63 | 14.89 | - |
| OPT-6.7B | 10.86 | 10.95 | 11.34 |
| OPT-13B | 10.13 | 10.22 | 10.53 |

**Key SmoothQuant Settings:**
- `alpha=0.5` - Migration strength (balances weight/activation difficulty)
- Per-channel weight quantization
- Per-token activation quantization

## Experiment Tracking

Results are tracked in two ways:

### 1. Weights & Biases (Recommended)
- Real-time visualization at wandb.ai
- Automatic hyperparameter tracking
- Collaboration features
- Model artifact storage

### 2. PostgreSQL Database
- Local structured storage
- SQL querying for analysis
- Integrated with FastAPI dashboard

## Directory Structure

```
experiments/
├── README.md                              # This file
├── 00_setup_and_quickstart.ipynb          # Setup verification
├── 01_gptq_paper_reproduction.ipynb       # GPTQ experiments
└── 02_smoothquant_paper_reproduction.ipynb # SmoothQuant experiments
```

## Model Recommendations

For quick testing, use smaller models first:

1. **facebook/opt-125m** (~250MB) - Fast iterations
2. **facebook/opt-350m** (~700MB) - Slightly larger
3. **facebook/opt-1.3b** (~2.6GB) - Good for paper reproduction
4. **bigscience/bloom-560m** (~1.1GB) - Different architecture

For full paper reproduction:
- **facebook/opt-6.7b**, **opt-13b**, **opt-30b**
- **bigscience/bloom-7b1**

## Extending the Experiments

### Adding New Methods

1. Implement quantizer in `src/quant/custom/`
2. Register with `register_quantizer()`
3. Create a new notebook following the template

### Adding Paper Comparisons

1. Add paper specification in `src/tracking/paper_reproduction.py`
2. Use `PaperReproductionTracker` in your notebook
3. Results automatically compare with paper values

## Troubleshooting

### GPU Not Detected
```bash
# Check ROCm installation
rocm-smi

# Verify HIP devices
echo $HIP_VISIBLE_DEVICES
```

### Database Connection Failed
```bash
# Start just the database
docker-compose up -d db

# Check it's running
docker-compose ps
```

### Out of Memory
- Use smaller models (opt-125m, opt-350m)
- Reduce calibration samples
- Use gradient checkpointing
