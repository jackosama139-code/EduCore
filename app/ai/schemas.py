from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    num_pages: int
    num_chunks: int
    uploaded_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(4, ge=1, le=8)


class Source(BaseModel):
    chunk_index: int
    score: float
    text: str


class AskResponse(BaseModel):
    answer: str
    mode: str  # "llm" | "extractive"
    sources: list[Source]
