# Corrected serving-efficiency summary

Energy recomputed over steady-state serving power (top-quartile of power samples), not the full load+idle window. `reported_energy_j_FULL_WINDOW` is the old (overstated) number, kept for transparency.

| model | fmt | tok/s | active W | peak W | E/1k-tok (J) | old E (J, full window) | note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Meta-Llama-3-8B-Instruct | bf16 | 19594.1 | 270.2 | 750.0 | 13.79 | 19571.7 |  |
| Meta-Llama-3-8B-Instruct | fp16 | 19738.2 | 277.0 | 734.0 | 14.03 | 20558.5 |  |
| Meta-Llama-3-8B-Instruct | fp8 | None | 185.4 | 213.0 | None | 7841.2 | no valid vLLM benchmark captured (vllm_bench empty) |
| Qwen3.5-35B-A3B-FP8 | fp8 | None | 147.1 | 175.0 | None | 2793.5 | no valid vLLM benchmark captured (vllm_bench empty) |
