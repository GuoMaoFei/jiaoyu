import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import KnowledgeNode, KnowledgeContent
from app.models.user import StudentNodeState
from app.models.testing import StudentMistake
from app.models.quiz import NodeQuiz
from app.schemas.quiz import (
    QuizConfig,
    QuestionGenerate,
    QuestionWithAnswer,
    QuestionResult,
    QuizPaper,
    QuizResult,
    QuizHistoryItem,
    NodeHealthChange,
)
from app.utils.llm_router import get_heavy_model, get_fast_model
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


async def get_node_content(node_id: str, db: AsyncSession) -> Optional[KnowledgeNode]:
    """获取节点及其内容"""
    result = await db.execute(select(KnowledgeNode).where(KnowledgeNode.id == node_id))
    return result.scalars().first()


async def get_student_node_state(
    student_id: str, node_id: str, db: AsyncSession
) -> Optional[StudentNodeState]:
    """获取学生在特定节点的学习状态"""
    result = await db.execute(
        select(StudentNodeState).where(
            StudentNodeState.student_id == student_id,
            StudentNodeState.node_id == node_id,
        )
    )
    return result.scalars().first()


async def get_node_mistakes(
    student_id: str, node_id: str, db: AsyncSession
) -> List[StudentMistake]:
    """获取学生在特定节点的错题"""
    result = await db.execute(
        select(StudentMistake).where(
            StudentMistake.student_id == student_id, StudentMistake.node_id == node_id
        )
    )
    return list(result.scalars().all())


async def analyze_quiz_config(
    node: KnowledgeNode,
    student_state: Optional[StudentNodeState],
    mistakes: List[StudentMistake],
    db: AsyncSession,
) -> QuizConfig:
    """
    LLM 分析节点，决定出题策略
    """
    model = get_heavy_model(temperature=0.3)

    node_summary = ""
    if node.pi_nodes_json:
        for pi in node.pi_nodes_json[:3]:
            if isinstance(pi, dict) and "summary" in pi:
                node_summary += f"- {pi.get('title', '')}: {pi.get('summary', '')}\n"

    health_score = student_state.health_score if student_state else 50
    mistake_count = len(mistakes)

    prompt = f"""你是资深教育专家，需要为学生设计微测试卷。

## 知识点信息
标题：{node.title}
层级：{node.level}
内容摘要：{node_summary[:500] if node_summary else "暂无详细摘要"}
是否为教材重点章节：{"是" if node.is_key_node else "否"}

## 学生学情
当前健康度：{health_score}（0-100，85以上为掌握）
历史错题数：{mistake_count}
重点章节：{"是" if node.is_key_node else "否"}

请分析并返回 JSON 格式的出题配置：
{{
    "question_count": 3-6,
    "time_limit_min": 8-20,
    "difficulty_level": "easy|medium|hard",
    "question_types": [
        {{"type": "SINGLE_CHOICE", "count": 1}},
        {{"type": "FILL_BLANK", "count": 1}},
        {{"type": "SHORT_ANSWER", "count": 1}}
    ],
    "reasoning": "设计理由..."
}}

要求：
1. 至少包含1道选择题（快速检测）
2. 重点章节可适当增加题数和时长
3. 根据学生历史表现调整难度
"""

    try:
        response = model.invoke([SystemMessage(content=prompt)])
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        config_data = json.loads(content.strip())

        return QuizConfig(
            question_count=config_data.get("question_count", 4),
            time_limit_min=config_data.get("time_limit_min", 12),
            difficulty_level=config_data.get("difficulty_level", "medium"),
            question_types=config_data.get("question_types", []),
            reasoning=config_data.get("reasoning", ""),
        )
    except Exception as e:
        logger.warning(f"LLM config analysis failed, using defaults: {e}")
        return QuizConfig(
            question_count=4,
            time_limit_min=12,
            difficulty_level="medium",
            question_types=[
                {"type": "SINGLE_CHOICE", "count": 1},
                {"type": "FILL_BLANK", "count": 2},
                {"type": "SHORT_ANSWER", "count": 1},
            ],
            reasoning="使用默认配置",
        )


async def generate_quiz_questions(
    node: KnowledgeNode, config: QuizConfig
) -> List[QuestionGenerate]:
    """
    LLM 根据配置生成具体题目
    """
    model = get_heavy_model(temperature=0.7)

    node_summary = ""
    if node.pi_nodes_json:
        for pi in node.pi_nodes_json[:5]:
            if isinstance(pi, dict):
                title = pi.get("title", "")
                summary = pi.get("summary", "")
                node_summary += f"### {title}\n{summary}\n\n"

    type_str = ""
    for qt in config.question_types:
        for _ in range(qt.get("count", 0)):
            type_str += f"- {qt['type']}\n"

    prompt = f"""根据以下要求生成 {config.question_count} 道题目。

## 知识点
标题：{node.title}
内容：
{node_summary[:1500]}

## 出题要求
题型分布：
{type_str}
难度：{config.difficulty_level}

## 输出格式（严格 JSON）
{{
    "questions": [
        {{
            "type": "SINGLE_CHOICE",
            "question_md": "题干（选择题需要包含 A/B/C/D 选项）",
            "options": ["A. ...", "B. ...", "C. ...", "D. ..."] 或 null,
            "correct_answer": "B",
            "solution_steps": "详细解题思路（Markdown格式）",
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": 1-5
        }}
    ]
}}

要求：
1. 题目必须紧扣知识点核心概念
2. 每道题都要有详细解题思路 solution_steps（用于后续展示）
3. 使用 Markdown 格式，数学公式用 $...$
4. 选择题必须提供4个选项
5. 难度递进：第1题最简单，最后一题最难
6. 返回严格 JSON 格式，不要有其他文字
"""

    try:
        response = model.invoke([SystemMessage(content=prompt)])
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        questions = []

        for q in data.get("questions", []):
            questions.append(
                QuestionGenerate(
                    type=q.get("type", "SINGLE_CHOICE"),
                    question_md=q.get("question_md", ""),
                    options=q.get("options"),
                    correct_answer=q.get("correct_answer", ""),
                    solution_steps=q.get("solution_steps", ""),
                    knowledge_points=q.get("knowledge_points", []),
                    difficulty=q.get("difficulty", 3),
                )
            )

        return questions[: config.question_count]

    except Exception as e:
        logger.warning(f"LLM question generation failed: {e}")
        return []


async def save_quiz_paper(
    student_id: str,
    node: KnowledgeNode,
    config: QuizConfig,
    questions: List[QuestionGenerate],
    db: AsyncSession,
) -> QuizPaper:
    """保存试卷到数据库"""
    quiz = NodeQuiz(
        student_id=student_id,
        node_id=node.id,
        node_title=node.title,
        is_key_node=1 if node.is_key_node else 0,
        question_count=len(questions),
        time_limit_min=config.time_limit_min,
        difficulty_level=config.difficulty_level,
        questions_json=json.dumps(
            [q.model_dump() for q in questions], ensure_ascii=False
        ),
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)

    return QuizPaper(
        id=quiz.id,
        node_id=node.id,
        node_title=node.title,
        is_key_node=bool(node.is_key_node),
        question_count=len(questions),
        time_limit_min=config.time_limit_min,
        difficulty_level=config.difficulty_level,
        questions=questions,
        created_at=quiz.created_at,
    )


async def generate_node_quiz(
    student_id: str, node_id: str, db: AsyncSession
) -> QuizPaper:
    """生成微测完整流程"""
    existing_unfinished = await get_unfinished_quiz(student_id, node_id, db)
    if existing_unfinished:
        raise ValueError("已有未完成的测试，请先完成或删除现有测试")

    node = await get_node_content(node_id, db)
    if not node:
        raise ValueError(f"Node {node_id} not found")

    student_state = await get_student_node_state(student_id, node_id, db)
    mistakes = await get_node_mistakes(student_id, node_id, db)

    config = await analyze_quiz_config(node, student_state, mistakes, db)
    questions = await generate_quiz_questions(node, config)

    if not questions:
        raise ValueError("Failed to generate questions")

    return await save_quiz_paper(student_id, node, config, questions, db)


async def get_unfinished_quiz(
    student_id: str, node_id: str, db: AsyncSession
) -> Optional[QuizPaper]:
    """获取未完成的测试"""
    result = await db.execute(
        select(NodeQuiz)
        .where(
            NodeQuiz.student_id == student_id,
            NodeQuiz.node_id == node_id,
            NodeQuiz.submitted_at == None,  # noqa: E711
        )
        .order_by(NodeQuiz.created_at.desc())
        .limit(1)
    )
    quiz = result.scalars().first()

    if not quiz:
        return None

    import json

    questions_data = json.loads(quiz.questions_json)

    # 为旧数据添加缺失的字段
    for q in questions_data:
        if "correct_answer" not in q:
            q["correct_answer"] = ""
        if "solution_steps" not in q:
            q["solution_steps"] = ""

    return QuizPaper(
        id=quiz.id,
        node_id=quiz.node_id,
        node_title=quiz.node_title,
        is_key_node=bool(quiz.is_key_node),
        question_count=quiz.question_count,
        time_limit_min=quiz.time_limit_min,
        difficulty_level=quiz.difficulty_level,
        questions=questions_data,
        created_at=quiz.created_at,
    )


async def save_quiz_progress(
    quiz_id: str, answers: list, current_index: int, db: AsyncSession
):
    """保存答题进度"""
    result = await db.execute(select(NodeQuiz).where(NodeQuiz.id == quiz_id))
    quiz = result.scalars().first()
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found")

    import json
    from datetime import datetime

    progress_data = {
        "answers": answers,
        "current_index": current_index,
        "saved_at": datetime.now().isoformat(),
    }
    quiz.answers_json = json.dumps(progress_data, ensure_ascii=False)
    await db.commit()


async def get_quiz_by_id(quiz_id: str, db: AsyncSession) -> Optional[NodeQuiz]:
    """根据 ID 获取试卷"""
    result = await db.execute(select(NodeQuiz).where(NodeQuiz.id == quiz_id))
    return result.scalars().first()


async def grade_quiz(
    questions: List[QuestionWithAnswer], answers: List[Dict[str, Any]]
) -> tuple[int, float, List[QuestionResult]]:
    """批改试卷"""
    model = get_fast_model(temperature=0.0)

    correct_count = 0
    results = []

    answer_map = {a["question_index"]: a["answer"] for a in answers}

    for i, q in enumerate(questions):
        student_answer = answer_map.get(i, "")
        is_correct = False

        if q.type in ["SINGLE_CHOICE", "MULTI_CHOICE", "FILL_BLANK"]:
            is_correct = (
                student_answer.strip().lower() == q.correct_answer.strip().lower()
            )
        else:
            prompt = f"""判断学生的简答题答案是否正确。

题目：{q.question_md}
正确答案：{q.correct_answer}
学生答案：{student_answer}

返回 JSON：{{"is_correct": true/false}}
"""
            try:
                resp = model.invoke([SystemMessage(content=prompt)])
                content = resp.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                data = json.loads(content.strip())
                is_correct = data.get("is_correct", False)
            except:
                is_correct = len(student_answer.strip()) > 10

        if is_correct:
            correct_count += 1

        results.append(
            QuestionResult(
                question_index=i,
                type=q.type,
                question_md=q.question_md,
                options=q.options,
                student_answer=student_answer,
                correct_answer=q.correct_answer,
                is_correct=is_correct,
                solution_steps=q.solution_steps,
                knowledge_points=q.knowledge_points,
            )
        )

    accuracy = (correct_count / len(questions)) * 100 if questions else 0

    return correct_count, accuracy, results


async def update_node_health(
    student_id: str, node_id: str, results: List[QuestionResult], db: AsyncSession
) -> NodeHealthChange:
    """更新节点健康度"""
    result = await db.execute(
        select(StudentNodeState).where(
            StudentNodeState.student_id == student_id,
            StudentNodeState.node_id == node_id,
        )
    )
    state = result.scalars().first()

    correct_count = sum(1 for r in results if r.is_correct)
    score_delta = correct_count * 5

    before_score = state.health_score if state else 50

    if state:
        state.health_score = max(0, min(100, state.health_score + score_delta))
    else:
        state = StudentNodeState(
            student_id=student_id,
            node_id=node_id,
            health_score=max(0, min(100, 50 + score_delta)),
            is_unlocked=True,
        )
        db.add(state)

    await db.commit()

    after_score = state.health_score if state else before_score

    return NodeHealthChange(
        before=before_score, after=after_score, change=after_score - before_score
    )


async def add_mistakes_to_review(
    student_id: str, node_id: str, results: List[QuestionResult], db: AsyncSession
):
    """错题加入艾宾浩斯复习队列"""
    from app.models.testing import StudentMistake, MistakeStatus

    wrong_results = [r for r in results if not r.is_correct]

    for r in wrong_results:
        mistake = StudentMistake(
            student_id=student_id,
            node_id=node_id,
            error_reason=f"微测错题：{r.question_md[:100]}...",
            status=MistakeStatus.ACTIVE,
            consecutive_correct_count=0,
        )
        db.add(mistake)

    await db.commit()


async def submit_quiz(
    student_id: str,
    quiz_id: str,
    answers: List[Dict[str, Any]],
    time_used_sec: int,
    db: AsyncSession,
) -> QuizResult:
    """提交并批改微测"""
    quiz = await get_quiz_by_id(quiz_id, db)
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found")

    questions_data = json.loads(quiz.questions_json)
    questions = [QuestionWithAnswer(**q) for q in questions_data]

    correct_count, accuracy, results = await grade_quiz(questions, answers)

    health_change = await update_node_health(student_id, quiz.node_id, results, db)

    if correct_count < len(questions):
        await add_mistakes_to_review(student_id, quiz.node_id, results, db)

    quiz.time_used_sec = time_used_sec
    quiz.score = correct_count
    quiz.accuracy_pct = accuracy
    quiz.answers_json = json.dumps(answers, ensure_ascii=False)
    quiz.results_json = json.dumps(
        [r.model_dump() for r in results], ensure_ascii=False
    )
    quiz.submitted_at = datetime.now(timezone.utc)

    await db.commit()

    return QuizResult(
        quiz_id=quiz_id,
        score=correct_count,
        accuracy_pct=accuracy,
        time_used_sec=time_used_sec,
        per_question=results,
        node_health_change=health_change,
    )


async def get_quiz_history(
    student_id: str, node_id: str, db: AsyncSession
) -> List[QuizHistoryItem]:
    """获取历史微测记录"""
    result = await db.execute(
        select(NodeQuiz)
        .where(NodeQuiz.student_id == student_id, NodeQuiz.node_id == node_id)
        .order_by(NodeQuiz.created_at.desc())
    )
    quizzes = result.scalars().all()

    return [
        QuizHistoryItem(
            id=q.id,
            score=q.score,
            accuracy_pct=q.accuracy_pct,
            question_count=q.question_count,
            time_used_sec=q.time_used_sec,
            created_at=q.created_at,
        )
        for q in quizzes
    ]
