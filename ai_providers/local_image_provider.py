"""Local image generation using HuggingFace diffusers.

Models are downloaded once from HuggingFace Hub and stored locally.
Generation runs fully offline after download — no external servers needed.

Required packages (install once):
    pip install diffusers transformers accelerate torch Pillow huggingface_hub
"""
import shutil
import threading
import uuid
from pathlib import Path
from typing import Callable, Optional


# ── Model catalog ─────────────────────────────────────────────────────────────
# Top open-weight image generation models available on HuggingFace (2026).
# pipeline_cls  → diffusers class name for AutoPipelineForText2Image to load
# hf_gated      → True if the HF repo requires a token (free account, no payment)

IMAGE_MODEL_CATALOG: list[dict] = [

    # ── Tier: High ────────────────────────────────────────────────────────────
    {
        "id":            "flux2-klein-4b",
        "label":         "FLUX.2 [klein] 4B",
        "repo_id":       "black-forest-labs/FLUX.2-klein-4B",
        "pipeline_cls":  "Flux2Pipeline",
        "size_gb":       13.0,
        "vram_gb":       12,
        "description":   "Black Forest Labs' newest compact model (Jan 2026). Sub-second generation on RTX 3090+. Apache 2.0, no login.",
        "tags":          ["newest", "fast", "apache", "no-login"],
        "tier":          "high",
        "steps_default": 4,
        "cfg_default":   0.0,
        "hf_gated":      False,
        "install_note":  "",
    },
    {
        "id":            "flux2-klein-9b",
        "label":         "FLUX.2 [klein] 9B",
        "repo_id":       "black-forest-labs/FLUX.2-klein-9B",
        "pipeline_cls":  "Flux2Pipeline",
        "size_gb":       20.0,
        "vram_gb":       24,
        "description":   "Larger FLUX.2 Klein — premium quality with fast inference. Requires RTX 3090/4090 (24 GB VRAM).",
        "tags":          ["newest", "best-quality"],
        "tier":          "high",
        "steps_default": 4,
        "cfg_default":   0.0,
        "hf_gated":      True,
        "install_note":  "Requires HuggingFace token + accepted license at hf.co/black-forest-labs/FLUX.2-klein-9B",
    },
    {
        "id":            "flux1-schnell",
        "label":         "FLUX.1 Schnell",
        "repo_id":       "black-forest-labs/FLUX.1-schnell",
        "pipeline_cls":  "FluxPipeline",
        "size_gb":       24.0,
        "vram_gb":       12,
        "description":   "Black Forest Labs' proven fast FLUX. 4-step generation, excellent quality. Apache 2.0.",
        "tags":          ["fast", "apache"],
        "tier":          "high",
        "steps_default": 4,
        "cfg_default":   0.0,
        "hf_gated":      True,
        "install_note":  "Requires free HuggingFace account + accepted license at hf.co/black-forest-labs/FLUX.1-schnell",
    },
    {
        "id":            "flux1-dev",
        "label":         "FLUX.1 Dev",
        "repo_id":       "black-forest-labs/FLUX.1-dev",
        "pipeline_cls":  "FluxPipeline",
        "size_gb":       24.0,
        "vram_gb":       16,
        "description":   "FLUX.1 Dev — 12B DiT, gold standard for photorealism and text rendering. Non-commercial.",
        "tags":          ["best-quality", "photorealistic"],
        "tier":          "high",
        "steps_default": 25,
        "cfg_default":   3.5,
        "hf_gated":      True,
        "install_note":  "Requires HuggingFace token + accepted license at hf.co/black-forest-labs/FLUX.1-dev",
    },

    # ── Tier: Mid ─────────────────────────────────────────────────────────────
    {
        "id":            "sd35-medium",
        "label":         "Stable Diffusion 3.5 Medium",
        "repo_id":       "stabilityai/stable-diffusion-3.5-medium",
        "pipeline_cls":  "StableDiffusion3Pipeline",
        "size_gb":       5.5,
        "vram_gb":       8,
        "description":   "Stability AI's accessible SD3.5. 2.5B MMDiT, good prompt adherence. Runs on 8 GB VRAM.",
        "tags":          ["balanced", "accessible"],
        "tier":          "mid",
        "steps_default": 28,
        "cfg_default":   4.5,
        "hf_gated":      True,
        "install_note":  "Requires HuggingFace token",
    },
    {
        "id":            "sdxl",
        "label":         "Stable Diffusion XL",
        "repo_id":       "stabilityai/stable-diffusion-xl-base-1.0",
        "pipeline_cls":  "StableDiffusionXLPipeline",
        "size_gb":       6.7,
        "vram_gb":       8,
        "description":   "SDXL 1.0. Apache 2.0. Massive LoRA/fine-tune ecosystem. No login required.",
        "tags":          ["balanced", "ecosystem", "no-login"],
        "tier":          "mid",
        "steps_default": 30,
        "cfg_default":   7.5,
        "hf_gated":      False,
        "install_note":  "",
    },

    # ── Tier: Base ────────────────────────────────────────────────────────────
    {
        "id":            "sd15",
        "label":         "Stable Diffusion 1.5",
        "repo_id":       "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "pipeline_cls":  "StableDiffusionPipeline",
        "size_gb":       4.0,
        "vram_gb":       4,
        "description":   "Classic SD 1.5. 4 GB download, 4 GB VRAM, thousands of fine-tunes. No login required.",
        "tags":          ["lightweight", "fast", "no-login"],
        "tier":          "base",
        "steps_default": 30,
        "cfg_default":   7.5,
        "hf_gated":      False,
        "install_note":  "",
    },
]

IMAGE_CATALOG_BY_ID: dict[str, dict] = {e["id"]: e for e in IMAGE_MODEL_CATALOG}

_TIER_LABELS = {
    "high": "High Tier",
    "mid":  "Mid Tier",
    "base": "Base Tier",
}


# ── Paths ─────────────────────────────────────────────────────────────────────

def _models_dir() -> Path:
    from storage.db import get_db_path
    d = Path(get_db_path()).parent / "image_models"
    d.mkdir(exist_ok=True)
    return d


def _output_dir() -> Path:
    from storage.db import get_db_path
    d = Path(get_db_path()).parent / "generated_images"
    d.mkdir(exist_ok=True)
    return d


def model_local_path(model_id: str) -> Path:
    return _models_dir() / model_id


# ── Install state ─────────────────────────────────────────────────────────────

def is_installed(model_id: str) -> bool:
    p = model_local_path(model_id)
    if not p.exists():
        return False
    # A model directory is considered complete if it has at least one .safetensors or .bin file
    return any(
        f.suffix in (".safetensors", ".bin", ".gguf", ".pt")
        for f in p.rglob("*")
        if f.is_file()
    )


def get_installed_models() -> list[str]:
    return [e["id"] for e in IMAGE_MODEL_CATALOG if is_installed(e["id"])]


# ── Download ──────────────────────────────────────────────────────────────────

def download_model(
    model_id: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> bool:
    """Download model from HuggingFace Hub into the local models directory."""
    entry = IMAGE_CATALOG_BY_ID.get(model_id)
    if not entry:
        if on_progress:
            on_progress(f"Unknown model: {model_id}")
        return False

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        if on_progress:
            on_progress("huggingface_hub not installed. Run: pip install huggingface_hub")
        return False

    dest = model_local_path(model_id)
    dest.mkdir(parents=True, exist_ok=True)

    hf_token = _get_hf_token()
    repo_id  = entry["repo_id"]

    if on_progress:
        on_progress("Connecting to HuggingFace…")

    expected_gb = entry.get("size_gb", 0)
    _stop = threading.Event()

    def _monitor():
        """Poll dest folder size every 2 s and report progress."""
        while not _stop.wait(2.0):
            try:
                total = sum(
                    f.stat().st_size
                    for f in dest.rglob("*")
                    if f.is_file() and f.suffix != ".lock"
                )
                gb = total / (1024 ** 3)
                if gb < 0.01:
                    continue
                if expected_gb and expected_gb > 0:
                    pct = min(99, int(gb / expected_gb * 100))
                    bar_filled = pct // 5          # 0-19 blocks
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)
                    msg = f"[{bar}] {pct}%  ({gb:.1f} / {expected_gb:.0f} GB)"
                else:
                    msg = f"Downloading… {gb:.1f} GB"
                if on_progress:
                    on_progress(msg)
            except Exception:
                pass

    monitor = threading.Thread(target=_monitor, daemon=True)
    monitor.start()

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(dest),
            token=hf_token or None,
            ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "rust_model*", "tf_model*"],
        )
        _stop.set()
        if on_progress:
            on_progress("Download complete ✓")
        return True
    except Exception as exc:
        _stop.set()
        err = str(exc)
        if "401" in err or "403" in err or "token" in err.lower():
            if on_progress:
                on_progress("Access denied — add your HuggingFace token in settings above")
        elif "gated" in err.lower() or "license" in err.lower():
            if on_progress:
                on_progress("Model is gated — accept license on huggingface.co first, then re-download")
        else:
            if on_progress:
                on_progress(f"Download failed: {exc}")
        # Clean up partial download
        try:
            if dest.exists():
                shutil.rmtree(dest)
        except Exception:
            pass
        return False


def delete_model(model_id: str) -> bool:
    """Delete a downloaded model from disk."""
    path = model_local_path(model_id)
    try:
        if path.exists():
            shutil.rmtree(path)
        return True
    except Exception:
        return False


# ── Pipeline cache ────────────────────────────────────────────────────────────

_pipeline_cache: dict[str, object] = {}  # model_id → loaded pipeline


def _get_hf_token() -> str:
    from storage.settings_repo import get_setting
    return get_setting("imggen_hf_token", "").strip()


def _get_pipeline(model_id: str, entry: dict):
    """Load (and cache) the diffusers pipeline for a model."""
    if model_id in _pipeline_cache:
        return _pipeline_cache[model_id]

    try:
        import torch
        from diffusers import (
            AutoPipelineForText2Image,
            FluxPipeline,
            StableDiffusion3Pipeline,
            StableDiffusionXLPipeline,
            StableDiffusionPipeline,
        )
        # Flux2Pipeline available in diffusers ≥ 0.32; import best-effort
        try:
            from diffusers import Flux2Pipeline  # noqa: F401
        except ImportError:
            pass
    except ImportError as e:
        raise RuntimeError(
            f"Required package missing: {e}\n"
            "Install with: pip install diffusers transformers accelerate torch"
        ) from e

    # Evict the cached pipeline if a different model was loaded (save VRAM)
    if _pipeline_cache:
        evicted = next(iter(_pipeline_cache))
        del _pipeline_cache[evicted]

    local_path = str(model_local_path(model_id))

    # Device + dtype selection
    if torch.cuda.is_available():
        device = "cuda"
        dtype  = torch.float16
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
        dtype  = torch.float16
    else:
        device = "cpu"
        dtype  = torch.float32

    pipe = AutoPipelineForText2Image.from_pretrained(
        local_path,
        torch_dtype=dtype,
        use_safetensors=True,
    )
    pipe = pipe.to(device)

    # Memory optimizations
    try:
        pipe.enable_attention_slicing()
    except Exception:
        pass

    _pipeline_cache[model_id] = pipe
    return pipe


# ── Generation ────────────────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    model_id: Optional[str] = None,
    width: int = 768,
    height: int = 768,
    steps: Optional[int] = None,
    cfg: Optional[float] = None,
    on_progress=None,
    stop_event=None,
) -> dict:
    """
    Generate an image locally using a downloaded diffusers model.
    Returns {"ok": True, "path": str, "model": str}
          | {"ok": False, "error": str}
          | {"ok": False, "error": "Cancelled"}
    on_progress: callable(str) — called with a progress bar string on each step
    stop_event:  threading.Event — set it to interrupt generation
    """
    import time as _time

    # Pick the model to use
    if not model_id:
        installed = get_installed_models()
        if not installed:
            return {
                "ok": False,
                "error": (
                    "No image model installed.\n"
                    "Go to Settings → Local Image Models and download a model first."
                ),
            }
        model_id = installed[0]

    entry = IMAGE_CATALOG_BY_ID.get(model_id)
    if not entry:
        return {"ok": False, "error": f"Unknown model ID: {model_id!r}"}

    if not is_installed(model_id):
        return {
            "ok": False,
            "error": (
                f"{entry['label']} is not installed.\n"
                "Download it in Settings → Local Image Models."
            ),
        }

    if steps is None:
        steps = entry.get("steps_default", 25)
    if cfg is None:
        cfg = entry.get("cfg_default", 7.0)

    _step_times: list[float] = []
    _t_last = [_time.time()]

    def _callback(pipe, step_idx, timestep, callback_kwargs):
        now = _time.time()
        elapsed = now - _t_last[0]
        _t_last[0] = now
        if step_idx > 0:
            _step_times.append(elapsed)

        done = step_idx + 1
        pct = int(done / steps * 100)
        bar_filled = pct // 5
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        if _step_times:
            avg = sum(_step_times[-5:]) / len(_step_times[-5:])
            eta_s = avg * (steps - done)
            eta_str = f"~{int(eta_s)}s left" if eta_s < 60 else f"~{int(eta_s / 60)}m left"
        else:
            eta_str = "estimating…"

        if on_progress:
            on_progress(f"[{bar}] {pct}%  {eta_str}")

        if stop_event and stop_event.is_set():
            pipe._interrupt = True

        return callback_kwargs

    try:
        pipe = _get_pipeline(model_id, entry)

        gen_kwargs: dict = {
            "prompt":                prompt,
            "width":                 width,
            "height":                height,
            "num_inference_steps":   steps,
            "callback_on_step_end":  _callback,
        }
        # FLUX Schnell is guidance-free (cfg = 0); skip the param when not needed
        if cfg > 0:
            gen_kwargs["guidance_scale"] = cfg

        result = pipe(**gen_kwargs)

        if stop_event and stop_event.is_set():
            return {"ok": False, "error": "Cancelled"}

        image = result.images[0]

        filename = f"img_{uuid.uuid4().hex[:12]}.png"
        path = _output_dir() / filename
        image.save(str(path))

        return {"ok": True, "path": str(path), "model": model_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Settings helpers ──────────────────────────────────────────────────────────

def get_imggen_settings() -> dict:
    from storage.settings_repo import get_setting
    return {
        "model_id": get_setting("imggen_model", ""),
        "steps":    int(get_setting("imggen_steps", "25")),
        "width":    int(get_setting("imggen_width", "768")),
        "height":   int(get_setting("imggen_height", "768")),
        "cfg":      float(get_setting("imggen_cfg", "7.0")),
    }


def check_deps() -> dict:
    """Return availability of required packages."""
    results = {}
    for pkg in ("torch", "diffusers", "transformers", "accelerate", "huggingface_hub"):
        try:
            __import__(pkg)
            results[pkg] = True
        except ImportError:
            results[pkg] = False
    return results


def get_gpu_info() -> dict:
    """Detect primary GPU name and VRAM.

    Returns dict with keys:
      name     – human-readable GPU name
      vram_gb  – total VRAM in GB (float), or 0.0 for CPU-only
      device   – 'cuda' | 'mps' | 'cpu'
    """
    # ── CUDA via torch ────────────────────────────────────────────────────────
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "name":    props.name,
                "vram_gb": round(props.total_memory / (1024 ** 3), 1),
                "device":  "cuda",
            }
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # Apple Silicon — shared memory; try to read it, fall back to None
            vram = _mps_vram_gb()
            return {"name": "Apple Silicon GPU", "vram_gb": vram, "device": "mps"}
    except ImportError:
        pass

    # ── CUDA via nvidia-smi (torch not installed) ─────────────────────────────
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
        )
        if r.returncode == 0:
            line = r.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2:
                return {
                    "name":    parts[0],
                    "vram_gb": round(int(parts[1]) / 1024, 1),
                    "device":  "cuda",
                }
    except Exception:
        pass

    return {"name": "No GPU detected", "vram_gb": 0.0, "device": "cpu"}


def _mps_vram_gb() -> Optional[float]:
    """Best-effort read of total GPU memory on Apple Silicon via system_profiler."""
    try:
        import subprocess, re
        r = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=5,
        )
        m = re.search(r"VRAM.*?:\s*(\d+)\s*MB", r.stdout, re.IGNORECASE)
        if m:
            return round(int(m.group(1)) / 1024, 1)
    except Exception:
        pass
    return None
