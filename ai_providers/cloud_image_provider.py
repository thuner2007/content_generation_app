"""Cloud image generation via Google Gemini / Imagen API.

Imagen models use the google-genai SDK's generate_images() with API key auth
on generativelanguage.googleapis.com — works with a free AI Studio key, no subscription.

Gemini image-gen uses generate_content() as before.

Supported models:
  nano-banana-pro   →  imagen-4.0-generate-001         (Imagen 4, best quality)
  nano-banana-fast  →  imagen-4.0-fast-generate-001    (faster / cheaper)
  gemini-imggen     →  gemini-3.1-flash-image-preview  (Nano Banana 2, editing-capable)
"""
import base64
import uuid
from pathlib import Path
from typing import Callable, Optional


CLOUD_IMAGE_MODELS: list[dict] = [
    {
        "id":          "nano-banana-pro",
        "label":       "Nano Banana Pro",
        "api_model":   "imagen-4.0-generate-001",
        "description": "Google Imagen 4 — photorealistic images, best quality. Uses your Gemini API key.",
        "tags":        ["best-quality", "photorealistic", "gemini"],
        "price_note":  "~$0.04/image (Gemini API quota)",
        "provider":    "gemini",
        "supports_ar": True,
    },
    {
        "id":          "nano-banana-fast",
        "label":       "Nano Banana Fast",
        "api_model":   "imagen-4.0-fast-generate-001",
        "description": "Google Imagen 4 Fast — quicker generation at lower cost. Good for drafts.",
        "tags":        ["fast", "gemini"],
        "price_note":  "~$0.02/image",
        "provider":    "gemini",
        "supports_ar": True,
    },
    {
        "id":          "gemini-imggen",
        "label":       "Nano Banana 2",
        "api_model":   "gemini-3.1-flash-image-preview",
        "description": "Gemini 3.1 Flash Image — Nano Banana 2. Best all-around: fast, creative, supports image editing and reference images.",
        "tags":        ["creative", "editing", "reference", "gemini"],
        "price_note":  "Gemini API quota",
        "provider":    "gemini",
        "supports_ar": False,
    },
]

CLOUD_IMAGE_BY_ID: dict[str, dict] = {m["id"]: m for m in CLOUD_IMAGE_MODELS}

_ASPECT_RATIOS = {
    "1:1":  "1:1",
    "16:9": "16:9",
    "9:16": "9:16",
    "4:3":  "4:3",
    "3:4":  "3:4",
}


def _output_dir() -> Path:
    from storage.db import get_db_path
    d = Path(get_db_path()).parent / "generated_images"
    d.mkdir(exist_ok=True)
    return d


def _get_gemini_key() -> str:
    from storage.asset_repo import get_api_key
    return (get_api_key("gemini") or "").strip()


def _imagen_sdk(api_key: str, model: str, prompt: str, aspect_ratio: str) -> bytes:
    """Generate via Imagen using the google-genai SDK (works with free AI Studio API key)."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed.\n"
            "Go to Settings and install it, or run: pip install google-genai"
        )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=_ASPECT_RATIOS.get(aspect_ratio, "1:1"),
        ),
    )
    if not response.generated_images:
        raise RuntimeError("No images returned by Imagen.")
    return response.generated_images[0].image.image_bytes


def generate_cloud_image(
    prompt: str,
    model_id: str = "nano-banana-pro",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    reference_image: Optional[bytes] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Generate (or edit) an image using a cloud provider.

    reference_image: raw image bytes to use as an editing reference.
                     Imagen models don't support editing, so they transparently
                     fall back to gemini-3.1-flash-image-preview (Nano Banana 2).
    resolution: "1K" | "2K" | "4K" | "8K"  — target longest-side pixel count.
    Returns:
        {"ok": True,  "path": str, "model": str, "provider": str}
      | {"ok": False, "error": str}
    """
    entry = CLOUD_IMAGE_BY_ID.get(model_id)
    if not entry:
        return {"ok": False, "error": f"Unknown cloud image model: {model_id!r}"}

    api_key = _get_gemini_key()
    if not api_key:
        return {
            "ok": False,
            "error": "Gemini API key not configured.\nGo to Settings → AI Provider API Keys and add your Google Gemini key.",
        }

    if on_progress:
        on_progress(f"Sending to {entry['label']}…")

    try:
        api_model = entry["api_model"]

        # Imagen models don't support editing — transparently fall back to Gemini imggen
        if reference_image and api_model.startswith("imagen-"):
            api_model = "gemini-3.1-flash-image-preview"

        if api_model.startswith("imagen-"):
            try:
                img_bytes = _imagen_sdk(api_key, api_model, prompt, aspect_ratio)
            except Exception as _imagen_exc:
                _e = str(_imagen_exc)
                # Imagen requires billing; fall back to Gemini native image generation
                if any(k in _e for k in ("NOT_FOUND", "404", "PERMISSION_DENIED", "403", "not found")):
                    if on_progress:
                        on_progress("Imagen unavailable — falling back to Gemini image generation…")
                    api_model = "gemini-3.1-flash-image-preview"
                    img_bytes = None  # handled below in the else branch
                else:
                    raise

        if not api_model.startswith("imagen-"):
            # gemini-3.1-flash-image-preview — native or fallback from Imagen
            try:
                from google import genai
                from google.genai import types
            except ImportError:
                return {
                    "ok": False,
                    "error": "google-genai package not installed.\nInstall it in Settings.",
                }
            client = genai.Client(api_key=api_key)

            # Build contents: prepend reference image if provided
            if reference_image:
                contents: list = [
                    types.Part.from_bytes(data=reference_image, mime_type="image/png"),
                    prompt,
                ]
            else:
                contents = prompt

            response = client.models.generate_content(
                model=api_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["Text", "Image"],
                ),
            )
            img_bytes = None
            for part in response.candidates[0].content.parts:
                if getattr(part, 'thought', False):  # skip intermediate thinking images
                    continue
                if part.inline_data:
                    img_bytes = part.inline_data.data  # SDK already decodes from base64
                    break
            if not img_bytes:
                return {"ok": False, "error": "No image returned by the model."}

        filename = f"img_{uuid.uuid4().hex[:12]}.png"
        path     = _output_dir() / filename
        path.write_bytes(img_bytes)

        # Upscale / downscale to requested resolution (target longest side in px)
        _RES_TARGETS = {"1K": 1024, "2K": 2048, "4K": 4096, "8K": 8192}
        target_px = _RES_TARGETS.get(resolution, 1024)
        try:
            from PIL import Image as _PILImage
            from io import BytesIO as _BytesIO
            img = _PILImage.open(_BytesIO(img_bytes))
            w, h = img.size
            long_side = max(w, h)
            if abs(long_side - target_px) > 32:  # only resize if meaningfully different
                scale = target_px / long_side
                new_w = max(8, int(round(w * scale / 8) * 8))
                new_h = max(8, int(round(h * scale / 8) * 8))
                resample = _PILImage.LANCZOS if scale < 1 else _PILImage.BICUBIC
                img = img.resize((new_w, new_h), resample)
                img.save(str(path), "PNG")
        except Exception:
            pass  # keep original if PIL fails

        if on_progress:
            on_progress("Done ✓")

        return {
            "ok":       True,
            "path":     str(path),
            "model":    model_id,
            "provider": "gemini",
            "label":    entry["label"],
        }

    except Exception as exc:
        err = str(exc)
        if "API_KEY_INVALID" in err or "invalid api key" in err.lower():
            return {"ok": False, "error": "Gemini API key is invalid. Check Settings."}
        if "PERMISSION_DENIED" in err or "403" in err:
            return {
                "ok": False,
                "error": (
                    "Access denied (403). Possible causes:\n"
                    "• Imagen is blocked in your region\n"
                    "• Your GCP project has the Gemini API disabled — "
                    "enable it at console.cloud.google.com → APIs & Services"
                ),
            }
        if "RESOURCE_EXHAUSTED" in err or "429" in err:
            return {"ok": False, "error": "Gemini API quota exceeded. Try again later."}
        if "NOT_FOUND" in err or "404" in err or "not found" in err.lower():
            return {
                "ok": False,
                "error": (
                    f"Model not found ({api_model}).\n\n"
                    "Imagen 4 requires billing to be enabled on your Google Cloud project. "
                    "Your API key is free, but the GCP project it belongs to needs billing turned on.\n\n"
                    "Fix: go to console.cloud.google.com → Billing → link a billing account "
                    "to your project. You won't be charged within the free quota."
                ),
            }
        return {"ok": False, "error": err}
