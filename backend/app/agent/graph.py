import json
from typing import Literal

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.agent.sub_agents.import_agent import import_agent
from app.agent.sub_agents.explain_agent import explain_agent
from app.agent.sub_agents.example_agent import example_agent
from app.agent.sub_agents.practice_agent import practice_agent
from app.agent.sub_agents.summary_agent import summary_agent
from app.agent.sub_agents.assessor import assessor_node
from app.agent.sub_agents.planner import planner_node
from app.agent.sub_agents.variant import variant_node
from app.agent.sub_agents.reporter import reporter_node
from app.agent.tools.pageindex_tools import search_knowledge_tree
from app.agent.tools.kp_tools import search_knowledge_points
from app.models.material import KnowledgeNode, Material
from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.agent.tools.assessment_tools import save_assessment
from app.agent.tools.planner_tools import create_study_plan, get_material_node_list
from app.agent.tools.variant_tools import get_node_questions, save_variant_question
from app.agent.tools.reporter_tools import (
    get_chapter_health_report,
    get_mistake_summary,
)
from app.services.memory_overlay import get_student_memory_overlay

all_tools = [
    search_knowledge_tree,
    search_knowledge_points,
    save_assessment,
    create_study_plan,
    get_material_node_list,
    get_node_questions,
    save_variant_question,
    get_chapter_health_report,
    get_mistake_summary,
]
tool_node = ToolNode(all_tools)

_STEP_NODE_MAP = {
    "IMPORT": "import",
    "EXPLAIN": "explain",
    "EXAMPLE": "example",
    "PRACTICE": "practice",
    "SUMMARY": "summary",
}


async def supervisor_node(state: AgentState):
    print("--- ENTER SUPERVISOR NODE ---")
    current_intent = state.get("current_intent") or "tutor"

    student_id = state.get("student_id", "")
    material_id = state.get("material_id")

    overlay = await get_student_memory_overlay(student_id, material_id)

    print(
        f"--- MEMORY OVERLAY: avg_score={overlay['avg_health_score']}, "
        f"weak_nodes={len(overlay['weak_nodes'])}, "
        f"weakest={overlay['weakest_node_id']} ---"
    )

    tutor_ctx = state.get("tutor_context", {})
    tutor_ctx["current_health_score"] = overlay["avg_health_score"]
    tutor_ctx["historical_mistakes"] = overlay["historical_mistakes_summary"]

    tutor_ctx["lesson_step"] = state.get("lesson_step")

    if material_id:
        async with AsyncSessionLocal() as db:
            mat_result = await db.execute(select(Material).where(Material.id == material_id))
            mat = mat_result.scalars().first()
            if mat:
                tutor_ctx["subject"] = mat.subject
                print(f"--- MATERIAL SUBJECT: {mat.subject} ---")

    tool_outputs = state.get("tool_outputs", {})
    if "example_content" in tool_outputs:
        tutor_ctx["example_content"] = tool_outputs["example_content"]

    node_id = state.get("node_id")
    print(f"--- NODE_ID FROM STATE: {node_id} ---")
    if node_id:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id == node_id)
            )
            node = result.scalars().first()
            if node:
                tutor_ctx["node_title"] = node.title
                prefetched = False
                if material_id and student_id:
                    try:
                        knowledge_result = await search_knowledge_tree.ainvoke({
                            "query": node.title,
                            "material_id": material_id,
                            "student_id": student_id,
                            "current_node_id": str(node_id),
                            "expert_preference": overlay.get("historical_mistakes_summary", ""),
                        })
                        tutor_ctx["node_content"] = knowledge_result
                        tutor_ctx["knowledge_prefetched"] = True
                        prefetched = True
                        print(f"--- PREFETCHED KNOWLEDGE: {len(knowledge_result)} chars ---")
                    except Exception as e:
                        print(f"--- PREFETCH FAILED: {e}, fallback to summary ---")

                # 预取当前节点关联的知识点（含层级和教材映射关系）
                try:
                    kp_result = await db.execute(
                        select(KnowledgePoint)
                        .join(KnowledgePointMapping, KnowledgePoint.id == KnowledgePointMapping.knowledge_point_id)
                        .where(KnowledgePointMapping.knowledge_node_id == node.id)
                    )
                    kp_rows = kp_result.scalars().all()
                    if kp_rows:
                        # 构建结构化的知识点上下文
                        kp_lines = []
                        for kp in kp_rows:
                            level_indent = "  " * (kp.level - 1)
                            kp_lines.append(
                                f"{level_indent}- [{kp.title}] (层级{kp.level}) {kp.summary or ''}"
                            )
                            if kp.keywords:
                                kp_lines.append(f"{level_indent}  关键词: {kp.keywords}")
                        tutor_ctx["knowledge_points_context"] = "\n".join(kp_lines)
                        print(f"--- PREFETCHED {len(kp_rows)} KNOWLEDGE POINTS for node {node_id} ---")
                    else:
                        tutor_ctx["knowledge_points_context"] = "（本节暂无知识点标签）"
                except Exception as e:
                    print(f"--- KP PREFETCH FAILED: {e} ---")
                    tutor_ctx["knowledge_points_context"] = ""
                if not prefetched:
                    _node_summary = ""
                    if (
                        node.pi_nodes_json
                        and isinstance(node.pi_nodes_json, list)
                        and len(node.pi_nodes_json) > 0
                    ):
                        _node_summary = node.pi_nodes_json[0].get("summary", "")
                    tutor_ctx["node_content"] = (
                        _node_summary
                        or f"本节主题：{node.title}。请使用 search_knowledge_tree 工具检索详细内容。"
                    )
                    print(f"--- INJECTED NODE: title='{node.title}', preview_len={len(_node_summary)} ---")
            else:
                print(f"--- WARNING: node_id={node_id} NOT FOUND in database ---")

    assessor_ctx = state.get("assessor_context", {})
    assessor_ctx["target_node_id"] = overlay["weakest_node_id"]

    return {
        "current_intent": current_intent,
        "subject": tutor_ctx.get("subject"),
        "tutor_context": tutor_ctx,
        "assessor_context": assessor_ctx,
    }


def router_after_supervisor(state: AgentState) -> str:
    intent = state.get("current_intent")
    if intent in ("assessor", "planner", "variant", "reporter"):
        return intent

    lesson_step = state.get("lesson_step") or "EXPLAIN"
    if lesson_step == "COMPLETED":
        print("--- SUPERVISOR: LESSON COMPLETED ---")
        return END

    step_node = _STEP_NODE_MAP.get(lesson_step, "explain")
    print(f"--- SUPERVISOR: routing to step '{step_node}' (lesson_step={lesson_step}) ---")
    return step_node


def _router_after_step(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        print(f"--- STEP ROUTING TO TOOLS: {last_message.tool_calls[0].get('name')} ---")
        return "tools"
    return END


def _router_after_step_with_assessor(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        print(f"--- STEP ROUTING TO TOOLS: {last_message.tool_calls[0].get('name')} ---")
        return "tools"

    print("--- STEP COMPLETED, HANDING OFF TO ASSESSOR ---")
    return "assessor"


def router_after_assessor(state: AgentState) -> str:
    messages = state["messages"]
    if not messages:
        return END

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"--- ASSESSOR ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"

    print("--- ASSESSOR COMPLETED EVALUATION ---")
    return END


def router_after_tools(state: AgentState) -> str:
    messages = state["messages"]

    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_name = msg.tool_calls[0].get("name", "")
            if tool_name == "save_assessment":
                print("--- TOOLS DONE, RETURNING TO ASSESSOR ---")
                return "assessor"
            elif tool_name in ("create_study_plan", "get_material_node_list"):
                print("--- TOOLS DONE, RETURNING TO PLANNER ---")
                return "planner"
            elif tool_name in ("get_node_questions", "save_variant_question"):
                print("--- TOOLS DONE, RETURNING TO VARIANT ---")
                return "variant"
            elif tool_name in ("get_chapter_health_report", "get_mistake_summary"):
                print("--- TOOLS DONE, RETURNING TO REPORTER ---")
                return "reporter"
            else:
                # search_knowledge_tree — route back to the step that called it
                # Walk further back to find which step agent issued the call
                for prev in messages[:messages.index(msg)]:
                    if hasattr(prev, "tool_calls") and prev.tool_calls:
                        pass
                # Fallback: determine by lesson_step
                lesson_step = state.get("lesson_step") or "EXPLAIN"
                step_node = _STEP_NODE_MAP.get(lesson_step, "explain")
                print(f"--- TOOLS DONE, RETURNING TO {step_node} ---")
                return step_node
        if isinstance(msg, ToolMessage):
            continue
        break

    lesson_step = state.get("lesson_step") or "EXPLAIN"
    step_node = _STEP_NODE_MAP.get(lesson_step, "explain")
    print(f"--- TOOLS DONE, FALLBACK TO {step_node} ---")
    return step_node


def router_after_planner(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        print(f"--- PLANNER ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"
    print("--- PLANNER COMPLETED PLAN ---")
    return END


def router_after_variant(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        print(f"--- VARIANT ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"
    print("--- VARIANT COMPLETED ---")
    return END


def router_after_reporter(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        print(f"--- REPORTER ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"
    print("--- REPORTER COMPLETED ---")
    return END


# Build the Graph
builder = StateGraph(AgentState)

# Add Nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("import", import_agent)
builder.add_node("explain", explain_agent)
builder.add_node("example", example_agent)
builder.add_node("practice", practice_agent)
builder.add_node("summary", summary_agent)
builder.add_node("assessor", assessor_node)
builder.add_node("planner", planner_node)
builder.add_node("variant", variant_node)
builder.add_node("reporter", reporter_node)
builder.add_node("tools", tool_node)

# Add Edges
builder.add_edge(START, "supervisor")

builder.add_conditional_edges(
    "supervisor",
    router_after_supervisor,
    {
        "import": "import",
        "explain": "explain",
        "example": "example",
        "practice": "practice",
        "summary": "summary",
        "assessor": "assessor",
        "planner": "planner",
        "variant": "variant",
        "reporter": "reporter",
        END: END,
    },
)

# IMPORT / SUMMARY → END (no assessment)
builder.add_conditional_edges(
    "import", _router_after_step, {"tools": "tools", END: END}
)
builder.add_conditional_edges(
    "summary", _router_after_step, {"tools": "tools", END: END}
)

# EXPLAIN / EXAMPLE / PRACTICE → assessor
builder.add_conditional_edges(
    "explain", _router_after_step_with_assessor, {"tools": "tools", "assessor": "assessor", END: END}
)
builder.add_conditional_edges(
    "example", _router_after_step_with_assessor, {"tools": "tools", "assessor": "assessor", END: END}
)
builder.add_conditional_edges(
    "practice", _router_after_step_with_assessor, {"tools": "tools", "assessor": "assessor", END: END}
)

builder.add_conditional_edges(
    "assessor", router_after_assessor, {"tools": "tools", END: END}
)

builder.add_conditional_edges(
    "planner", router_after_planner, {"tools": "tools", END: END}
)

builder.add_conditional_edges(
    "variant", router_after_variant, {"tools": "tools", END: END}
)

builder.add_conditional_edges(
    "reporter", router_after_reporter, {"tools": "tools", END: END}
)

builder.add_conditional_edges(
    "tools",
    router_after_tools,
    {
        "import": "import",
        "explain": "explain",
        "example": "example",
        "practice": "practice",
        "summary": "summary",
        "assessor": "assessor",
        "planner": "planner",
        "variant": "variant",
        "reporter": "reporter",
    },
)

memory = MemorySaver()
treeedu_graph = builder.compile(checkpointer=memory)
