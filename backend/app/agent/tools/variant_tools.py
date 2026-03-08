"""
Variant Tools - Tools for the Variant Agent to generate variant questions.
"""
from typing import Optional
from langchain_core.tools import tool
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.material import KnowledgeNode, Question, QuestionSourceType


@tool
async def get_node_questions(node_id: str) -> str:
    """
    Get existing questions for a knowledge node as reference for generating variants.
    
    Args:
        node_id: The knowledge tree node ID to get questions for.
    
    Returns:
        Formatted list of existing questions for the node.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question).where(Question.node_id == node_id)
        )
        questions = result.scalars().all()
        
        if not questions:
            return f"节点 {node_id} 暂无已有题目。请根据节点内容全新出题。"
        
        output = [f"该节点已有 {len(questions)} 道题目："]
        for i, q in enumerate(questions, 1):
            output.append(f"\n{i}. [{q.source_type.value}] {q.content_md}")
            if q.answer_md:
                output.append(f"   标准答案：{q.answer_md}")
        
        return "\n".join(output)


@tool
async def save_variant_question(
    node_id: str,
    question_content: str,
    answer_content: str,
    difficulty: int = 3
) -> str:
    """
    Save a generated variant question to the database.
    
    Args:
        node_id: The knowledge node this question tests.
        question_content: The full question text in Markdown.
        answer_content: The full answer/solution in Markdown.
        difficulty: Difficulty level 1-5 (1=easiest, 5=hardest).
    
    Returns:
        Confirmation with the saved question ID.
    """
    async with AsyncSessionLocal() as db:
        try:
            question = Question(
                node_id=node_id,
                source_type=QuestionSourceType.AI_GENERATED,
                content_md=question_content,
                answer_md=answer_content,
                difficulty=difficulty,
            )
            db.add(question)
            await db.commit()
            await db.refresh(question)
            
            return f"变式题已保存。题目 ID: {question.id}，难度: {difficulty}/5，关联节点: {node_id}"
        except Exception as e:
            await db.rollback()
            return f"保存题目失败：{str(e)}"
