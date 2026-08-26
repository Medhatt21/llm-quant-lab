#!/usr/bin/env python3
"""Standalone experiment worker — runs as a subprocess with CUDA_VISIBLE_DEVICES isolation.

Reads experiment config from stdin (JSON), performs quantization + evaluation via
LightCompress, writes results to the database, and prints structured lines to stdout:
  PROGRESS:<msg>   — updates the progress label in the parent
  LOG:<msg>        — appended to the experiment log buffer
  ERROR:<msg>      — error (also logged)
  RESULT:<json>    — final result payload

Exit code 0 = success, non-zero = failure.
"""

import gc
import json
import os
import sys
import time


def _print(msg: str) -> None:
    print(msg, flush=True)


def main(payload: dict) -> None:
    experiment_id: int = payload["experiment_id"]
    config: dict = payload["config"]
    db_url: str = payload["db_url"]

    import torch
    import torch.distributed as dist
    from easydict import EasyDict
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)

    from src.quant.llmc_wrappers import LLMC_ALGORITHMS, detect_model_type
    from llmc.data import BaseDataset
    from llmc.utils.registry_factory import ALGO_REGISTRY, MODEL_REGISTRY
    from llmc.utils import get_modality
    import llmc.compression.quantization   # noqa: F401
    import llmc.models                     # noqa: F401

    _print("PROGRESS:Initializing...")

    with SessionLocal() as session:
        session.execute(
            text("UPDATE experiments SET status = 'running', updated_at = NOW() WHERE id = :id"),
            {"id": experiment_id},
        )
        session.commit()

    try:
        from huggingface_hub import login as hf_login
        hf_token = os.environ.get("HF_TOKEN")
        if hf_token:
            hf_login(token=hf_token, add_to_git_credential=False)
    except Exception:
        pass

    baseline_only = config.get("baseline_only", False)

    method = config["quant_methods"][0]
    if not baseline_only:
        spec = LLMC_ALGORITHMS.get(method.lower())
        if spec is None:
            raise ValueError(f"Unknown quantization method: {method}")
        llmc_method = spec.llmc_method
    else:
        llmc_method = "fp16"

    model_path = config["model_name"]
    model_type = detect_model_type(model_path)
    bit_width = config["bit_width"]
    group_size = config["group_size"]
    symmetric = config["symmetric"]
    calib_dataset = config["calib_dataset"]
    calib_size = max(config["calib_size"], 1)
    calib_seq_length = config["calib_seq_length"]

    # ── W&B ──────────────────────────────────────────────────────────
    wandb_run = None
    try:
        import wandb
        wandb_project = os.environ.get("WANDB_PROJECT", "llm-quant-lab")
        wandb_run = wandb.init(
            project=wandb_project,
            name=config.get("name") or f"exp-{experiment_id}",
            config={
                "experiment_id": experiment_id, "model": model_path,
                "method": method, "llmc_method": llmc_method,
                "bit_width": bit_width, "group_size": group_size,
                "symmetric": symmetric, "calib_dataset": calib_dataset,
                "calib_size": calib_size, "calib_seq_length": calib_seq_length,
            },
            tags=[method, f"{bit_width}bit", model_path.split("/")[-1]],
            reinit=True,
        )
        with SessionLocal() as session:
            session.execute(text(
                "UPDATE experiments SET wandb_run_id = :run_id, "
                "wandb_run_url = :run_url, wandb_project = :project, "
                "updated_at = NOW() WHERE id = :id"
            ), {"run_id": wandb_run.id, "run_url": wandb_run.url,
                "project": wandb_project, "id": experiment_id})
            session.commit()
        _print(f"LOG:W&B run initialized: {wandb_run.url}")
    except Exception as wandb_err:
        _print(f"LOG:W&B init failed (non-fatal): {wandb_err}")

    # ── Build LLMC config ────────────────────────────────────────────
    preproc_map = {
        "wikitext2": "wikitext2_gptq", "c4": "c4_gptq",
        "ptb": "ptb_gptq", "pile": "pile_gptq",
    }

    special_cfg = spec.special_config.copy()
    user_method_config = config.get("method_config") or {}
    method_overrides = {k: v for k, v in user_method_config.items() if not k.startswith("_")}
    if method_overrides:
        special_cfg.update(method_overrides)
        _print(f"LOG:Method config overrides applied: {method_overrides}")

    quant_cfg = {
        "method": llmc_method,
        "weight": {
            "bit": bit_width, "symmetric": symmetric,
            "granularity": "per_group" if group_size else "per_channel",
            "group_size": group_size if group_size else -1,
        },
        "special": special_cfg, "quant_out": True,
    }
    calib_cfg = {
        "name": calib_dataset, "download": True, "n_samples": calib_size,
        "bs": 1, "seq_len": calib_seq_length,
        "preproc": preproc_map.get(calib_dataset, "general"), "seed": 42,
    }
    eval_cfg = {
        "eval_pos": ["fake_quant"], "name": calib_dataset, "download": True,
        "bs": 1, "seq_len": calib_seq_length, "inference_per_block": False,
    }

    model_dtype = "auto"

    llmc_config = EasyDict({
        "model": {"type": model_type, "path": model_path, "torch_dtype": model_dtype},
        "calib": calib_cfg, "eval": eval_cfg, "quant": quant_cfg, "base": {"seed": 42},
    })

    # ── Distributed init (per-process, unique port) ──────────────────
    import socket
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    os.environ["RANK"] = "0"
    os.environ["WORLD_SIZE"] = "1"
    os.environ["LOCAL_RANK"] = "0"
    os.environ["MASTER_ADDR"] = "127.0.0.1"
    os.environ["MASTER_PORT"] = str(_free_port())

    if not dist.is_initialized():
        dist.init_process_group(backend="gloo", world_size=1, rank=0)

    # ── 1. Load model ────────────────────────────────────────────────
    _print("PROGRESS:Loading model...")
    n_devices = torch.cuda.device_count()
    # Multi-GPU via device_map=auto only for baselines (no quantization).
    # Quantized runs need all layers on one device for LLMC's block-wise loop.
    if baseline_only and n_devices >= 2:
        device_map = "auto"
        _print(f"LOG:Using {n_devices} GPUs (device_map=auto) for baseline eval")
    else:
        device_map = "cuda:0"
    _print(f"LOG:Loading model {model_path} via LightCompress...")
    llmc_model = MODEL_REGISTRY[model_type](llmc_config, device_map=device_map)

    # ── 2. Calibrate + quantize ──────────────────────────────────────
    from filelock import FileLock
    _ds_lock = FileLock("/tmp/llm_quant_dataset.lock", timeout=600)
    compressor = None

    if baseline_only:
        _print("PROGRESS:FP16 baseline — skipping quantization")
        _print("LOG:Baseline mode: evaluating unquantized FP16 model")
        quant_duration = 0.0
    else:
        modalities, modality_configs = get_modality(llmc_config)

        for modality, modality_config in zip(modalities, modality_configs):
            llmc_model.set_modality(modality)

            _print("PROGRESS:Loading calibration data...")
            _print(f"LOG:Loading calibration data: {calib_dataset} ({calib_size} samples, seq_len={calib_seq_length})")

            with _ds_lock:
                dataset = BaseDataset(
                    llmc_model.get_tokenizer(), llmc_config.calib, llmc_model.batch_process,
                )
                calib_data, padding_mask = dataset.get_calib_dataset()

            llmc_model.collect_first_block_input(calib_data, padding_mask)
            del calib_data
            gc.collect()
            torch.cuda.empty_cache()

            _print(f"PROGRESS:Quantizing ({llmc_method} {bit_width}-bit)...")
            _print(f"LOG:Running {llmc_method} quantization @ {bit_width}-bit, group_size={group_size}, symmetric={symmetric}")

            quant_start = time.time()
            compressor = ALGO_REGISTRY[modality_config.method](
                llmc_model, modality_config,
                llmc_model.get_first_block_input(), llmc_model.get_padding_mask(),
                llmc_config,
            )
            compressor.run_block_loop()
        quant_duration = time.time() - quant_start
        _print(f"LOG:Quantization completed in {quant_duration:.1f}s")

    # ── 3. Evaluate perplexity ───────────────────────────────────────
    eval_datasets = config.get("eval_datasets") or []
    PERPLEXITY_DATASETS = {"wikitext2", "c4", "ptb", "pile"}
    ppl_datasets = [d for d in eval_datasets if d in PERPLEXITY_DATASETS]
    if not ppl_datasets:
        ppl_datasets = [calib_dataset]

    _print("PROGRESS:Evaluating...")
    _print(f"LOG:Running perplexity evaluation on: {ppl_datasets}")

    ppl_results: dict[str, float] = {}
    from llmc.eval.eval_ppl import PerplexityEval

    preproc_map_eval = {
        "c4": "c4_gptq", "wikitext2": "wikitext2_gptq",
        "ptb": "ptb_gptq", "pile": "pile_gptq",
    }

    for ppl_ds in ppl_datasets:
        try:
            _print(f"PROGRESS:Evaluating perplexity ({ppl_ds})...")
            _print(f"LOG:Evaluating perplexity on {ppl_ds}...")
            eval_cfg_copy = dict(llmc_config.eval)
            eval_cfg_copy["name"] = ppl_ds
            eval_cfg_copy["preproc"] = preproc_map_eval.get(ppl_ds, "general")
            llmc_config.eval = EasyDict(eval_cfg_copy)
            with _ds_lock:
                evaluator = PerplexityEval(llmc_model, llmc_config)
            ppl_val = evaluator.eval(llmc_model)
            ppl_results[ppl_ds] = float(ppl_val)
            _print(f"LOG:Perplexity ({ppl_ds}): {ppl_val:.2f}")
            del evaluator
        except Exception as eval_err:
            _print(f"LOG:Perplexity eval on {ppl_ds} failed (non-fatal): {eval_err}")

    fake_quant_ppl = ppl_results.get(calib_dataset) or next(iter(ppl_results.values()), None)

    # ── 3b. lm-eval-harness for accuracy benchmarks ─────────────────
    run_accuracy = config.get("run_accuracy_benchmarks", False)
    accuracy_tasks = [d for d in eval_datasets if d not in PERPLEXITY_DATASETS] if run_accuracy else []
    eval_harness_results: dict[str, dict[str, float]] = {}

    if accuracy_tasks:
        _print("PROGRESS:Running lm-eval-harness...")
        try:
            import lm_eval
            from lm_eval.models.huggingface import HFLM
            eval_model = llmc_model.get_model()
            if n_devices >= 2 and baseline_only:
                try:
                    eval_model = eval_model.to(dtype=torch.float16)
                except Exception:
                    pass
            else:
                try:
                    eval_model = eval_model.to(dtype=torch.float16, device="cuda")
                except Exception:
                    try:
                        eval_model = eval_model.float().cuda()
                    except Exception:
                        pass
            lm_obj = HFLM(pretrained=eval_model, tokenizer=llmc_model.get_tokenizer(), batch_size=1)
            task_results = lm_eval.simple_evaluate(model=lm_obj, tasks=accuracy_tasks, batch_size=1)
            for task_name, task_data in (task_results.get("results") or {}).items():
                for metric_key, metric_val in task_data.items():
                    if isinstance(metric_val, (int, float)) and not metric_key.endswith("_stderr"):
                        clean_metric = metric_key.replace(",none", "").replace(",_none", "")
                        eval_harness_results.setdefault(task_name, {})[clean_metric] = float(metric_val)
                        _print(f"LOG:lm-eval {task_name}/{clean_metric}: {metric_val:.4f}")
        except ImportError:
            _print("LOG:lm-eval-harness not installed — skipping accuracy benchmarks.")
        except Exception as eval_err:
            _print(f"LOG:lm-eval-harness failed (non-fatal): {eval_err}")

    # ── W&B logging ──────────────────────────────────────────────────
    if wandb_run is not None:
        try:
            log_data = {"quant_duration_s": quant_duration}
            for k, v in ppl_results.items():
                log_data[f"perplexity/{k}"] = v
            if fake_quant_ppl is not None:
                log_data["perplexity"] = float(fake_quant_ppl)
            wandb_run.log(log_data)
            wandb_run.summary["perplexity"] = float(fake_quant_ppl) if fake_quant_ppl else None
            wandb_run.summary["quant_duration_s"] = quant_duration
            wandb_run.summary["status"] = "completed"
        except Exception:
            pass

    # ── 4. Write results to DB ───────────────────────────────────────
    with SessionLocal() as session:
        session.execute(text(
            "UPDATE quant_configs SET status='completed', duration_seconds=:dur WHERE experiment_id=:eid"
        ), {"dur": quant_duration, "eid": experiment_id})

        for ds_name, ppl_val in ppl_results.items():
            session.execute(text(
                "INSERT INTO metrics (experiment_id,dataset,metric_name,value,split,created_at) "
                "VALUES (:eid,:dataset,'perplexity',:value,'test',NOW())"
            ), {"eid": experiment_id, "dataset": ds_name, "value": ppl_val})

        for task_name, task_metrics in eval_harness_results.items():
            for mname, mval in task_metrics.items():
                session.execute(text(
                    "INSERT INTO metrics (experiment_id,dataset,metric_name,value,split,created_at) "
                    "VALUES (:eid,:dataset,:metric_name,:value,'test',NOW())"
                ), {"eid": experiment_id, "dataset": task_name, "metric_name": mname, "value": mval})

        paper_id = config.get("paper_id")
        if paper_id:
            session.execute(text(
                "UPDATE experiments SET tags=array_append(COALESCE(tags,ARRAY[]::text[]),:tag) "
                "WHERE id=:eid AND NOT(:tag=ANY(COALESCE(tags,ARRAY[]::text[])))"
            ), {"eid": experiment_id, "tag": f"paper:{paper_id}"})

        session.execute(text(
            "UPDATE experiments SET status='completed', updated_at=NOW() WHERE id=:id"
        ), {"id": experiment_id})
        session.commit()

    # ── 5. Log baseline metrics to W&B for comparison ───────────────
    if wandb_run is not None and not baseline_only:
        try:
            from src.tracking.paper_reproduction import ALL_PAPER_SPECS as _ALL_SPECS
            tags = config.get("tags") or []
            paper_id = next((t.split(":", 1)[1] for t in tags if t.startswith("paper:")), None)
            if paper_id:
                with SessionLocal() as session:
                    baseline_rows = session.execute(text("""
                        SELECT m.dataset, m.metric_name, m.value
                        FROM metrics m
                        JOIN experiments e ON e.id = m.experiment_id
                        WHERE e.model_name = :model
                          AND e.status = 'completed'
                          AND :tag = ANY(e.tags)
                          AND 'baseline' = ANY(e.tags)
                        ORDER BY e.created_at DESC
                    """), {"model": model_path, "tag": f"paper:{paper_id}"}).fetchall()

                    baseline_logged = 0
                    seen_keys: set[str] = set()
                    for row in baseline_rows:
                        rd = dict(row._mapping)
                        key = f"{rd['dataset']}_{rd['metric_name']}"
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        wandb_run.summary[f"baseline/{key}"] = float(rd["value"])
                        baseline_logged += 1
                    if baseline_logged:
                        _print(f"LOG:Logged {baseline_logged} baseline metrics from DB to W&B")

                spec_obj = _ALL_SPECS.get(paper_id)
                if spec_obj:
                    paper_baseline_logged = 0
                    for r in spec_obj.results:
                        if r.model == model_path and r.method in ("fp16", "fp32"):
                            wandb_run.summary[f"paper_baseline/{r.dataset}_{r.metric_name}"] = r.value
                            paper_baseline_logged += 1
                    if paper_baseline_logged:
                        _print(f"LOG:Logged {paper_baseline_logged} paper FP16 baseline values to W&B")
        except Exception as baseline_err:
            _print(f"LOG:Baseline W&B logging failed (non-fatal): {baseline_err}")

    del llmc_model
    if compressor is not None:
        del compressor
    gc.collect()
    torch.cuda.empty_cache()

    if wandb_run is not None:
        try:
            wandb_run.finish()
        except Exception:
            pass

    _print("PROGRESS:Done")
    _print("RESULT:" + json.dumps({"status": "completed", "ppl": ppl_results}))


if __name__ == "__main__":
    import traceback as _tb
    _payload = None
    try:
        _payload = json.loads(sys.stdin.read())
        main(_payload)
    except Exception as e:
        _tb.print_exc(file=sys.stderr)
        sys.stderr.flush()
        print(f"ERROR:{e}", flush=True)
        if _payload:
            try:
                from sqlalchemy import create_engine as _ce, text as _t
                from sqlalchemy.orm import sessionmaker as _sm
                _eng = _ce(_payload["db_url"])
                with _sm(bind=_eng)() as _sess:
                    _sess.execute(_t(
                        "UPDATE experiments SET status='failed', "
                        "error_message=:err, updated_at=NOW() WHERE id=:id"
                    ), {"id": _payload["experiment_id"], "err": str(e)[:1000]})
                    _sess.commit()
            except Exception:
                pass
        sys.exit(1)
