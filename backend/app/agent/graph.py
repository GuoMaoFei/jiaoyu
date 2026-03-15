import json
from typing import Literal

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.agent.sub_agents.tutor import tutor_node
from app.agent.sub_agents.assessor import assessor_node
from app.agent.sub_agents.planner import planner_node
from app.agent.sub_agents.variant import variant_node
from app.agent.sub_agents.reporter import reporter_node
from app.agent.tools.pageindex_tools import search_knowledge_tree
from app.models.material import KnowledgeNode
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
from app.utils.llm_router import get_fast_model

# We create the tool node that LangGraph will call when models return tool_calls.
# This single ToolNode handles tools from ALL sub-agents.
# Note: search_knowledge_tree is now dynamically created in tutor_node,
# but we still need a static version or a placeholder if the model expects it in the global node.
# For now, we will add it back to the tools list once we restore it in pageindex_tools.
all_tools = [
    search_knowledge_tree,
    save_assessment,
    create_study_plan,
    get_material_node_list,
    get_node_questions,
    save_variant_question,
    get_chapter_health_report,
    get_mistake_summary,
]
tool_node = ToolNode(all_tools)


async def supervisor_node(state: AgentState):
    """
    The Supervisor decides what sub-agent should handle the user's input.
    It queries the database for the student's real learning profile (Memory Overlay)
    and injects it into the agent contexts.

    For Sprint 3 PoC, intent is still locked to "tutor".
    In the future, this node will use get_fast_model() to classify the intent.
    """
    print("--- ENTER SUPERVISOR NODE ---")
    # Use incoming intent if provided, otherwise mock to tutor
    current_intent = state.get("current_intent") or "tutor"

    # === REAL Memory Overlay Injection ===
    # Query the student's actual learning profile from the database
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

    # Inject Guided Learning Step Context
    tutor_ctx["lesson_step"] = state.get("lesson_step")

    # Check if there are pre-injected tool outputs from guided learning
    tool_outputs = state.get("tool_outputs", {})
    if "example_content" in tool_outputs:
        tutor_ctx["example_content"] = tool_outputs["example_content"]

    # === Node Content Injection ===
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
                # Extract summary from pi_nodes_json since content_md was moved to KnowledgeContent
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
                print(
                    f"--- INJECTED NODE: title='{node.title}', preview_len={len(_node_summary)} ---"
                )
            else:
                print(f"--- WARNING: node_id={node_id} NOT FOUND in database ---")

    assessor_ctx = state.get("assessor_context", {})
    assessor_ctx["target_node_id"] = overlay["weakest_node_id"]

    return {
        "current_intent": current_intent,
        "tutor_context": tutor_ctx,
        "assessor_context": assessor_ctx,
    }


def router_after_supervisor(state: AgentState) -> str:
    """Routes from supervisor to the appropriate sub-agent"""
    intent = state.get("current_intent")
    if intent == "assessor":
        return "assessor"
    if intent == "planner":
        return "planner"
    if intent == "variant":
        return "variant"
    if intent == "reporter":
        return "reporter"
    # Default to tutor
    return "tutor"


def router_after_tutor(state: AgentState) -> str:
    """Routes after the tutor model generates a response."""
    messages = state["messages"]
    last_message = messages[-1]

    # If the model decided to call a tool, route to tools
    if last_message.tool_calls:
        print(f"--- TUTOR ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"

    # Tutor gave a final answer -> hand off to Assessor for implicit evaluation
    print("--- TUTOR PROVIDED FINAL ANSWER, HANDING OFF TO ASSESSOR ---")
    return "assessor"


def router_after_assessor(state: AgentState) -> str:
    """Routes after the assessor model generates a response."""
    messages = state["messages"]
    last_message = messages[-1]

    # If the assessor wants to call tool (save_assessment), route to tools
    if last_message.tool_calls:
        print(f"--- ASSESSOR ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"

    # Otherwise, assessor is done
    print("--- ASSESSOR COMPLETED EVALUATION ---")
    return END


def router_after_tools(state: AgentState) -> str:
    """
    Routes after a tool has been executed.
    We need to figure out which agent issued the tool call so we route back to them.
    """
    messages = state["messages"]

    # Walk backwards to find the AI message that triggered the tool call
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
                print("--- TOOLS DONE, RETURNING TO TUTOR ---")
                return "tutor"
        # Stop looking if we hit a ToolMessage (the result we just produced)
        if isinstance(msg, ToolMessage):
            continue
        break

    # Fallback to tutor
    print("--- TOOLS DONE, FALLBACK TO TUTOR ---")
    return "tutor"


def router_after_planner(state: AgentState) -> str:
    """Routes after the planner model generates a response."""
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        print(f"--- PLANNER ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"

    print("--- PLANNER COMPLETED PLAN ---")
    return END


def router_after_variant(state: AgentState) -> str:
    """Routes after the variant model generates a response."""
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        print(f"--- VARIANT ROUTING TO TOOLS: {last_message.tool_calls} ---")
        return "tools"

    print("--- VARIANT COMPLETED ---")
    return END


def router_after_reporter(state: AgentState) -> str:
    """Routes after the reporter model generates a response."""
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
builder.add_node("tutor", tutor_node)
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
        "tutor": "tutor",
        "assessor": "assessor",
        "planner": "planner",
        "variant": "variant",
        "reporter": "reporter",
    },
)

builder.add_conditional_edges(
    "tutor", router_after_tutor, {"tools": "tools", "assessor": "assessor"}
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
        "tutor": "tutor",
        "assessor": "assessor",
        "planner": "planner",
        "variant": "variant",
        "reporter": "reporter",
    },
)

# Compile with a checkpointer for memory persistence
memory = MemorySaver()
treeedu_graph = builder.compile(checkpointer=memory)
