from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.common import generate_uuid


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    parent_id = Column(
        String, ForeignKey("knowledge_points.id"), nullable=True, index=True
    )
    subject = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)  # 逗号分隔，用于 bigram 匹配和去重
    level = Column(Integer, nullable=False, default=1)  # 1=领域 2=主题 3=概念 4=子概念
    parent_title = Column(String, nullable=True)  # 提取时记录的父级主题名称
    embedding_hash = Column(String, index=True, nullable=True)  # 标准化标题 SHA256[:32]
    source_count = Column(Integer, nullable=False, default=0)  # 被多少教材引用
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Self-referential: parent/children
    parent = relationship(
        "KnowledgePoint", back_populates="children", remote_side=[id]
    )
    children = relationship(
        "KnowledgePoint", back_populates="parent", foreign_keys=[parent_id]
    )
    mappings = relationship(
        "KnowledgePointMapping", back_populates="knowledge_point", cascade="all, delete-orphan"
    )


class KnowledgePointMapping(Base):
    __tablename__ = "knowledge_point_mappings"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "knowledge_node_id", name="uq_kp_node"
        ),
    )

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    knowledge_point_id = Column(
        String, ForeignKey("knowledge_points.id"), nullable=False, index=True
    )
    knowledge_node_id = Column(
        String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True
    )
    relevance_score = Column(Integer, nullable=True)  # 0-100
    context_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    knowledge_point = relationship(
        "KnowledgePoint", back_populates="mappings"
    )
    knowledge_node = relationship(
        "KnowledgeNode", back_populates="kp_mappings"
    )
