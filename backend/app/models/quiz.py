from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.common import generate_uuid


class NodeQuiz(Base):
    __tablename__ = "node_quizzes"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    node_id = Column(
        String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True
    )

    # 知识点信息
    node_title = Column(String, nullable=False)
    is_key_node = Column(Integer, default=0)  # 0: 普通, 1: 重点章节

    # 出题配置
    question_count = Column(Integer, nullable=False)
    time_limit_min = Column(Integer, nullable=False)
    difficulty_level = Column(String, default="medium")  # easy, medium, hard

    # 题目快照（JSON，存储生成时的题目，不含答案）
    questions_json = Column(Text, nullable=False)

    # 答题结果
    time_used_sec = Column(Integer, nullable=True)
    score = Column(Integer, nullable=True)
    accuracy_pct = Column(Float, nullable=True)

    # 答案快照（JSON）
    answers_json = Column(Text, nullable=True)

    # 批改结果（JSON，包含解题思路）
    results_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime, nullable=True)

    # 关系
    student = relationship("Student", back_populates="node_quizzes")
    node = relationship("KnowledgeNode", back_populates="quizzes")
