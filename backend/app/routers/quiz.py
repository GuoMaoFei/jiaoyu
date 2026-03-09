import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizPaper,
    QuizSubmitRequest,
    QuizResult,
    QuizHistoryItem,
    QuizPaperWithAnswers,
)
from app.services import quiz_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quizzes", tags=["Quiz"])


@router.post("/generate", response_model=QuizPaper)
async def generate_quiz(
    request: QuizGenerateRequest, db: AsyncSession = Depends(get_db)
):
    """
    为单个知识点生成智能微测

    LLM 会分析：
    1. 知识点复杂度
    2. 是否重点章节
    3. 学生历史表现
    动态决定：题目数量、题型分布、时间限制
    """
    try:
        quiz = await quiz_generator.generate_node_quiz(
            request.student_id, request.node_id, db
        )
        return quiz
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Quiz generation failed: {e}")
        raise HTTPException(status_code=500, detail="生成微测失败，请稍后重试")


@router.post("/submit", response_model=QuizResult)
async def submit_quiz(request: QuizSubmitRequest, db: AsyncSession = Depends(get_db)):
    """
    提交微测答案并批改

    返回结果包含：
    - 每道题的批改详情
    - 详细解题思路
    - 节点健康度变化
    - 错题自动加入复习队列
    """
    try:
        result = await quiz_generator.submit_quiz(
            request.student_id,
            request.quiz_id,
            [a.model_dump() for a in request.answers],
            request.time_used_sec,
            db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Quiz submission failed: {e}")
        raise HTTPException(status_code=500, detail="提交失败，请稍后重试")


@router.get("/history/{student_id}/{node_id}", response_model=List[QuizHistoryItem])
async def get_quiz_history(
    student_id: str, node_id: str, db: AsyncSession = Depends(get_db)
):
    """
    获取某知识点的历史微测记录（全部保留）
    """
    try:
        history = await quiz_generator.get_quiz_history(student_id, node_id, db)
        return history
    except Exception as e:
        logger.exception(f"Failed to get quiz history: {e}")
        raise HTTPException(status_code=500, detail="获取历史记录失败")


@router.get("/{quiz_id}", response_model=QuizPaperWithAnswers)
async def get_quiz_detail(quiz_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取微测详情（包含答案和解题思路）
    """
    try:
        quiz = await quiz_generator.get_quiz_by_id(quiz_id, db)
        if not quiz:
            raise HTTPException(status_code=404, detail="微测不存在")

        import json
        from app.schemas.quiz import QuestionWithAnswer

        questions_data = json.loads(quiz.questions_json)
        questions = [QuestionWithAnswer(**q) for q in questions_data]

        return QuizPaperWithAnswers(
            id=quiz.id,
            node_id=quiz.node_id,
            node_title=quiz.node_title,
            is_key_node=bool(quiz.is_key_node),
            question_count=quiz.question_count,
            time_limit_min=quiz.time_limit_min,
            difficulty_level=quiz.difficulty_level,
            questions=questions,
            created_at=quiz.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get quiz detail: {e}")
        raise HTTPException(status_code=500, detail="获取微测详情失败")


@router.get("/unfinished/{student_id}/{node_id}", response_model=QuizPaper)
async def get_unfinished_quiz(
    student_id: str, node_id: str, db: AsyncSession = Depends(get_db)
):
    """
    获取未完成的测试（用于继续答题）
    """
    try:
        quiz = await quiz_generator.get_unfinished_quiz(student_id, node_id, db)
        if not quiz:
            raise HTTPException(status_code=404, detail="没有未完成的测试")
        return quiz
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get unfinished quiz: {e}")
        raise HTTPException(status_code=500, detail="获取未完成测试失败")


class SaveProgressRequest(BaseModel):
    quiz_id: str
    answers: list
    current_index: int


@router.post("/save-progress")
async def save_quiz_progress(
    request: SaveProgressRequest, db: AsyncSession = Depends(get_db)
):
    """
    保存答题进度（切题时自动保存）
    """
    try:
        await quiz_generator.save_quiz_progress(
            request.quiz_id, request.answers, request.current_index, db
        )
        return {"status": "ok", "message": "进度已保存"}
    except Exception as e:
        logger.exception(f"Failed to save progress: {e}")
        raise HTTPException(status_code=500, detail="保存进度失败")
