"""
Student Router - Handles student profiles, bookshelf, and learning state.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import Student, BookActivation, StudentNodeState
from app.models.material import Material, KnowledgeNode
from app.models.testing import StudentMistake, MistakeStatus
from app.services.memory_overlay import get_student_memory_overlay
from app.schemas.student import (
    StudentCreateRequest,
    StudentProfileResponse,
    BookActivateRequest,
    BookshelfResponse,
    BookshelfItemResponse,
    NodeHealthResponse,
    StudentNodeStateResponse,
    StudentNodeListResponse,
    StudentMistakeResponse,
    MistakeListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/students", tags=["Students"])


@router.post("/", response_model=StudentProfileResponse)
async def create_student(request: StudentCreateRequest, db: AsyncSession = Depends(get_db)):
    """Register a new student."""
    student = Student(
        nickname=request.nickname,
        grade=request.grade,
        parent_id=request.parent_id,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
    return StudentProfileResponse(
        id=student.id,
        nickname=student.nickname,
        grade=student.grade,
    )



@router.get("/{student_id}/profile", response_model=StudentProfileResponse)
async def get_student_profile(student_id: str, db: AsyncSession = Depends(get_db)):
    """Get a student's full learning profile with memory overlay data."""
    # Verify student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get memory overlay
    overlay = await get_student_memory_overlay(student_id)
    
    # Get weak nodes with titles
    weak_nodes = []
    if overlay["weak_nodes"]:
        for node_id in overlay["weak_nodes"][:10]:
            # Get node state
            ns_result = await db.execute(
                select(StudentNodeState).where(
                    StudentNodeState.student_id == student_id,
                    StudentNodeState.node_id == node_id
                )
            )
            ns = ns_result.scalars().first()
            
            # Get node title
            node_result = await db.execute(
                select(KnowledgeNode.title).where(KnowledgeNode.id == node_id)
            )
            title_row = node_result.first()
            
            if ns:
                weak_nodes.append(NodeHealthResponse(
                    node_id=node_id,
                    node_title=title_row[0] if title_row else None,
                    is_unlocked=ns.is_unlocked,
                    health_score=ns.health_score,
                ))
    
    # Count total studied nodes
    studied_result = await db.execute(
        select(func.count(StudentNodeState.id)).where(
            StudentNodeState.student_id == student_id
        )
    )
    total_studied = studied_result.scalar() or 0
    
    # Count active mistakes
    mistakes_result = await db.execute(
        select(func.count(StudentMistake.id)).where(
            StudentMistake.student_id == student_id,
            StudentMistake.status != MistakeStatus.MASTERED
        )
    )
    active_mistakes = mistakes_result.scalar() or 0
    
    return StudentProfileResponse(
        id=student.id,
        nickname=student.nickname,
        grade=student.grade,
        avg_health_score=overlay["avg_health_score"],
        weak_nodes=weak_nodes,
        total_nodes_studied=total_studied,
        active_mistakes_count=active_mistakes,
    )


@router.post("/activate-book")
async def activate_book(request: BookActivateRequest, db: AsyncSession = Depends(get_db)):
    """Activate (add to bookshelf) a material for a student."""
    # Verify student
    student_result = await db.execute(select(Student).where(Student.id == request.student_id))
    if not student_result.scalars().first():
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Verify material
    material_result = await db.execute(select(Material).where(Material.id == request.material_id))
    if not material_result.scalars().first():
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Check if already activated
    existing = await db.execute(
        select(BookActivation).where(
            BookActivation.student_id == request.student_id,
            BookActivation.material_id == request.material_id
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Material already activated for this student")
    
    activation = BookActivation(
        student_id=request.student_id,
        material_id=request.material_id,
    )
    db.add(activation)
    await db.commit()
    
    return {"status": "ok", "message": "Material activated successfully", "activation_id": activation.id}


@router.get("/{student_id}/bookshelf", response_model=BookshelfResponse)
async def get_bookshelf(student_id: str, db: AsyncSession = Depends(get_db)):
    """Get ALL materials in the system, with activation status for this student."""
    # 1. Get all materials
    all_materials_result = await db.execute(
        select(Material).order_by(Material.created_at.desc())
    )
    all_materials = all_materials_result.scalars().all()
    
    # 2. Get this student's activations as a lookup
    act_result = await db.execute(
        select(BookActivation).where(BookActivation.student_id == student_id)
    )
    activations = {act.material_id: act for act in act_result.scalars().all()}
    
    # 3. Build unified list
    books = []
    for material in all_materials:
        act = activations.get(material.id)
        
        # Count nodes for this material
        count_result = await db.execute(
            select(func.count(KnowledgeNode.id)).where(KnowledgeNode.material_id == material.id)
        )
        node_count = count_result.scalar() or 0
        
        books.append(BookshelfItemResponse(
            activation_id=act.id if act else None,
            material_id=material.id,
            material_title=material.title,
            grade=material.grade,
            subject=material.subject,
            node_count=node_count,
            progress_pct=act.global_progress_pct or 0 if act else 0,
            health_score=act.current_health_score or 0 if act else 0,
            activated_at=act.activated_at if act else None,
            is_activated=act is not None,
        ))
    
    return BookshelfResponse(student_id=student_id, books=books)


@router.get("/{student_id}/materials/{material_id}/nodes", response_model=StudentNodeListResponse)
async def get_student_nodes(student_id: str, material_id: str, db: AsyncSession = Depends(get_db)):
    """Get a student's node mastery states for a specific material."""
    # Ensure all nodes for the material are known
    nodes_result = await db.execute(
        select(KnowledgeNode.id).where(KnowledgeNode.material_id == material_id)
    )
    material_node_ids = [row[0] for row in nodes_result.all()]
    
    if not material_node_ids:
        return StudentNodeListResponse(student_id=student_id, material_id=material_id, node_states=[])

    # Fetch student's states for these nodes
    states_result = await db.execute(
        select(StudentNodeState).where(
            StudentNodeState.student_id == student_id,
            StudentNodeState.node_id.in_(material_node_ids)
        )
    )
    states = states_result.scalars().all()
    
    # Create lookup
    state_lookup = {state.node_id: state for state in states}
    
    response_states = []
    for node_id in material_node_ids:
        state = state_lookup.get(node_id)
        if state:
            response_states.append(StudentNodeStateResponse(
                node_id=node_id,
                is_unlocked=state.is_unlocked,
                health_score=state.health_score,
            ))
        else:
            # Default state
            response_states.append(StudentNodeStateResponse(
                node_id=node_id,
                is_unlocked=False,
                health_score=0,
            ))
            
    return StudentNodeListResponse(
        student_id=student_id,
        material_id=material_id,
        node_states=response_states
    )


@router.get("/{student_id}/mistakes", response_model=MistakeListResponse)
async def get_mistakes(
    student_id: str, 
    material_id: Optional[str] = None, 
    status: Optional[MistakeStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get a student's mistakes, optionally filtered by material and status."""
    stmt = select(StudentMistake, KnowledgeNode.title.label("node_title")).join(
        KnowledgeNode, StudentMistake.node_id == KnowledgeNode.id
    ).where(StudentMistake.student_id == student_id)
    
    if material_id:
        stmt = stmt.where(KnowledgeNode.material_id == material_id)
    
    if status:
        stmt = stmt.where(StudentMistake.status == status)
        
    stmt = stmt.order_by(StudentMistake.updated_at.desc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    mistakes = []
    for mistake_obj, node_title in rows:
        mistakes.append(StudentMistakeResponse(
            id=mistake_obj.id,
            student_id=mistake_obj.student_id,
            node_id=mistake_obj.node_id,
            node_title=node_title,
            original_question_id=mistake_obj.original_question_id,
            error_reason=mistake_obj.error_reason,
            consecutive_correct_count=mistake_obj.consecutive_correct_count,
            status=mistake_obj.status.value,
            next_review_date=mistake_obj.next_review_date.isoformat() if mistake_obj.next_review_date else None,
            created_at=mistake_obj.created_at,
            updated_at=mistake_obj.updated_at,
        ))
        
    return MistakeListResponse(
        student_id=student_id,
        mistakes=mistakes,
        total=len(mistakes)
    )
