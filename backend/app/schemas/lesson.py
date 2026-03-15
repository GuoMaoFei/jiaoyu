"""
Lesson Schemas - Pydantic models for guided learning API
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LessonStartRequest(BaseModel):
    """Request to start or resume a guided learning session."""

    student_id: str = Field(..., description="Student's unique ID")
    node_id: str = Field(..., description="Knowledge node ID to study")


class LessonAdvanceRequest(BaseModel):
    """Request to advance to the next lesson step."""

    student_id: str
    node_id: str


class LessonStatusResponse(BaseModel):
    """Response with current lesson status."""

    lesson_id: str
    student_id: Optional[str] = None
    node_id: Optional[str] = None
    material_id: Optional[str] = None
    current_step: str
    is_completed: bool = False
    node_title: Optional[str] = None
    content_preview: Optional[str] = None
    step_prompt: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class PlanGenerateRequest(BaseModel):
    """Request to generate studying plans via Planner Agent."""

    student_id: str
    material_id: str
    start_date: Optional[str] = None
    sessions_per_week: Optional[int] = 3


class PlanItemResponse(BaseModel):
    """A single scheduled study task."""

    id: str
    node_id: str
    type: str  # 'LEARN_NEW' or 'DO_QUIZ' or 'REVIEW_VARIANT'
    title: str
    completed: bool
    duration_min: int
    date: str


class PlanListResponse(BaseModel):
    """List of planned study tasks for the student."""

    student_id: str
    items: list[PlanItemResponse]
    start_date: str | None = None
    end_date: str | None = None
