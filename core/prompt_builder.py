"""Build context-aware prompts by injecting project brand data."""
import json
from typing import Optional

from storage.models import Project, Message

# ── Generation type system prompts ─────────────────────────────────────────────

_NO_PREAMBLE = (
    "Never acknowledge the task type, explain what you are about to do, or add meta-commentary. "
    "Output the result directly."
)

# Prepended to the user message sent to the AI (not shown in the UI bubble)
_TYPE_INSTRUCTION: dict[str, str] = {
    "ad_copy":       "Write compelling ad copy for the following product/topic:",
    "image_prompt":  "Write a detailed AI image generation prompt for the following:",
    "video_prompt":  "Write a cinematic AI video generation prompt for the following:",
    "bulk":          "Generate 10 distinct ad copy variations for the following product/topic:",
    "product_ideas": "Generate concrete product ideas (variants, bundles, accessories, use-case expansions) for the following:",
}

_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "You are a professional marketing consultant and copywriter inside a content generation studio. "
        "Your job is to help entrepreneurs and businesses craft ad campaigns, brand messaging, and marketing strategy. "
        "When the user asks for help defining their ideal customer profile, USP, product benefits, pain points, "
        "tone of voice, campaign goals, or any other marketing brief field, interview them with one short "
        "question at a time, collect their answers, and summarise everything as structured marketing brief fields. "
        "Always respond helpfully and professionally. Never refuse a standard marketing or advertising task."
    ),
    "ad_copy": (
        "You are a world-class direct-response copywriter specialising in digital ads. "
        "Generate persuasive, benefit-driven ad copy. "
        "Structure your output clearly with: Headline, Primary Text, and CTA. "
        "Make multiple variations if not specified otherwise. "
        f"{_NO_PREAMBLE}"
    ),
    "image_prompt": (
        "You are an expert at writing image generation prompts for AI tools like Midjourney, "
        "DALL-E, and Stable Diffusion. "
        "Output highly detailed, specific prompts that result in professional ad-quality images. "
        "Include: subject, style, lighting, composition, color palette, aspect ratio. "
        f"{_NO_PREAMBLE}"
    ),
    "video_prompt": (
        "You are an expert at writing video generation prompts for AI tools like Kling, Sora, "
        "and Runway. "
        "Output cinematic, detailed prompts that describe camera movement, scene, mood, lighting, "
        "and the story being told. Each prompt should be 3-5 sentences. "
        f"{_NO_PREAMBLE}"
    ),
    "bulk": (
        "You are a performance marketing creative director. "
        "Generate exactly 10 distinct ad variations optimised for A/B testing. "
        "Number each variation. Vary the angle, hook, and CTA across variations. "
        "Format: ## Variation N\\n[content] "
        f"{_NO_PREAMBLE}"
    ),
    "product_ideas": (
        "You are a product innovation consultant. "
        "Generate concrete product ideas: new variants, line extensions, bundles, accessories, "
        "use-case expansions, and complementary products the user could create or sell. "
        "Focus purely on what products to make or offer — not on how to market them. "
        f"{_NO_PREAMBLE}"
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

    # Prepend a task instruction for specialized modes so the AI acts on vague input
    instruction = _TYPE_INSTRUCTION.get(generation_type)
    api_input = f"{instruction}\n\n{user_input}" if instruction else user_input

    messages.append({"role": "user", "content": api_input})
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


_BRIEF_LABELS = {
    "target_audience":  "Target Audience",
    "usp":              "Unique Selling Proposition",
    "key_benefits":     "Key Benefits",
    "pain_points":      "Pain Points Addressed",
    "tone_of_voice":    "Tone of Voice",
    "price_positioning":"Price Positioning",
    "competitors":      "Competitors & Advantage",
    "social_proof":     "Social Proof",
    "campaign_goal":    "Campaign Goal",
    "geography":        "Geography / Market",
    "offer_hook":       "Offer / Hook / CTA",
    "product_category": "Product / Service Type",
}


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

    brief_section = _format_marketing_brief(project.marketing_brief)
    if brief_section:
        lines.append("")
        lines.append(brief_section)

    lines.append(
        "Always align all content with this brand identity. "
        "Maintain consistent tone, style, and messaging."
    )
    return "\n".join(lines)


def _format_marketing_brief(brief_json: str) -> str:
    if not brief_json:
        return ""
    try:
        brief = json.loads(brief_json)
    except Exception:
        return ""
    lines = ["## Marketing Brief"]
    for key, label in _BRIEF_LABELS.items():
        val = (brief.get(key) or "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    return "\n".join(lines) if len(lines) > 1 else ""


def estimate_token_count(text: str) -> int:
    """Rough estimate: ~4 chars per token."""
    return max(1, len(text) // 4)
