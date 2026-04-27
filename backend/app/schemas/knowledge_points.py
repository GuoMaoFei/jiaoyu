"""
Knowledge Points Schemas - Pydantic models for knowledge point API
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class KnowledgePointBrief(BaseModel):
    """知识点简要信息"""
    id: str
    title: str
    level: int


class KnowledgePointNodeResponse(BaseModel):
    """知识点树节点（递归结构）"""
    id: str
    title: str
    summary: Optional[str] = None
    keywords: Optional[str] = None
    level: int
    source_count: int = 0
    children: Optional[List[KnowledgePointNodeResponse]] = None


class KnowledgePointTreeResponse(BaseModel):
    """学科知识点树响应"""
    subject: str
    total_points: int
    tree: List[KnowledgePointNodeResponse]


class KnowledgePointMappingResponse(BaseModel):
    """知识点映射信息"""
    knowledge_node_id: str
    knowledge_node_title: str
    material_id: str
    material_title: str
    relevance_score: Optional[int] = None
    context_snippet: Optional[str] = None


class KnowledgePointDetailResponse(BaseModel):
    """知识点详情响应"""
    id: str
    title: str
    summary: Optional[str] = None
    keywords: Optional[str] = None
    level: int
    subject: str
    source_count: int = 0
    parent_id: Optional[str] = None
    mappings: List[KnowledgePointMappingResponse] = []


class KnowledgePointSearchResultItem(BaseModel):
    """知识点搜索结果项"""
    id: str
    title: str
    summary: Optional[str] = None
    level: int
    source_count: int = 0


class KnowledgePointSearchResponse(BaseModel):
    """知识点搜索响应"""
    subject: str
    query: str
    results: List[KnowledgePointSearchResultItem]


class KnowledgePointMaterialItem(BaseModel):
    """知识点关联教材项"""
    material_id: str
    material_title: str
    node_title: str
    content_preview: Optional[str] = None


class KnowledgePointMaterialsResponse(BaseModel):
    """知识点关联教材响应"""
    knowledge_point_id: str
    knowledge_point_title: str
    materials: List[KnowledgePointMaterialItem]
