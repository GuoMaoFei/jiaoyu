import logging
import json
import uuid
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.testing import TestPaper, TestRecord, StudentMistake, MistakeStatus
from app.models.user import StudentNodeState
from app.models.material import KnowledgeNode
from app.agent.tools.assessment_tools import save_assessment
from app.utils.llm_router import get_fast_model
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exams", tags=["Exam"])

class GenerateExamRequest(BaseModel):
    student_id: str
    material_id: str
    exam_type: str = "diagnostic" # diagnostic or unit_test

class ExamAnswerInput(BaseModel):
    question_id: str
    student_answer: str

class SubmitExamRequest(BaseModel):
    student_id: str
    exam_id: str
    paper_metadata: dict # Includes questions, title, etc. (for simplicity, bypassing DB lookup for now)
    answers: List[ExamAnswerInput]
    time_used_sec: int

# Fixed diagnostic paper for demonstration (replaces frontend mock)
DIAGNOSTIC_PAPER = {
    "id": "exam-demo",
    "title": "初二数学上册 · 诊断测验",
    "total_score": 100,
    "time_limit_min": 30,
    "questions": [
        {
            "id": "q1", "type": "SINGLE_CHOICE", "node_id": "sec1_1", "node_title": "全等三角形的概念",
            "question_md": "下列说法正确的是：\n\nA. 面积相等的两个三角形是全等三角形\n\nB. 全等三角形的面积一定相等\n\nC. 形状相同的两个三角形是全等三角形\n\nD. 周长相等的两个三角形是全等三角形",
            "options": ["A", "B", "C", "D"], "correct_answer": "B"
        },
        {
            "id": "q2", "type": "FILL_BLANK", "node_id": "sec1_2", "node_title": "性质",
            "question_md": "已知 $\\triangle ABC \\cong \\triangle DEF$，若 $AB = 5$，则 $DE = $ ______。",
            "correct_answer": "5"
        },
        {
            "id": "q3", "type": "SHORT_ANSWER", "node_id": "sec2_1", "node_title": "轴对称",
            "question_md": "请简述什么是轴对称图形。",
            "correct_answer": "一个图形沿着一条直线折叠，直线两旁的部分能够完全重合的图形是轴对称图形。"
        }
    ]
}

@router.post("/generate")
async def generate_exam(req: GenerateExamRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate an exam paper. Fetch ONLY unlocked nodes for the student to prevent out-of-bounds testing.
    Dynamically generates questions using the Variant Agent prompt pattern.
    """
    if req.exam_type == 'diagnostic':
        # Diagnostic tests sample across the entire material
        stmt = (
            select(KnowledgeNode)
            .where(KnowledgeNode.material_id == req.material_id)
            .limit(3)
        )
    else:
        # Unit tests strictly enforce bounds
        stmt = (
            select(KnowledgeNode)
            .join(StudentNodeState, KnowledgeNode.id == StudentNodeState.node_id)
            .where(
                KnowledgeNode.material_id == req.material_id,
                StudentNodeState.student_id == req.student_id,
                StudentNodeState.is_unlocked == True
            )
            .limit(3)
        )

    nodes_result = await db.execute(stmt)
    nodes = nodes_result.scalars().all()
    
    if not nodes:
        raise HTTPException(status_code=400, detail="没有已解锁的知识点，无法生成测试。")

    paper_id = str(uuid.uuid4())
    questions = []
    model = get_fast_model(temperature=0.7)
    
    sys_msg = SystemMessage(content="你是客观的学科测试出题专家。请根据给定的知识点，出一道具有检测作用的单选题。请返回严格的JSON格式：{\"question_md\": \"题干(加上选项)\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"大写字母\", \"explanation\": \"原理解析\"}")

    for i, node in enumerate(nodes):
        user_msg = HumanMessage(content=f"为知识点「{node.title}」出一道单选题。")
        try:
            resp = model.invoke([sys_msg, user_msg])
            txt = resp.content.replace("```json", "").replace("```", "").strip()
            q_data = json.loads(txt)
            questions.append({
                "id": f"q{i+1}",
                "type": "SINGLE_CHOICE",
                "node_id": node.id,
                "node_title": node.title,
                "question_md": q_data.get("question_md", "内容缺失"),
                "options": q_data.get("options", ["A", "B", "C", "D"]),
                "correct_answer": q_data.get("correct_answer", "A")
            })
        except Exception as e:
            logger.warning(f"LLM question generation failed for {node.id}: {e}")
            questions.append({
                "id": f"q{i+1}",
                "type": "SINGLE_CHOICE",
                "node_id": node.id,
                "node_title": node.title,
                "question_md": f"关于【{node.title}】的备用题:\n\nA. 完全正确\n\nB. 必须相等\n\nC. 形状相同\n\nD. 周长相等",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A"
            })

    paper_data = {
        "id": paper_id,
        "title": "摸底诊断测评" if req.exam_type == 'diagnostic' else "综合随堂测验",
        "total_score": 100,
        "time_limit_min": 30,
        "questions": questions
    }
    
    # Save the paper to DB
    tp = TestPaper(
        id=paper_id,
        student_id=req.student_id,
        snapshot_question_md=json.dumps(paper_data, ensure_ascii=False),
        total_score=paper_data["total_score"]
    )
    db.add(tp)
    await db.commit()
    
    return {"status": "ok", "paper": paper_data}


@router.post("/submit")
async def submit_exam(req: SubmitExamRequest, db: AsyncSession = Depends(get_db)):
    """
    Submits exam answers. Evaluates them (using exact match or LLM for short answers),
    calculates score, updates StudentNodeState, inserts Mistakes, and saves TestRecord.
    """
    questions = req.paper_metadata.get("questions", [])
    q_map = {q["id"]: q for q in questions}
    
    results = []
    total_correct = 0
    total_questions = len(questions)
    
    for ans in req.answers:
        q = q_map.get(ans.question_id)
        if not q:
            continue
            
        student_ans = (ans.student_answer or "").strip()
        correct_ans = str(q.get("correct_answer", "")).strip()
        is_correct = False
        explanation = "正确"
        
        # Simple evaluation logic (for prototype efficiency, could also invoke Assessor graph node)
        if q["type"] in ["SINGLE_CHOICE", "MULTI_CHOICE", "FILL_BLANK"]:
            is_correct = student_ans.lower() == correct_ans.lower()
            explanation = "回答正确" if is_correct else f"标准答案是 {correct_ans}"
        else:
            # For SHORT_ANSWER, we use a fast LLM assessor
            model = get_fast_model(temperature=0.0)
            sys_msg = SystemMessage(content="你是客观的阅卷老师。比较学生的简答和标准答案，判断对错。返回JSON格式: {\"is_correct\": true/false, \"explanation\": \"简短评语\"}")
            user_msg = HumanMessage(content=f"题目: {q['question_md']}\n标答: {correct_ans}\n学生回答: {student_ans}")
            try:
                resp = model.invoke([sys_msg, user_msg])
                # Extremely primitive json extract
                txt = resp.content.replace("```json", "").replace("```", "").strip()
                res_obj = json.loads(txt)
                is_correct = res_obj.get("is_correct", False)
                explanation = res_obj.get("explanation", "自动批阅完成")
            except Exception as e:
                logger.warning(f"LLM grading failed: {e}")
                is_correct = len(student_ans) > 5 # dummy fallback
                explanation = "系统自动批阅回退策略"
                
        if is_correct:
            total_correct += 1
            
        results.append({
            "question_id": q["id"],
            "question_md": q["question_md"],
            "question_type": q["type"],
            "student_answer": student_ans,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "explanation": explanation,
            "node_id": q.get("node_id"),
            "node_title": q.get("node_title")
        })
        
        # Node State tracking logic
        node_id = q.get("node_id")
        if node_id:
            # Update NodeState
            score_delta = 10 if is_correct else -5
            # Inline state update instead of calling tool to save overhead
            stmt = select(StudentNodeState).where(
                StudentNodeState.student_id == req.student_id,
                StudentNodeState.node_id == node_id
            )
            ns_result = await db.execute(stmt)
            ns = ns_result.scalars().first()
            if ns:
                ns.health_score = max(0, min(100, ns.health_score + score_delta))
            else:
                db.add(StudentNodeState(student_id=req.student_id, node_id=node_id, health_score=max(0, 50+score_delta), is_unlocked=True))
                
            # Log Mistake if wrong
            if not is_correct:
                db.add(StudentMistake(
                    student_id=req.student_id,
                    node_id=node_id,
                    error_reason=explanation,
                    status=MistakeStatus.ACTIVE,
                    consecutive_correct_count=0
                ))
                
    final_score = round((total_correct / total_questions) * req.paper_metadata.get("total_score", 100)) if total_questions else 0
    
    # Save TestRecord
    tr = TestRecord(
        test_paper_id=req.exam_id,
        student_score=final_score,
        answers_json=json.dumps([a.dict() for a in req.answers], ensure_ascii=False),
        grading_json=json.dumps(results, ensure_ascii=False)
    )
    db.add(tr)
    await db.commit()
    
    return {
        "status": "ok",
        "exam_result": {
            "exam_id": req.exam_id,
            "title": req.paper_metadata.get("title", "Exam"),
            "score": final_score,
            "total_score": req.paper_metadata.get("total_score", 100),
            "correct_count": total_correct,
            "total_count": total_questions,
            "accuracy_pct": round((total_correct/total_questions)*100) if total_questions else 0,
            "time_used_sec": req.time_used_sec,
            "per_question": results
        }
    }


@router.get("/{paper_id}/result")
async def get_exam_result(paper_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get the result timeline mapping for a particular exam.
    """
    stmt = select(TestRecord).where(TestRecord.test_paper_id == paper_id)
    result = await db.execute(stmt)
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Test record not found")
        
    grading_json = json.loads(record.grading_json) if record.grading_json else []
    
    return {
        "status": "ok",
        "exam_result": {
            "exam_id": paper_id,
            "score": record.student_score,
            "per_question": grading_json
        }
    }
