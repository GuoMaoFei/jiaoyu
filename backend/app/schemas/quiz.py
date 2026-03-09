from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class QuestionGenerate(BaseModel):
    """单道题目（生成时含解题思路）"""

    type: str = Field(
        ..., description="SINGLE_CHOICE, MULTI_CHOICE, FILL_BLANK, SHORT_ANSWER"
    )
    question_md: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    solution_steps: Optional[str] = None
    knowledge_points: List[str] = Field(default_factory=list)
    difficulty: int = Field(ge=1, le=5, description="1-5 难度")


class QuestionWithAnswer(BaseModel):
    """单道题目（包含答案，用于提交后显示）"""

    type: str
    question_md: str
    options: Optional[List[str]] = None
    correct_answer: str
    solution_steps: str
    knowledge_points: List[str]
    difficulty: int


class QuestionResult(BaseModel):
    """单题批改结果"""

    question_index: int
    type: str
    question_md: str
    options: Optional[List[str]] = None
    student_answer: str
    correct_answer: str
    is_correct: bool
    solution_steps: str
    knowledge_points: List[str]


class QuizConfig(BaseModel):
    """LLM 智能分析结果"""

    question_count: int = Field(ge=3, le=6, description="题目数量")
    time_limit_min: int = Field(ge=8, le=20, description="建议时长（分钟）")
    difficulty_level: str = Field(description="easy, medium, hard")
    question_types: List[dict] = Field(description="题型分布")
    reasoning: str = Field(description="设计理由")


class QuizGenerateRequest(BaseModel):
    """生成微测请求"""

    student_id: str
    node_id: str


class QuizAnswerInput(BaseModel):
    """学生答案"""

    question_index: int
    answer: str


class QuizSubmitRequest(BaseModel):
    """提交微测请求"""

    student_id: str
    quiz_id: str
    answers: List[QuizAnswerInput]
    time_used_sec: int


class QuizPaper(BaseModel):
    """微测试卷（不含答案）"""

    id: str
    node_id: str
    node_title: str
    is_key_node: bool = False
    question_count: int
    time_limit_min: int
    difficulty_level: str
    questions: List[QuestionGenerate]
    created_at: datetime


class QuizPaperWithAnswers(BaseModel):
    """微测试卷（包含答案，用于结果页）"""

    id: str
    node_id: str
    node_title: str
    is_key_node: bool = False
    question_count: int
    time_limit_min: int
    difficulty_level: str
    questions: List[QuestionWithAnswer]
    created_at: datetime


class QuizHistoryItem(BaseModel):
    """历史微测记录"""

    id: str
    score: Optional[int]
    accuracy_pct: Optional[float]
    question_count: int
    time_used_sec: Optional[int]
    created_at: datetime


class NodeHealthChange(BaseModel):
    """节点健康度变化"""

    before: int
    after: int
    change: int


class QuizResult(BaseModel):
    """微测结果"""

    quiz_id: str
    score: int
    accuracy_pct: float
    time_used_sec: int
    per_question: List[QuestionResult]
    node_health_change: NodeHealthChange
