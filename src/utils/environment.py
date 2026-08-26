"""Automatic environment snapshotting for reproducibility.

Captures GPU info, pip freeze, git SHA, library versions, etc.
and stores them in the ``environment_snapshots`` table.  If an
identical snapshot already exists (matched by ``env_hash``), the
existing record is reused.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version detection helpers
# ---------------------------------------------------------------------------

def _safe_import_version(module_name: str) -> str | None:
    """Return version string of *module_name* or None."""
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", None)
    except ImportError:
        return None


def _detect_gpu() -> dict[str, Any]:
    """Return GPU name, driver, count via torch, rocm-smi, nvidia-smi, or sysfs.

    Tries multiple strategies so the lightweight API container (no torch)
    can still report GPU info when the host devices are mounted.
    """
    info: dict[str, Any] = {"gpu_name": None, "gpu_driver": None, "gpu_count": 0}

    # Strategy 1: PyTorch (if installed)
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_name"] = torch.cuda.get_device_name(0)
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    stderr=subprocess.DEVNULL,
                ).decode().strip().split("\n")[0]
                info["gpu_driver"] = out
            except Exception:
                pass
            return info
    except ImportError:
        logger.debug("torch not installed — trying CLI fallbacks")

    # Strategy 2: rocm-smi (AMD ROCm GPUs — works if /dev/kfd + /dev/dri are mounted)
    try:
        concise = subprocess.check_output(
            ["rocm-smi"], stderr=subprocess.DEVNULL, timeout=10,
        ).decode()
        gpu_count = 0
        for line in concise.split("\n"):
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and "0x" in stripped:
                gpu_count += 1
        if gpu_count > 0:
            info["gpu_count"] = gpu_count
            # Determine name from GFX version
            gfx_names = {
                "gfx942": "AMD Instinct MI300X",
                "gfx940": "AMD Instinct MI300A",
                "gfx90a": "AMD Instinct MI250X",
                "gfx908": "AMD Instinct MI100",
            }
            try:
                prod = subprocess.check_output(
                    ["rocm-smi", "--showproductname"],
                    stderr=subprocess.DEVNULL, timeout=10,
                ).decode()
                for line in prod.split("\n"):
                    if "GFX Version" in line:
                        gfx = line.split(":")[-1].strip()
                        if gfx in gfx_names:
                            info["gpu_name"] = gfx_names[gfx]
                            break
            except Exception:
                pass
            if not info["gpu_name"]:
                info["gpu_name"] = f"AMD GPU (x{gpu_count})"
            try:
                drv = subprocess.check_output(
                    ["rocm-smi", "--showdriverversion"],
                    stderr=subprocess.DEVNULL, timeout=10,
                ).decode()
                for line in drv.split("\n"):
                    if "Driver" in line and ":" in line:
                        info["gpu_driver"] = line.split(":")[-1].strip()
                        break
            except Exception:
                pass
            return info
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("rocm-smi not available")
    except Exception as e:
        logger.debug(f"rocm-smi failed: {e}")

    # Strategy 3: nvidia-smi (NVIDIA GPUs)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode().strip()
        lines = [l.strip() for l in out.split("\n") if l.strip()]
        if lines:
            parts = lines[0].split(",")
            info["gpu_name"] = parts[0].strip()
            info["gpu_driver"] = parts[1].strip() if len(parts) > 1 else None
            info["gpu_count"] = len(lines)
            return info
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("nvidia-smi not available")
    except Exception as e:
        logger.debug(f"nvidia-smi failed: {e}")

    # Strategy 4: sysfs (Linux — count GPU vendor IDs and map device IDs)
    try:
        import glob as glob_mod
        amd_device_names = {
            "0x74a1": "AMD Instinct MI300X",
            "0x74a0": "AMD Instinct MI300A",
            "0x7408": "AMD Instinct MI250X",
            "0x740c": "AMD Instinct MI250",
            "0x738c": "AMD Instinct MI100",
            "0x744c": "AMD Radeon RX 7900 XTX",
            "0x7448": "AMD Radeon RX 7900 XT",
        }
        cards = glob_mod.glob("/sys/class/drm/card*/device/vendor")
        amd_count = 0
        amd_name = None
        for p in cards:
            with open(p) as f:
                vendor = f.read().strip()
            if vendor == "0x1002":  # AMD
                amd_count += 1
                if not amd_name:
                    dev_path = p.replace("vendor", "device")
                    try:
                        with open(dev_path) as f:
                            dev_id = f.read().strip()
                        amd_name = amd_device_names.get(dev_id)
                    except Exception:
                        pass
        nv_count = sum(1 for p in cards if open(p).read().strip() == "0x10de")
        if amd_count > 0:
            info["gpu_count"] = amd_count
            info["gpu_name"] = amd_name or f"AMD GPU (x{amd_count})"
        elif nv_count > 0:
            info["gpu_count"] = nv_count
            info["gpu_name"] = f"NVIDIA GPU (x{nv_count})"
    except Exception as e:
        logger.debug(f"sysfs GPU detection failed: {e}")

    return info


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception as e:
        logger.debug(f"git SHA unavailable (not a git repo?): {e}")
        return None


def _git_branch() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception as e:
        logger.debug(f"git branch unavailable: {e}")
        return None


def _git_diff_hash() -> str | None:
    """Hash of uncommitted changes (None if clean)."""
    try:
        diff = subprocess.check_output(
            ["git", "diff", "HEAD"], stderr=subprocess.DEVNULL
        ).decode()
        if not diff.strip():
            return None
        return hashlib.sha256(diff.encode()).hexdigest()
    except Exception as e:
        logger.debug(f"git diff hash unavailable: {e}")
        return None


def _pip_freeze() -> str:
    try:
        return subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze", "--local"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception as e:
        logger.debug(f"pip freeze failed: {e}")
        return ""


def _cpu_model() -> str:
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        return platform.processor() or "unknown"
    except Exception as e:
        logger.debug(f"CPU model detection failed: {e}")
        return platform.processor() or "unknown"


def _ram_gb() -> float | None:
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        return round(kb / (1024 * 1024), 1)
        return None
    except Exception as e:
        logger.debug(f"RAM detection failed: {e}")
        return None


def _cuda_version() -> str | None:
    try:
        import torch
        return torch.version.cuda
    except ImportError:
        # Fallback: check nvidia-smi
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                stderr=subprocess.DEVNULL, timeout=10,
            ).decode().strip()
            if out:
                return out.split("\n")[0]  # driver version as proxy
        except Exception:
            pass
        return None
    except Exception as e:
        logger.debug(f"CUDA version detection failed: {e}")
        return None


def _rocm_version() -> str | None:
    try:
        import torch
        return getattr(torch.version, "hip", None)
    except ImportError:
        # Fallback: check /opt/rocm/.info/version or rocm-smi
        try:
            with open("/opt/rocm/.info/version") as f:
                return f.read().strip()
        except Exception:
            pass
        # Check env var
        v = os.environ.get("ROCM_VERSION")
        if v:
            return v
        # Try rocm-smi version output
        try:
            out = subprocess.check_output(
                ["rocm-smi", "--version"], stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
            for line in out.split("\n"):
                if "version" in line.lower():
                    return line.split(":")[-1].strip()
        except Exception:
            pass
        return None
    except Exception as e:
        logger.debug(f"ROCm version detection failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def capture_environment() -> dict[str, Any]:
    """Capture a full environment snapshot as a dictionary."""
    gpu = _detect_gpu()
    pip = _pip_freeze()

    data = {
        "python_version": platform.python_version(),
        "pytorch_version": _safe_import_version("torch"),
        "cuda_version": _cuda_version(),
        "rocm_version": _rocm_version(),
        "transformers_version": _safe_import_version("transformers"),
        "lightcompress_version": _safe_import_version("llmc"),
        "gpu_name": gpu["gpu_name"],
        "gpu_driver": gpu["gpu_driver"],
        "gpu_count": gpu["gpu_count"],
        "cpu_model": _cpu_model(),
        "ram_gb": _ram_gb(),
        "pip_freeze": pip,
        "git_sha": _git_sha(),
        "git_branch": _git_branch(),
        "git_diff_hash": _git_diff_hash(),
    }

    # Build stable hash from key fields
    hash_fields = [
        data["python_version"] or "",
        data["pytorch_version"] or "",
        data["cuda_version"] or "",
        data["rocm_version"] or "",
        data["transformers_version"] or "",
        data["gpu_name"] or "",
        str(data["gpu_count"]),
        data["git_sha"] or "",
        data["git_diff_hash"] or "",
        pip,
    ]
    data["env_hash"] = hashlib.sha256("|".join(hash_fields).encode()).hexdigest()

    return data


def get_or_create_snapshot(db_url: str | None = None) -> int:
    """Capture environment and insert into DB if new; return snapshot id."""
    from ..db.models import EnvironmentSnapshot, get_session

    data = capture_environment()
    session = get_session(db_url)

    # Check if identical snapshot already exists
    existing = (
        session.query(EnvironmentSnapshot)
        .filter(EnvironmentSnapshot.env_hash == data["env_hash"])
        .first()
    )
    if existing:
        snap_id = existing.id
        session.close()
        logger.debug(f"Reusing environment snapshot {snap_id}")
        return snap_id

    snap = EnvironmentSnapshot(
        python_version=data["python_version"],
        pytorch_version=data["pytorch_version"],
        cuda_version=data["cuda_version"],
        rocm_version=data["rocm_version"],
        transformers_version=data["transformers_version"],
        lightcompress_version=data["lightcompress_version"],
        gpu_name=data["gpu_name"],
        gpu_driver=data["gpu_driver"],
        gpu_count=data["gpu_count"],
        cpu_model=data["cpu_model"],
        ram_gb=data["ram_gb"],
        pip_freeze=data["pip_freeze"],
        git_sha=data["git_sha"],
        git_branch=data["git_branch"],
        git_diff_hash=data["git_diff_hash"],
        env_hash=data["env_hash"],
    )
    session.add(snap)
    session.commit()
    snap_id = snap.id
    session.close()

    logger.info(f"Created environment snapshot {snap_id} (hash={data['env_hash'][:12]}...)")
    return snap_id
