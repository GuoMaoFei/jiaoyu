import enum
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text, Date

from app.database import Base
from app.utils.common import generate_uuid

sys_now = lambda: datetime.now(timezone.utc)

class TestPaper(Base):
    __tablename__ = "test_papers"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    snapshot_question_md = Column(Text, nullable=False) # Important: lock the paper content
    total_score = Column(Integer, default=100)
    created_at = Column(DateTime, default=sys_now)

class TestRecord(Base):
    __tablename__ = "test_records"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    test_paper_id = Column(String, ForeignKey("test_papers.id"), nullable=False, index=True)
    student_score = Column(Integer)
    answers_json = Column(Text) 
    grading_json = Column(Text) # Assessor agent evaluations
    submitted_at = Column(DateTime, default=sys_now)

class MistakeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVIEWING = "REVIEWING"
    MASTERED = "MASTERED"

class StudentMistake(Base):
    __tablename__ = "student_mistakes"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    node_id = Column(String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    
    original_question_id = Column(String, ForeignKey("questions.id"), nullable=True) 
    source_message_id = Column(String, ForeignKey("chat_messages.id"), nullable=True) 
    
    error_reason = Column(String)
    consecutive_correct_count = Column(Integer, default=0) # Must reach threshold to be MASTERED
    status = Column(Enum(MistakeStatus, name="mistake_status_enum"), default=MistakeStatus.ACTIVE)
    next_review_date = Column(Date)
    
    created_at = Column(DateTime, default=sys_now)
    updated_at = Column(DateTime, default=sys_now, onupdate=sys_now)
