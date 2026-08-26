# Complete serving-performance grid, AMD MI300X (IISWC #414)

vLLM bench throughput, single MI300X, input/output 1024/256, 200 prompts, nightly vLLM ROCm image.

| Base model | Arch | Precision | GPU weights (GiB) | Host RAM (GiB) | GPU util (%) | Power (W) | Throughput (tok/s) | Energy (J/1k-tok) |
|---|---|---|---|---|---|---|---|---|
| Meta-Llama-3-8B-Instruct | dense 8B | BF16 | 14.96 | 5.0 | 64.6 | 440.2 | 21958 | 20.05 |
| Meta-Llama-3-8B-Instruct | dense 8B | FP8 | 8.46 | 7.0 | 57.6 | 386.9 | 23657 | 16.35 |
| phi-4 | dense 14B | BF16 | 27.39 | 6.7 | 73.2 | 564.2 | 13168 | 42.84 |
| phi-4 | dense 14B | FP8 | 14.62 | 6.1 | 65.3 | 464.7 | 17636 | 26.35 |
| gemma-3-27b-it | dense 27B | BF16 | 51.45 | 8.7 | 73.9 | 648.0 | 5943 | 109.04 |
| gemma-3-27b-it | dense 27B | FP8 | 27.42 | 9.5 | 69.0 | 505.0 | 8900 | 56.75 |
| Qwen3-32B | dense 32B | BF16 | 61.03 | 5.5 | 80.4 | 687.2 | 6445 | 106.62 |
| Qwen3-32B | dense 32B | FP8 | 31.98 | 7.0 | 71.5 | 564.0 | 9998 | 56.41 |
| Qwen3-30B-A3B | MoE, 3.3B act | BF16 | 56.88 | 6.3 | 50.8 | 366.4 | 21590 | 16.97 |
| Qwen3-30B-A3B | MoE, 3.3B act | FP8 | 29.03 | 7.3 | 48.6 | 333.7 | 24473 | 13.64 |
| Llama-4-Scout | MoE, 17B act | FP8 | 109.35 | None | 59.3 | 412.7 | 10188 | 40.51 |
