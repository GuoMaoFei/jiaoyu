from typing import Optional
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from app.models.chat import ChatAssessment, AssessmentType
from app.models.user import StudentNodeState


@tool
async def save_assessment(
    student_id: str,
    node_id: str,
    is_correct: int,
    score_delta: int,
    diagnosis: str
) -> str:
    """
    Save the assessment result to the database and update the student's knowledge node health score.
    Call this tool after evaluating the student's response to a question.
    
    Args:
        student_id: The student's unique ID.
        node_id: The knowledge tree node ID that was being assessed.
        is_correct: 1 for correct, 0 for incorrect, -1 for partially correct.
        score_delta: The change to apply to health_score (e.g., +5 or -10).
        diagnosis: A brief structured diagnosis of the student's understanding (e.g., error reasons).
    
    Returns:
        A confirmation string with the updated health score.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Create ChatAssessment record
            assessment = ChatAssessment(
                node_id=node_id,
                assessment_type=AssessmentType.IMPLICIT,
                is_correct=is_correct,
                score_delta=score_delta,
                diagnosis_json={"diagnosis": diagnosis, "student_id": student_id}
            )
            db.add(assessment)
            
            # 2. Update or create StudentNodeState
            result = await db.execute(
                select(StudentNodeState).where(
                    StudentNodeState.student_id == student_id,
                    StudentNodeState.node_id == node_id
                )
            )
            node_state = result.scalars().first()
            
            if node_state:
                # Clamp health_score between 0 and 100
                new_score = max(0, min(100, node_state.health_score + score_delta))
                node_state.health_score = new_score
            else:
                # Create new state entry with default 50 + delta
                new_score = max(0, min(100, 50 + score_delta))
                node_state = StudentNodeState(
                    student_id=student_id,
                    node_id=node_id,
                    is_unlocked=True,
                    health_score=new_score
                )
                db.add(node_state)
            
            await db.commit()
            
            return (
                f"Assessment saved successfully. "
                f"Node: {node_id}, Correct: {is_correct}, Delta: {score_delta}. "
                f"Updated health_score: {new_score}/100. "
                f"Diagnosis: {diagnosis}"
            )
        except Exception as e:
            await db.rollback()
            return f"Failed to save assessment: {str(e)}"
