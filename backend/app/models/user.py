import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.common import generate_uuid

class Student(Base):
    __tablename__ = "students"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    parent_id = Column(String, ForeignKey("parents.id"), nullable=True, index=True)
    nickname = Column(String, nullable=False)
    grade = Column(String)
    learning_style = Column(String) # For the Empathy & Tutor Agent
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)
    
    parent = relationship("Parent", back_populates="children")
    activations = relationship("BookActivation", back_populates="student")
    node_states = relationship("StudentNodeState", back_populates="student")

class Parent(Base):
    __tablename__ = "parents"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    phone_number = Column(String, unique=True, index=True)
    password_hash = Column(String)
    wechat_openid = Column(String, unique=True, index=True)
    nickname = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    children = relationship("Student", back_populates="parent")

class BookActivation(Base):
    __tablename__ = "book_activations"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    material_id = Column(String, ForeignKey("materials.id"), nullable=False, index=True)
    activated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    global_progress_pct = Column(Integer, default=0)
    current_health_score = Column(Integer, default=0)
    
    student = relationship("Student", back_populates="activations")
    # material relationship not explicitly required for now unless needed

class StudentNodeState(Base):
    __tablename__ = "student_node_states"
    
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    node_id = Column(String, ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    is_unlocked = Column(Boolean, default=False)
    health_score = Column(Integer, default=50) # 0-100 indicating mastery level
    last_practiced_at = Column(DateTime)
    
    student = relationship("Student", back_populates="node_states")
