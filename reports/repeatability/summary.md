# Repeatability & verdict-stability summary

- Corpus: **174 metric measurements from 79 unique configurations** (79 measurements across 76 configs have paper refs).

## Per-config repeatability

| method | model | platform | torch | n | mean | SD | CV% | type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gptq | opt125m | amd_mi300x | 2.9.1+rocm7.2.0 | 3 | 29.323 | 0.1241 | 0.423 | calibration |
| gptq | opt125m | nvidia_a10g | 2.6.0+cu124 | 3 | 29.2398 | 0.1074 | 0.367 | calibration |
| rtn | opt125m | amd_mi300x | 2.9.1+rocm7.2.0 | 3 | 30.4717 | 0.0 | 0.0 | process-repro |
| rtn | opt125m | nvidia_a10g | 2.6.0+cu124 | 3 | 30.4717 | 0.0 | 0.0 | process-repro |

## Cross-hardware paired deltas (same config, both platforms)

| method | model | AMD mean | NVIDIA mean | AMD-vs-NVIDIA % | stack_matched | note |
| --- | --- | --- | --- | --- | --- | --- |
| gptq | opt125m | 29.323 | 29.2398 | 0.2845 | False |  |
| rtn | opt125m | 30.4717 | 30.4717 | 0.0 | False | exact bitwise agreement |

## Verdict stability (all trials must agree to be stable)

- gptq/opt125m/amd_mi300x (vs paper 31.12): thr2:stable, thr5:stable, thr10:stable
- gptq/opt125m/nvidia_a10g (vs paper 31.12): thr2:stable, thr5:stable, thr10:stable
- rtn/opt125m/amd_mi300x (vs paper 37.28): thr2:stable, thr5:stable, thr10:stable
- rtn/opt125m/nvidia_a10g (vs paper 37.28): thr2:stable, thr5:stable, thr10:stable
