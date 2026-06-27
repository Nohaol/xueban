from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FocusMetrics(BaseModel):
    gaze: int = Field(ge=0, le=100)
    posture: int = Field(ge=0, le=100)
    stability: int = Field(ge=0, le=100)
    presence: int = Field(ge=0, le=100)


class FocusPayload(BaseModel):
    timestamp: int
    studentLabel: str
    status: str
    focusScore: int = Field(ge=0, le=100)
    awaySeconds: int = Field(ge=0)
    eventText: str
    metrics: FocusMetrics
    sourceId: str | None = None
    sourceLabel: str | None = None
    engineMode: str | None = None


class ControlCommand(BaseModel):
    command: str
    issuedAt: int | None = None
    text: str | None = None


class SourceSelectionCommand(BaseModel):
    sourceId: str


class NetworkSourceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    url: str = Field(min_length=1, max_length=1024)
    transport: Literal["stream", "snapshot"] = "stream"


class RuntimeSettings(BaseModel):
    awayTimeoutMinutes: int = Field(ge=1, le=120)
    xiaozhiMcpUrl: str = Field(default="", max_length=1024)
    xiaozhiMcpToken: str = Field(default="", max_length=512)
    ageMode: Literal["primary", "middle", "high"] = "middle"


class AIReviewRequest(BaseModel):
    context: dict[str, Any]


