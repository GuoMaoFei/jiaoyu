"""
Student Schemas - Pydantic models for student profile and learning state API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# === Request Models ===

class StudentCreateRequest(BaseModel):
    """Request to register a new student."""
    nickname: str = Field(..., min_length=1, description="Student nickname")
    grade: Optional[str] = Field(None, description="Current grade level")
    parent_id: Optional[str] = Field(None, description="Parent account ID to bind")


class LoginRequest(BaseModel):
    """Request to login a student (for demo purposes, uses nickname)."""
    username: str = Field(..., description="Student nickname or username")
    password: str = Field(..., description="Password (ignored in demo)")


class BookActivateRequest(BaseModel):
    """Request to activate (add to bookshelf) a material."""
    student_id: str
    material_id: str


# === Response Models ===

class LoginResponse(BaseModel):
    """Response after successful login."""
    access_token: str
    token_type: str = "bearer"
    student_id: str
    nickname: str
    grade: Optional[str] = None


class NodeHealthResponse(BaseModel):
    """Health status of a single knowledge node for a student."""
    node_id: str
    node_title: Optional[str] = None
    is_unlocked: bool = False
    health_score: int = 50


class StudentProfileResponse(BaseModel):
    """Full student learning profile."""
    id: str
    nickname: str
    grade: Optional[str] = None
    avg_health_score: int = 50
    weak_nodes: List[NodeHealthResponse] = []
    total_nodes_studied: int = 0
    active_mistakes_count: int = 0


class BookshelfItemResponse(BaseModel):
    """A material on the student's bookshelf (unified view)."""
    activation_id: Optional[str] = None
    material_id: str
    material_title: str
    grade: Optional[str] = None
    subject: Optional[str] = None
    node_count: int = 0
    progress_pct: int = 0
    health_score: int = 0
    activated_at: Optional[datetime] = None
    is_activated: bool = False


class BookshelfResponse(BaseModel):
    """Response for listing a student's activated materials."""
    student_id: str
    books: List[BookshelfItemResponse]


class StudentNodeStateResponse(BaseModel):
    """A single node's health and unlock state for a student."""
    node_id: str
    is_unlocked: bool
    health_score: int


class StudentNodeListResponse(BaseModel):
    """List of node states for a specific student and material."""
    student_id: str
    material_id: str
    node_states: List[StudentNodeStateResponse]


class StudentMistakeResponse(BaseModel):
    """A single student mistake record."""
    id: str
    student_id: str
    node_id: str
    node_title: Optional[str] = None
    original_question_id: Optional[str] = None
    error_reason: Optional[str] = None
    consecutive_correct_count: int
    status: str
    next_review_date: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MistakeListResponse(BaseModel):
    """List of mistakes for a student."""
    student_id: str
    mistakes: List[StudentMistakeResponse]
    total: int
