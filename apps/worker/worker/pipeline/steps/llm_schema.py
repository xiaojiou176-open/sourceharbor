from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TimestampReference(_StrictModel):
    ts_s: int = Field(ge=0)
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class CodeSnippet(_StrictModel):
    title: str = Field(min_length=1)
    language: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    range_start_s: int = Field(ge=0)
    range_end_s: int = Field(ge=0)


class OutlineChapter(_StrictModel):
    chapter_no: int = Field(ge=1)
    title: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    start_s: int = Field(ge=0)
    end_s: int = Field(ge=0)
    summary: str = Field(min_length=1)
    bullets: list[str] = Field(min_length=1)
    key_terms: list[str] = Field(default_factory=list)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)


class OutlinePayload(_StrictModel):
    title: str = Field(min_length=1)
    tldr: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(min_length=1)
    recommended_actions: list[str] = Field(default_factory=list)
    risk_or_pitfalls: list[str] = Field(default_factory=list)
    chapters: list[OutlineChapter] = Field(min_length=1)
    timestamp_references: list[TimestampReference] = Field(default_factory=list)
    generated_by: str | None = None
    generated_at: str | None = None


class DigestPayload(_StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    tldr: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(min_length=1)
    action_items: list[str] = Field(default_factory=list)
    code_blocks: list[CodeSnippet] = Field(default_factory=list)
    timestamp_references: list[TimestampReference] = Field(default_factory=list)
    fallback_notes: list[str] = Field(default_factory=list)
    generated_by: str | None = None
    generated_at: str | None = None


def outline_response_schema() -> dict:
    return OutlinePayload.model_json_schema()


def digest_response_schema() -> dict:
    return DigestPayload.model_json_schema()
