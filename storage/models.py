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
