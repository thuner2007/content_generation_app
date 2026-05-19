"""Catalog of recommended downloadable Ollama models."""

# Each entry: id (ollama pull name), label, size_gb, description, tags
CATALOG: list[dict] = [
    {
        "id": "llama3.2:3b",
        "label": "Llama 3.2 3B",
        "size_gb": 2.0,
        "description": "Meta's fast 3B model. Great for chat and quick tasks.",
        "tags": ["fast", "chat", "recommended"],
    },
    {
        "id": "llama3.2:1b",
        "label": "Llama 3.2 1B",
        "size_gb": 0.8,
        "description": "Tiny but capable. Ideal for low-RAM machines.",
        "tags": ["tiny", "fast"],
    },
    {
        "id": "llama3.1:8b",
        "label": "Llama 3.1 8B",
        "size_gb": 4.7,
        "description": "Meta's balanced 8B model. Strong reasoning and writing.",
        "tags": ["balanced", "chat"],
    },
    {
        "id": "mistral:7b",
        "label": "Mistral 7B",
        "size_gb": 4.1,
        "description": "Excellent for instruction following and writing tasks.",
        "tags": ["writing", "balanced"],
    },
    {
        "id": "gemma3:4b",
        "label": "Gemma 3 4B",
        "size_gb": 3.3,
        "description": "Google's efficient 4B model. Good all-around performance.",
        "tags": ["balanced", "recommended"],
    },
    {
        "id": "gemma3:1b",
        "label": "Gemma 3 1B",
        "size_gb": 0.8,
        "description": "Google's smallest model. Very fast on any hardware.",
        "tags": ["tiny", "fast"],
    },
    {
        "id": "phi4-mini:3.8b",
        "label": "Phi-4 Mini 3.8B",
        "size_gb": 2.5,
        "description": "Microsoft's compact powerhouse. Punches above its size.",
        "tags": ["fast", "recommended"],
    },
    {
        "id": "qwen2.5:7b",
        "label": "Qwen 2.5 7B",
        "size_gb": 4.7,
        "description": "Alibaba's strong 7B model. Great multilingual support.",
        "tags": ["multilingual", "balanced"],
    },
    {
        "id": "qwen2.5:3b",
        "label": "Qwen 2.5 3B",
        "size_gb": 2.0,
        "description": "Fast 3B with multilingual capabilities.",
        "tags": ["fast", "multilingual"],
    },
    {
        "id": "deepseek-r1:7b",
        "label": "DeepSeek R1 7B",
        "size_gb": 4.7,
        "description": "Strong reasoning model. Ideal for analytical tasks.",
        "tags": ["reasoning", "balanced"],
    },
    {
        "id": "codellama:7b",
        "label": "Code Llama 7B",
        "size_gb": 3.8,
        "description": "Optimized for code generation and explanation.",
        "tags": ["code"],
    },
]
