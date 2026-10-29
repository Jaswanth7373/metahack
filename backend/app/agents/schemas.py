"""Strict, validated shapes for every model output the agent consumes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ToolName = Literal["explain_document", "extract_deadline", "fill_form", "draft_response",
                   "add_deadline", "verify_form", "ask_user_confirmation"]


class PlanAction(BaseModel):
    tool: ToolName
    reason: str = Field(max_length=400)


class Plan(BaseModel):
    document_type: str = Field(max_length=80)
    document_title: str = Field(max_length=160)
    intent: str = Field(max_length=200)
    actions: list[PlanAction] = Field(min_length=1, max_length=10)


class Explanation(BaseModel):
    summary: str
    what_it_means: str
    steps: list[str] = Field(min_length=1, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=6)


class DeadlineItem(BaseModel):
    title: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = ""


class Deadlines(BaseModel):
    deadlines: list[DeadlineItem] = Field(default_factory=list, max_length=5)


class FieldValue(BaseModel):
    name: str
    value: str
    confidence: float = Field(ge=0, le=1)
    note: str | None = None


class FillResult(BaseModel):
    fields: list[FieldValue]


class Letter(BaseModel):
    subject: str
    body: str = Field(min_length=20)


class FieldCheck(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    note: str | None = None


class Verification(BaseModel):
    overall_confidence: float = Field(ge=0, le=1)
    summary: str
    issues: list[str] = Field(default_factory=list)
    fields: list[FieldCheck] = Field(default_factory=list)

    @field_validator("issues")
    @classmethod
    def _cap(cls, v: list[str]) -> list[str]:
        return v[:8]


def json_schema(model: type[BaseModel]) -> dict:
    return model.model_json_schema()
