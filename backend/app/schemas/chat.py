"""
Chat Schemas - Pydantic models for chat interaction API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# === Request Models ===

class ChatMessageRequest(BaseModel):
    """Request body for sending a message to the Agent."""
    student_id: str = Field(..., description="Student's unique ID")
    material_id: str = Field(..., description="The active material/textbook ID")
    session_id: Optional[str] = Field(None, description="Existing session ID. If null, a new session is created.")
    node_id: Optional[str] = Field(None, description="The current active knowledge node ID, if learning a specific lesson")
    lesson_step: Optional[str] = Field(None, description="The current guided learning step (IMPORT, EXPLAIN, etc.)")
    message: str = Field(..., min_length=1, description="The student's message text")
    image_url: Optional[str] = Field(None, description="URL of an uploaded image (for photo-question feature)")


# === Response Models ===

class AgentMessageResponse(BaseModel):
    """A single message from the Agent."""
    session_id: str
    role: str = Field(..., description="TUTOR_AGENT or ASSESSOR_AGENT")
    content: str = Field(..., description="The agent's response text")
    tool_calls_made: Optional[List[str]] = Field(None, description="List of tool names called during this turn")
    
    # Memory Overlay snapshot for debugging / frontend display
    health_score: Optional[int] = Field(None, description="Student's current avg health score")
    weak_nodes_count: Optional[int] = Field(None, description="Number of weak nodes detected")


class ChatSessionInfo(BaseModel):
    """Summary info for a chat session."""
    id: str
    student_id: str
    session_type: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    """Response for listing chat sessions."""
    sessions: List[ChatSessionInfo]
    total: int
