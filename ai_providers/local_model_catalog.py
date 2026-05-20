"""Catalog of recommended downloadable Ollama models.

Each entry fields:
  id          – ollama pull name
  label       – display name
  size_gb     – approximate download size
  description – one-liner shown in settings
  tags        – small chips shown in the card
  category    – "vision" | "chat" | "reasoning" | "code"
  vision      – True if the model accepts image inputs
"""

CATALOG: list[dict] = [

    # ── Vision models ──────────────────────────────────────────────────────────
    {
        "id":          "moondream",
        "label":       "Moondream",
        "size_gb":     1.7,
        "description": "Tiny 2B vision model. Describes images, answers visual questions.",
        "tags":        ["tiny", "fast"],
        "category":    "vision",
        "vision":      True,
    },
    {
        "id":          "llava-phi3",
        "label":       "LLaVA Phi-3",
        "size_gb":     2.9,
        "description": "Microsoft Phi-3 + vision encoder. Compact model that understands images.",
        "tags":        ["fast", "recommended"],
        "category":    "vision",
        "vision":      True,
    },
    {
        "id":          "llava:7b",
        "label":       "LLaVA 7B",
        "size_gb":     4.7,
        "description": "Most popular open-source vision model. Detailed image analysis.",
        "tags":        ["balanced"],
        "category":    "vision",
        "vision":      True,
    },
    {
        "id":          "minicpm-v",
        "label":       "MiniCPM-V",
        "size_gb":     5.5,
        "description": "Strong multimodal model with OCR. Good at reading text in images.",
        "tags":        ["ocr", "balanced"],
        "category":    "vision",
        "vision":      True,
    },
    {
        "id":          "llava:13b",
        "label":       "LLaVA 13B",
        "size_gb":     8.0,
        "description": "Larger vision model for detailed scene understanding.",
        "tags":        ["quality"],
        "category":    "vision",
        "vision":      True,
    },

    # ── Chat & writing ─────────────────────────────────────────────────────────
    {
        "id":          "llama3.2:1b",
        "label":       "Llama 3.2 1B",
        "size_gb":     0.8,
        "description": "Tiny but capable. Ideal for low-RAM machines.",
        "tags":        ["tiny", "fast"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "llama3.2:3b",
        "label":       "Llama 3.2 3B",
        "size_gb":     2.0,
        "description": "Meta's fast 3B model. Great for chat and quick tasks.",
        "tags":        ["fast", "recommended"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "llama3.1:8b",
        "label":       "Llama 3.1 8B",
        "size_gb":     4.7,
        "description": "Meta's balanced 8B model. Strong reasoning and writing.",
        "tags":        ["balanced"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "gemma3:1b",
        "label":       "Gemma 3 1B",
        "size_gb":     0.8,
        "description": "Google's smallest model. Very fast on any hardware.",
        "tags":        ["tiny", "fast"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "gemma3:4b",
        "label":       "Gemma 3 4B",
        "size_gb":     3.3,
        "description": "Google's efficient 4B model. Good all-around performance.",
        "tags":        ["balanced", "recommended"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "gemma3:12b",
        "label":       "Gemma 3 12B",
        "size_gb":     8.1,
        "description": "Google's larger Gemma. Higher quality responses and stronger reasoning.",
        "tags":        ["quality"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "mistral:7b",
        "label":       "Mistral 7B",
        "size_gb":     4.1,
        "description": "Excellent for instruction following and writing tasks.",
        "tags":        ["balanced"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "mistral-nemo",
        "label":       "Mistral Nemo 12B",
        "size_gb":     7.1,
        "description": "Mistral's 12B model with a large 128k context window.",
        "tags":        ["quality", "long-context"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "phi4-mini:3.8b",
        "label":       "Phi-4 Mini 3.8B",
        "size_gb":     2.5,
        "description": "Microsoft's compact powerhouse. Punches well above its size.",
        "tags":        ["fast", "recommended"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "phi4:14b",
        "label":       "Phi-4 14B",
        "size_gb":     8.9,
        "description": "Microsoft's flagship local model. State-of-the-art quality.",
        "tags":        ["quality"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "qwen2.5:3b",
        "label":       "Qwen 2.5 3B",
        "size_gb":     2.0,
        "description": "Fast 3B with multilingual capabilities.",
        "tags":        ["fast", "multilingual"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "qwen2.5:7b",
        "label":       "Qwen 2.5 7B",
        "size_gb":     4.7,
        "description": "Alibaba's strong 7B model. Great multilingual support.",
        "tags":        ["balanced", "multilingual"],
        "category":    "chat",
        "vision":      False,
    },
    {
        "id":          "qwen2.5:14b",
        "label":       "Qwen 2.5 14B",
        "size_gb":     9.0,
        "description": "Alibaba's 14B model. High quality multilingual text generation.",
        "tags":        ["quality", "multilingual"],
        "category":    "chat",
        "vision":      False,
    },

    # ── Reasoning ─────────────────────────────────────────────────────────────
    {
        "id":          "deepseek-r1:7b",
        "label":       "DeepSeek R1 7B",
        "size_gb":     4.7,
        "description": "Strong reasoning model. Ideal for analytical and logic tasks.",
        "tags":        ["balanced"],
        "category":    "reasoning",
        "vision":      False,
    },
    {
        "id":          "deepseek-r1:14b",
        "label":       "DeepSeek R1 14B",
        "size_gb":     9.0,
        "description": "Larger reasoning model. Handles complex multi-step problems.",
        "tags":        ["quality"],
        "category":    "reasoning",
        "vision":      False,
    },
    {
        "id":          "qwq",
        "label":       "QwQ 32B",
        "size_gb":     20.0,
        "description": "Alibaba's advanced reasoning model. Near GPT-o1 quality thinking.",
        "tags":        ["quality", "reasoning"],
        "category":    "reasoning",
        "vision":      False,
    },

    # ── Code ──────────────────────────────────────────────────────────────────
    {
        "id":          "codellama:7b",
        "label":       "Code Llama 7B",
        "size_gb":     3.8,
        "description": "Meta's code model. Strong at generation, completion, and explanation.",
        "tags":        ["balanced"],
        "category":    "code",
        "vision":      False,
    },
    {
        "id":          "qwen2.5-coder:7b",
        "label":       "Qwen 2.5 Coder 7B",
        "size_gb":     4.7,
        "description": "State-of-the-art coding model. Outperforms CodeLlama on most benchmarks.",
        "tags":        ["balanced", "recommended"],
        "category":    "code",
        "vision":      False,
    },
    {
        "id":          "devstral",
        "label":       "Devstral",
        "size_gb":     14.0,
        "description": "Mistral's agentic coding model. Built for multi-file coding tasks.",
        "tags":        ["quality", "agentic"],
        "category":    "code",
        "vision":      False,
    },
]

# Convenience lookup
CATALOG_BY_ID: dict[str, dict] = {e["id"]: e for e in CATALOG}

_CATEGORY_META: dict[str, dict] = {
    "vision":    {"label": "Vision Models",    "icon": "image",    "desc": "These models can analyze images you attach to the chat"},
    "chat":      {"label": "Chat & Writing",   "icon": "chat",     "desc": "General-purpose models for conversation and content creation"},
    "reasoning": {"label": "Reasoning",        "icon": "thinking", "desc": "Models optimized for logic, analysis, and step-by-step thinking"},
    "code":      {"label": "Code",             "icon": "code",     "desc": "Models trained specifically for programming tasks"},
}

CATEGORY_ORDER = ["vision", "chat", "reasoning", "code"]
