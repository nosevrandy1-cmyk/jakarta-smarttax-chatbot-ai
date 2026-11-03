"""Text-only public chat contract. Source uploads belong to developer RAG routes."""
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from .config import DEFAULT_CHAT_MODEL


class ChatMessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=8000)


class ChatRequestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    room_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    history: List[ChatMessageInput] = Field(default_factory=list, max_length=20)
    model: Optional[str] = Field(default=DEFAULT_CHAT_MODEL, max_length=80)
    tema_pajak: Optional[str] = Field(default='PBB-P2', max_length=20)
    mode_kapabilitas: Optional[str] = Field(default='konsultasi', max_length=32)
