"""
Materials Schemas - Pydantic models for material/textbook management API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# === Request Models ===

class MaterialCreateRequest(BaseModel):
    """Request to register a new material/textbook."""
    title: str = Field(..., description="Title of the textbook, e.g. '人教版八年级数学上册'")
    grade: str = Field(..., description="Grade level, e.g. '八年级'")
    subject: str = Field(..., description="Subject, e.g. '数学'")
    version: str = Field(..., description="Edition version, e.g. '2024年版'")
    publisher: Optional[str] = Field(None, description="Publisher name")


class TreeBuildRequest(BaseModel):
    """Request to trigger knowledge tree construction from a PDF."""
    material_id: str = Field(..., description="ID of the material to build tree for")
    pdf_url: str = Field(..., description="URL or local path to the PDF file")


# === Response Models ===

class KnowledgeNodeResponse(BaseModel):
    """A single knowledge tree node."""
    id: str
    title: str
    level: int
    seq_num: int
    parent_id: Optional[str] = None
    content_preview: Optional[str] = Field(None, description="First 200 chars of content")
    children_count: int = 0


class MaterialResponse(BaseModel):
    """Response for a single material."""
    id: str
    title: str
    grade: str
    subject: str
    version: str
    publisher: Optional[str] = None
    material_type: str
    created_at: datetime
    node_count: int = 0


class MaterialListResponse(BaseModel):
    """Response for listing materials."""
    materials: List[MaterialResponse]
    total: int


class TreeBuildResponse(BaseModel):
    """Response after triggering tree build."""
    status: str
    message: str
    doc_id: Optional[str] = None


class KnowledgeTreeResponse(BaseModel):
    """Response for the full knowledge tree of a material."""
    material_id: str
    material_title: str
    nodes: List[KnowledgeNodeResponse]
    total_nodes: int
