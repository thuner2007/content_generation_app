"""Data model dataclasses mirroring the DB schema."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    id: str
    name: str
    slogan: str = ""
    brand_colors: str = ""
    fonts: str = ""
    logo_path: str = ""
    legal_info: str = ""
    description: str = ""
    marketing_brief: str = ""
    image_style: str = ""
    # Brand voice & positioning
    tone_of_voice: str = ""
    brand_values: str = ""
    # Audio & video direction
    voiceover_voice: str = ""
    music_mood: str = ""
    video_style: str = ""
    # Audience & content strategy
    target_audience: str = ""
    content_pillars: str = ""
    hashtags: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Chat:
    id: str
    project_id: Optional[str]
    title: str = "New Chat"
    created_at: str = ""


@dataclass
class Message:
    id: str
    chat_id: str
    role: str  # user | assistant | system
    content: str
    provider: str = ""
    model: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    pinned: bool = False
    created_at: str = ""


@dataclass
class Asset:
    id: str
    project_id: str
    type: str  # text | image_prompt | video_prompt | image | bulk
    title: str = ""
    content: str = ""
    tags: str = ""
    provider: str = ""
    model: str = ""
    created_at: str = ""


@dataclass
class ApiKey:
    provider: str
    api_key: str
    updated_at: str = ""


@dataclass
class UsageLog:
    id: str
    project_id: str
    provider: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost: float = 0.0
    generation_type: str = "chat"
    created_at: str = ""


@dataclass
class ProjectFile:
    id: str
    project_id: str
    filename: str
    file_path: str
    file_type: str = ""
    extracted_text: str = ""
    created_at: str = ""


@dataclass
class Product:
    id: str
    project_id: str
    name: str
    description: str = ""
    price: str = ""
    url: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Campaign:
    id: str
    project_id: str
    name: str
    status: str = "draft"        # draft | active | paused | completed
    strategy: str = ""           # awareness | conversion | retargeting | lead_gen | brand | retention
    objective: str = ""          # traffic | leads | sales | awareness | engagement | app_installs | video_views
    platforms: str = "[]"        # JSON list e.g. '["meta","google"]'
    daily_budget: float = 0.0
    total_budget: float = 0.0
    start_date: str = ""
    end_date: str = ""
    target_audience: str = ""
    notes: str = ""
    product_name: str = ""
    product_description: str = ""
    video_ideas: str = "[]"      # JSON list of {id, title, concept, how_to_film, how_to_cut, scheduled_date, format, pub_status}
    product_ids: str = "[]"      # JSON list of project product IDs promoted in this campaign
    created_at: str = ""
    updated_at: str = ""
