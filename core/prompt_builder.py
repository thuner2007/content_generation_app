"""Build context-aware prompts by injecting project brand data."""
from typing import Optional

from storage.models import Project, Message

# ── Generation type system prompts ─────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "You are an expert marketing AI assistant. "
        "Help the user create compelling content for their brand."
    ),
    "ad_copy": (
        "You are a world-class direct-response copywriter specialising in digital ads. "
        "Generate persuasive, benefit-driven ad copy. "
        "Structure your output clearly with: Headline, Primary Text, and CTA. "
        "Make multiple variations if not specified otherwise."
    ),
    "image_prompt": (
        "You are an expert at writing image generation prompts for AI tools like Midjourney, "
        "DALL-E, and Stable Diffusion. "
        "Output highly detailed, specific prompts that result in professional ad-quality images. "
        "Include: subject, style, lighting, composition, color palette, aspect ratio."
    ),
    "video_prompt": (
        "You are an expert at writing video generation prompts for AI tools like Kling, Sora, "
        "and Runway. "
        "Output cinematic, detailed prompts that describe camera movement, scene, mood, lighting, "
        "and the story being told. Each prompt should be 3-5 sentences."
    ),
    "bulk": (
        "You are a performance marketing creative director. "
        "Generate exactly 10 distinct ad variations optimised for A/B testing. "
        "Number each variation. Vary the angle, hook, and CTA across variations. "
        "Format: ## Variation N\\n[content]"
    ),
    "product_ideas": (
        "You are a growth-focused product marketing strategist. "
        "Generate creative, actionable marketing ideas for the product. "
        "Include angles: pain point, aspiration, social proof, urgency, value-stack."
    ),
}


def build_messages(
    user_input: str,
    history: list[Message],
    project: Optional[Project] = None,
    generation_type: str = "chat",
    file_context: str = "",
) -> list[dict]:
    """
    Build the full messages list to send to the AI.
    Returns [{'role': ..., 'content': ...}, ...]
    """
    system = _build_system_message(project, generation_type, file_context)
    messages: list[dict] = [{"role": "system", "content": system}]

    # Add recent conversation history (last 20 turns to stay within context limits)
    for msg in history[-20:]:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_input})
    return messages


def _build_system_message(
    project: Optional[Project],
    generation_type: str,
    file_context: str,
) -> str:
    base = _SYSTEM_PROMPTS.get(generation_type, _SYSTEM_PROMPTS["chat"])

    if project:
        brand_section = _format_brand_context(project)
        system = f"{base}\n\n{brand_section}"
    else:
        system = base

    if file_context:
        system += f"\n\n## Reference Documents\n{file_context}"

    return system


def _format_brand_context(project: Project) -> str:
    lines = [f"## Brand Context: {project.name}"]
    if project.slogan:
        lines.append(f"- Slogan: {project.slogan}")
    if project.description:
        lines.append(f"- Description: {project.description}")
    if project.brand_colors:
        lines.append(f"- Brand Colors: {project.brand_colors}")
    if project.fonts:
        lines.append(f"- Fonts: {project.fonts}")
    if project.legal_info:
        lines.append(f"- Legal / Disclaimers: {project.legal_info}")
    lines.append(
        "Always align all content with this brand identity. "
        "Maintain consistent tone, style, and messaging."
    )
    return "\n".join(lines)


def estimate_token_count(text: str) -> int:
    """Rough estimate: ~4 chars per token."""
    return max(1, len(text) // 4)
