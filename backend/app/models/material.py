import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum, DateTime, JSON
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.common import generate_uuid


class MaterialType(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    EXTERNAL = "EXTERNAL"


class Material(Base):
    __tablename__ = "materials"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    title = Column(String, index=True, nullable=False)
    grade = Column(String, index=True, nullable=False)
    subject = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    publisher = Column(String)
    material_type = Column(
        Enum(MaterialType, name="material_type_enum"), default=MaterialType.OFFICIAL
    )
    pdf_asset_id = Column(String, ForeignKey("media_assets.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    nodes = relationship(
        "KnowledgeNode", back_populates="material", cascade="all, delete-orphan"
    )


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    material_id = Column(String, ForeignKey("materials.id"), nullable=False, index=True)
    parent_id = Column(
        String, ForeignKey("knowledge_nodes.id"), nullable=True, index=True
    )
    title = Column(String, nullable=False)
    level = Column(Integer, nullable=False)  # 1: Chapter, 2: Section, 3: Concept
    seq_num = Column(Integer, nullable=False)
    pageindex_ref = Column(String)
    mapped_pi_nodes = Column(JSON, nullable=True)  # Adding mapped_pi_nodes JSON field
    pi_nodes_json = Column(
        JSON, nullable=True
    )  # Full native PageIndex node objects array
    is_key_node = Column(Integer, default=0)  # 0: 普通, 1: 重点章节
    key_node_reason = Column(Text, nullable=True)  # 为什么是重点章节
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    material = relationship("Material", back_populates="nodes")
    # Self-referential: parent_id FK -> id PK. remote_side=[id] means "the remote side of this join is id"
    parent = relationship("KnowledgeNode", back_populates="children", remote_side=[id])
    children = relationship(
        "KnowledgeNode", back_populates="parent", foreign_keys=[parent_id]
    )
    questions = relationship("Question", back_populates="node")
    contents = relationship(
        "KnowledgeContent", back_populates="node", cascade="all, delete-orphan"
    )
    quizzes = relationship("NodeQuiz", back_populates="node")


class KnowledgeContent(Base):
    __tablename__ = "knowledge_contents"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    knowledge_node_id = Column(
        String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True
    )
    pi_node_id = Column(String, index=True)
    content_md = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    node = relationship("KnowledgeNode", back_populates="contents")


class QuestionSourceType(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    VARIANT_GENERATED = "VARIANT_GENERATED"
    UPLOADED = "UPLOADED"


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    node_id = Column(
        String, ForeignKey("knowledge_nodes.id"), nullable=True, index=True
    )
    content_md = Column(Text, nullable=False)
    answer_md = Column(Text)
    explanation_md = Column(Text)
    difficulty_level = Column(Integer, default=1)
    source_type = Column(
        Enum(QuestionSourceType, name="question_source_type_enum"),
        default=QuestionSourceType.OFFICIAL,
    )
    parent_question_id = Column(String, ForeignKey("questions.id"), nullable=True)
    media_asset_id = Column(String, ForeignKey("media_assets.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    node = relationship("KnowledgeNode", back_populates="questions")


class AssetScope(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    TEMPORARY = "TEMPORARY"


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    # Forward ref pointing to student, we allow nullable here to avoid circular
    student_id = Column(String, ForeignKey("students.id"), nullable=True, index=True)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    mime_type = Column(String, nullable=False)  # e.g., image/jpeg
    file_size_bytes = Column(Integer)
    access_scope = Column(
        Enum(AssetScope, name="asset_scope_enum"), default=AssetScope.PRIVATE
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
