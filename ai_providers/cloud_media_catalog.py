"""Catalog of cloud-based image and video generation APIs.

These are external services accessed via API key — no local download required.
Each entry includes: id, label, category, description, api_url, docs_url, pricing_note,
and tags for display in the Settings view.
"""

CLOUD_IMAGE_CATALOG: list[dict] = [

    # ── Image generation ──────────────────────────────────────────────────────
    {
        "id":            "nano-banana-pro",
        "label":         "Nano Banana Pro",
        "category":      "image",
        "provider":      "Google",
        "description":   "Google Imagen 4 — photorealistic text-to-image. Best quality available via Gemini API key. Free-tier quota included.",
        "api_url":       "https://aistudio.google.com/apikey",
        "docs_url":      "https://ai.google.dev/gemini-api/docs/image-generation",
        "pricing_note":  "Included with Gemini API quota. ~$0.04/image via paid tier.",
        "tags":          ["image", "newest", "text-rendering", "gemini"],
        "setting_key":   "gemini",  # reuses Gemini API key
    },
    {
        "id":            "openai-images",
        "label":         "OpenAI Images (GPT-Image-1)",
        "category":      "image",
        "provider":      "OpenAI",
        "description":   "OpenAI's GPT-Image-1 / DALL-E 3 — photorealistic images, strong instruction following, safe content filters. Multiple sizes and quality tiers.",
        "api_url":       "https://platform.openai.com/api-keys",
        "docs_url":      "https://platform.openai.com/docs/guides/images",
        "pricing_note":  "~$0.04–$0.08 per image depending on size/quality.",
        "tags":          ["image", "photorealistic"],
        "setting_key":   "openai",  # reuses OpenAI API key
    },
    {
        "id":            "stability-ultra",
        "label":         "Stability AI (Stable Image Ultra)",
        "category":      "image",
        "provider":      "Stability AI",
        "description":   "Stable Image Ultra — Stability AI's flagship API. Photorealism, concept art, product shots. SD3.5 Ultra under the hood.",
        "api_url":       "https://platform.stability.ai/account/keys",
        "docs_url":      "https://platform.stability.ai/docs/api-reference",
        "pricing_note":  "~$0.08/image (Ultra). Credits-based.",
        "tags":          ["image", "photorealistic", "product"],
        "setting_key":   "stability",
    },
]

CLOUD_VIDEO_CATALOG: list[dict] = [

    # ── Video generation ──────────────────────────────────────────────────────
    {
        "id":            "kling-v3",
        "label":         "Kling 3.0",
        "category":      "video",
        "provider":      "Kuaishou",
        "description":   "Kling 3.0 — unified multimodal: video + audio + lip-sync in one model. Up to 4K / 60 FPS / 15s. Text-to-video and image-to-video. Multi-shot storyboarding up to 6 scenes.",
        "api_url":       "https://app.klingai.com/global/dev",
        "docs_url":      "https://klingai.com/global/dev/document-api/apiReference/model/skillsMap",
        "pricing_note":  "Credits-based. ~0.5 credits/s standard, 1 credit/s pro.",
        "tags":          ["video", "4K", "audio", "newest", "recommended"],
        "setting_key":   "kling",
    },
    {
        "id":            "kling-v2.1",
        "label":         "Kling 2.1 Master",
        "category":      "video",
        "provider":      "Kuaishou",
        "description":   "Kling v2.1 Master — proven quality, 1080p, text/image-to-video. Cheaper than Kling 3.0.",
        "api_url":       "https://app.klingai.com/global/dev",
        "docs_url":      "https://klingai.com/global/dev/document-api/apiReference/model/skillsMap",
        "pricing_note":  "Credits-based. ~0.35 credits/s.",
        "tags":          ["video", "1080p", "balanced"],
        "setting_key":   "kling",
    },
    {
        "id":            "sora",
        "label":         "Sora (OpenAI)",
        "category":      "video",
        "provider":      "OpenAI",
        "description":   "OpenAI Sora — cinematic text-to-video up to 1080p / 20s. Strong temporal coherence and camera controls. Available via API.",
        "api_url":       "https://platform.openai.com/api-keys",
        "docs_url":      "https://platform.openai.com/docs/guides/video",
        "pricing_note":  "~$0.03/s for 480p, ~$0.07/s for 720p.",
        "tags":          ["video", "cinematic", "openai"],
        "setting_key":   "openai",  # reuses OpenAI API key
    },
    {
        "id":            "runway-gen4",
        "label":         "Runway Gen-4",
        "category":      "video",
        "provider":      "Runway",
        "description":   "Runway Gen-4 — reference-consistent video from images or text. Multi-character scene continuity. Industry standard for VFX workflows.",
        "api_url":       "https://app.runwayml.com",
        "docs_url":      "https://docs.runwayml.com",
        "pricing_note":  "Credits-based. ~$0.05–$0.10/s.",
        "tags":          ["video", "vfx", "reference-consistent"],
        "setting_key":   "runway",
    },
    {
        "id":            "luma-dream-machine",
        "label":         "Luma Dream Machine 2",
        "category":      "video",
        "provider":      "Luma AI",
        "description":   "Luma Dream Machine 2 — smooth, photorealistic video with Ray2 physics engine. Fast generation, strong camera motion.",
        "api_url":       "https://lumalabs.ai/dream-machine/api",
        "docs_url":      "https://docs.lumalabs.ai",
        "pricing_note":  "~$0.03/s for standard, ~$0.08/s for Ray2.",
        "tags":          ["video", "physics", "fast"],
        "setting_key":   "luma",
    },
    {
        "id":            "higgsfield",
        "label":         "Higgsfield AI",
        "category":      "video",
        "provider":      "Higgsfield",
        "description":   "Higgsfield — human-focused video AI. Characters, expressions, cinematography. Built-in virality predictor and marketing studio.",
        "api_url":       "https://higgsfield.ai",
        "docs_url":      "https://higgsfield.ai/docs",
        "pricing_note":  "Credits-based. See higgsfield.ai/pricing.",
        "tags":          ["video", "characters", "marketing"],
        "setting_key":   "higgsfield",
    },
]

# Combined for iteration
CLOUD_MEDIA_CATALOG: list[dict] = CLOUD_IMAGE_CATALOG + CLOUD_VIDEO_CATALOG

CLOUD_CATALOG_BY_ID: dict[str, dict] = {e["id"]: e for e in CLOUD_MEDIA_CATALOG}

# Keys that need separate API key entries (not reusing existing text providers)
CLOUD_DEDICATED_KEYS: list[str] = ["kling", "stability", "runway", "luma", "higgsfield"]

_CLOUD_CATEGORY_LABELS: dict[str, str] = {
    "image": "Cloud Image Generation",
    "video": "Cloud Video Generation",
}
