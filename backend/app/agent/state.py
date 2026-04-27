from typing import TypedDict, Annotated, Sequence, Any, Dict, Optional
import operator
from langchain_core.messages import BaseMessage, AIMessage


def strip_thinking_blocks(msg: AIMessage) -> AIMessage:
    """Convert AIMessage list content to plain text string.

    MiniMax via ChatAnthropic returns content as a list of dicts
    (e.g. [{'text': '...', 'type': 'text', 'index': 1}]), which causes
    duplicate tool_use serialization and odd formatting in subsequent API
    calls. Always flatten to a plain string.
    """
    content = msg.content
    if not isinstance(content, list):
        return msg

    text_parts = []
    for b in content:
        btype = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
        if btype == "text":
            text = b.get("text") if isinstance(b, dict) else getattr(b, "text", "")
            if text:
                text_parts.append(text)

    return AIMessage(
        content="".join(text_parts) if text_parts else "",
        tool_calls=msg.tool_calls,
        id=msg.id,
        response_metadata=msg.response_metadata,
        usage_metadata=msg.usage_metadata,
    )

class TutorContext(TypedDict, total=False):
    """Holds context specific to the Tutor Agent's tree search operations and Memory Overlay"""
    current_health_score: Optional[int]
    historical_mistakes: Optional[str]
    retrieved_content: Optional[str]
    # Guided Learning context
    lesson_step: Optional[str]       # e.g. "IMPORT", "EXPLAIN", "EXAMPLE", "PRACTICE", "SUMMARY"
    node_title: Optional[str]        # Title of the knowledge node being studied
    node_content: Optional[str]      # Content preview of the knowledge node
    example_content: Optional[str]   # Example question content for EXAMPLE step
    subject: Optional[str]           # 学科名称，如"数学"、"物理"

class AssessorContext(TypedDict, total=False):
    """Holds context specific to the Assessor Agent's evaluation operations"""
    target_node_id: Optional[str]
    last_assessment_result: Optional[str]  # e.g., "correct", "incorrect", "partial"
    last_score_delta: Optional[int]

class PlannerContext(TypedDict, total=False):
    """Holds context specific to the Planner Agent's scheduling operations"""
    plan_created: Optional[bool]
    total_nodes_planned: Optional[int]

class VariantContext(TypedDict, total=False):
    """Holds context specific to the Variant Agent's question generation"""
    target_node_id: Optional[str]
    questions_generated: Optional[int]

class ReporterContext(TypedDict, total=False):
    """Holds context specific to the Reporter Agent's analytics"""
    report_type: Optional[str]  # e.g. "weekly", "chapter"

class AgentState(TypedDict):
    """The global StateGraph dictionary passed between all agents."""
    session_id: str
    student_id: str
    material_id: Optional[str]
    node_id: Optional[str]
    lesson_step: Optional[str]  # Current guided learning step
    subject: Optional[str]      # 学科名称，由 supervisor 从 material_id 派生
    
    # LangGraph standard pattern for appending messages
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # Control flow
    current_intent: str # e.g., "tutor", "assess", "plan"
    
    # Agent-Specific sub-states
    tutor_context: TutorContext
    assessor_context: AssessorContext
    planner_context: PlannerContext
    variant_context: VariantContext
    reporter_context: ReporterContext
    
    # Generic dumping ground for tool outputs if needed
    tool_outputs: Dict[str, Any]
