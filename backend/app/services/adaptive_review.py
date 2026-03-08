"""
Adaptive Review Service - Ebbinghaus forgetting curve based review scheduler.

Scans student's mistake records and node states to find items due for review,
then injects them into the student's daily plan.
"""
import logging
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.testing import StudentMistake, MistakeStatus
from app.models.lesson import PlanItem, PlanStatus, TaskType
from app.models.user import StudentNodeState

logger = logging.getLogger(__name__)

# Ebbinghaus review intervals (in days)
# After each successful review, move to the next interval
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]


def _next_review_date(last_reviewed: datetime, review_count: int) -> date:
    """Calculate the next review date based on Ebbinghaus forgetting curve."""
    interval_index = min(review_count, len(REVIEW_INTERVALS) - 1)
    interval_days = REVIEW_INTERVALS[interval_index]
    return (last_reviewed + timedelta(days=interval_days)).date()


async def get_due_reviews(student_id: str, as_of_date: date = None) -> List[Dict]:
    """
    Get all mistake items that are due for review based on the Ebbinghaus curve.
    
    Args:
        student_id: The student's unique ID.
        as_of_date: Check against this date (default: today).
    
    Returns:
        List of dicts with node_id, mistake_id, days_overdue, review_count.
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    async with AsyncSessionLocal() as db:
        # Get all non-mastered mistakes
        result = await db.execute(
            select(StudentMistake).where(
                StudentMistake.student_id == student_id,
                StudentMistake.status != MistakeStatus.MASTERED,
            )
        )
        mistakes = result.scalars().all()
        
        due_items = []
        for m in mistakes:
            last_date = m.last_reviewed_at or m.created_at
            next_date = _next_review_date(last_date, m.review_count)
            
            if next_date <= as_of_date:
                days_overdue = (as_of_date - next_date).days
                due_items.append({
                    "node_id": m.node_id,
                    "mistake_id": m.id,
                    "root_cause": m.root_cause_summary,
                    "review_count": m.review_count,
                    "days_overdue": days_overdue,
                    "next_review_date": next_date.isoformat(),
                })
        
        # Sort by overdue days (most overdue first)
        due_items.sort(key=lambda x: x["days_overdue"], reverse=True)
        
        return due_items


async def inject_review_plans(student_id: str) -> Dict:
    """
    Check for due reviews and inject them into the student's daily plan.
    
    Returns:
        Summary dict with count of injected review items.
    """
    today = date.today()
    due_items = await get_due_reviews(student_id, today)
    
    if not due_items:
        return {"injected": 0, "message": "No reviews due today."}
    
    async with AsyncSessionLocal() as db:
        injected = 0
        
        for item in due_items:
            # Check if a review plan already exists for today
            existing = await db.execute(
                select(PlanItem).where(
                    PlanItem.student_id == student_id,
                    PlanItem.node_id == item["node_id"],
                    PlanItem.scheduled_date == today,
                    PlanItem.task_type == TaskType.REVIEW,
                )
            )
            if existing.scalars().first():
                continue
            
            # Create a review plan item
            plan = PlanItem(
                student_id=student_id,
                node_id=item["node_id"],
                scheduled_date=today,
                task_type=TaskType.REVIEW,
                status=PlanStatus.PENDING,
            )
            db.add(plan)
            injected += 1
        
        await db.commit()
        
        return {
            "injected": injected,
            "total_due": len(due_items),
            "message": f"已注入 {injected} 个复习计划到今日任务。",
        }
