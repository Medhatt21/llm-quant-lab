# AE Quickstart (IISWC 2026 #414 / AE #75)

Our Docker Engine: **29.0.2, build 810835**, with the Compose v2 plugin.
You don't need to match it — Engine 24.0+ / Compose 2.20+ is fine, because the
engine is not in the numerical path (see Notes).

Steps 1–4 need **no GPU and no model downloads**: the published 174-experiment
corpus ships as a Postgres dump, so you can validate the artifact end to end in
a few minutes before committing GPU time.

### 1. Clone

```bash
git clone https://github.com/Medhatt21/llm-quant-lab.git && cd llm-quant-lab
```

### 2. Write `.env`

Use this block, not `config/env.template` (its values are empty and it is
missing `POSTGRES_PORT_EXTERNAL`, which makes `up` fail). No secrets needed;
"variable is not set" warnings for the blank optional keys are harmless.

```bash
cat > .env <<'EOF'
HARDWARE_PROFILE=rocm
HIP_VISIBLE_DEVICES=0
CUDA_VISIBLE_DEVICES=0
NVIDIA_VISIBLE_DEVICES=all
POSTGRES_USER=llmquant
POSTGRES_PASSWORD=llmquant
POSTGRES_DB=llmquant
POSTGRES_PORT_EXTERNAL=5433
DATABASE_URL=postgresql://llmquant:llmquant@db:5432/llmquant
API_PORT=8080
FRONTEND_PORT=3000
JUPYTER_PORT=8888
VLLM_PORT=8000
PGADMIN_PORT=5050
LOCAL_MODELS_DIR=.local/models
LOCAL_DATA_DIR=.local/data
LOCAL_CACHE_DIR=.local/cache
LOG_LEVEL=INFO
LOG_FORMAT=text
EOF
mkdir -p .local/models .local/data .local/cache
```

### 3. Start Postgres and load the published results

The dump carries its own `CREATE TABLE`s, so start from an empty database:

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d db
docker compose exec -T db psql -U llmquant -d postgres \
  -c "DROP DATABASE IF EXISTS llmquant;" -c "CREATE DATABASE llmquant;"
docker compose exec -T db psql -U llmquant -d llmquant < data/db_dump_amd.sql
docker compose exec -T db psql -U llmquant -d llmquant -c "SELECT count(*) FROM experiments;"
```

### 4. Start the API and call the reproduction endpoint

```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d app
docker compose logs -f app     # wait for uvicorn on 0.0.0.0:8080, then Ctrl-C

curl -s localhost:8080/api/health
curl -s "localhost:8080/api/papers/reproduction-summary?v2_only=1" | jq '.'   # headline table
curl -s localhost:8080/api/papers/reproduction | jq '.'                        # paper specs
```

API docs at <http://localhost:8080/docs>. Optional dashboard (knowledge graph +
reproduction table): add `up -d frontend`, then <http://localhost:3000>.

### 5. Recompute the analysis from the pinned image (still no GPU)

```bash
bash scripts/reproduce_iiswc.sh            # add --run-gpu to rerun experiments on MI300X/MI210
```

Refits the per-method power law with 1,000-sample bootstrap CIs into
`reports/powerlaw/` and regenerates all 174 experiment YAMLs into
`experiments/configs/`. Needs `reproduction_results.csv` at the repo root.

### Notes

- **Pull by digest, not tag** — the digest is what fixes the numbers:
  `rocm/pytorch@sha256:3e917342db23b080cc7aa274321b4a7f33eb321e71b9607d69c0cb4deaaa8820`
  (= `rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0`). Full pin
  list in `REPRODUCIBILITY.md`. AMD GPU access is plain device passthrough
  (`/dev/kfd`, `/dev/dri`, groups `video`/`render`, `--ipc=host --shm-size=16g`)
  with no container runtime plugin, so the engine version does not affect
  results; the only host constraint is ROCm kernel driver ≥ ROCm userspace in
  the image.
- **Disk:** correcting the appendix — the ROCm image is ~11 GB compressed /
  ~30 GB on disk and NGC PyTorch ~10 GB / ~20–25 GB, so budget ~60 GB for images
  plus model weights, not 15–20 GB.
- **The anonymized mirror does not serve `.csv` files**, so
  `reproduction_results.csv` (needed in step 5) is missing there:
  <FILL: direct link or attachment>.
- **No GPU on the box?** The `app` service requests `/dev/kfd` and `/dev/dri`;
  comment out its `devices:`/`group_add:` block in `docker-compose.yml`. Steps
  3–5 never touch the GPU.
- **NVIDIA side is not containerized.** The paired-CUDA numbers came from a
  user-level `uv` virtualenv, because that host had no docker/sudo:
  `TORCH_PIN=2.9.1 TORCH_CUDA_TAG=cu128 bash scripts/setup_cuda_arm_venv.sh`,
  then `source .cuda-arm.env && bash scripts/run_parity_arm.sh 0`. Please don't
  use `docker/Dockerfile.cuda-arm` for parity runs — it is pinned to
  `nvcr.io/nvidia/pytorch:24.08-py3`, whose torch predates 2.9.1 and reintroduces
  the stack mismatch the paired arm exists to remove.
