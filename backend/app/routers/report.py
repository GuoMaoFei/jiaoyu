"""
Report Router - Handles learning report generation and adaptive review.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.adaptive_review import get_due_reviews, inject_review_plans
from app.utils.vision_ocr import extract_text_from_image, validate_image_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Reports & Tools"])


class ReportRequest(BaseModel):
    student_id: str
    material_id: str


class ReviewInjectRequest(BaseModel):
    student_id: str


class OcrRequest(BaseModel):
    image_source: str = Field(
        ...,
        description="Base64 data URL (data:image/...) or public HTTPS URL",
        min_length=1,
        max_length=2048,
    )


@router.post("/reports/generate")
async def generate_report(request: ReportRequest):
    """
    Generate a learning report for a student on a specific material.
    Uses the Reporter Agent to query data and produce a structured report.
    """
    from app.agent.graph import treeedu_graph
    from langchain_core.messages import HumanMessage
    import uuid

    session_id = str(uuid.uuid4())
    agent_input = {
        "session_id": session_id,
        "student_id": request.student_id,
        "material_id": request.material_id,
        "current_intent": "reporter",
        "messages": [HumanMessage(content="请为该学生生成本周学情报告。")],
    }
    config = {"configurable": {"thread_id": session_id}}

    final_content = ""
    try:
        async for event in treeedu_graph.astream(agent_input, config=config):
            for node_name, values in event.items():
                if "messages" in values and node_name == "reporter":
                    last_msg = values["messages"][-1]
                    if hasattr(last_msg, "content") and last_msg.content:
                        final_content = last_msg.content
                    if hasattr(last_msg, "tool_calls"):
                        logger.debug(f"Report tool_calls: {last_msg.tool_calls}")
    except Exception as e:
        logger.exception(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")

    return {
        "status": "ok",
        "student_id": request.student_id,
        "material_id": request.material_id,
        "report_md": final_content or "报告生成失败，请稍后重试。",
    }


@router.get("/reviews/due/{student_id}")
async def get_reviews_due(student_id: str):
    """Get all review items due for a student based on Ebbinghaus forgetting curve."""
    due_items = await get_due_reviews(student_id)
    return {
        "student_id": student_id,
        "due_count": len(due_items),
        "items": due_items,
    }


@router.post("/reviews/inject")
async def inject_reviews(request: ReviewInjectRequest):
    """Inject due review items into the student's daily plan."""
    result = await inject_review_plans(request.student_id)
    return result


@router.post("/ocr/extract")
async def ocr_extract(request: OcrRequest):
    """
    Extract text and LaTeX from an image using LLM vision.

    Security: Only accepts base64 data URLs or public HTTPS URLs.
    Internal URLs and local file paths are blocked for security.
    """
    is_valid, error_msg = validate_image_source(request.image_source)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    result = await extract_text_from_image(request.image_source)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "OCR failed"))
    return result
