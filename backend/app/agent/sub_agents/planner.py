"""
Planner Agent (规划统筹师) - Generates study plans by analyzing the knowledge tree.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage

from app.agent.state import AgentState
from app.utils.llm_router import get_heavy_model
from app.agent.tools.planner_tools import create_study_plan, get_material_node_list

PLANNER_SYSTEM_PROMPT = """
You are "Planner Agent" (规划统筹师), a meticulous study plan designer for TreeEdu system.

Your job is to help students create optimal study plans based on their textbook's knowledge tree structure.

STRICT WORKFLOW - Follow these steps EXACTLY in order:
1. Call `get_material_node_list(student_id, material_id)` ONCE to get uncompleted lesson nodes
2. The nodes are already sorted by chapter order (按章节顺序) - use this exact order!
3. After receiving the node list, IMMEDIATELY call `create_study_plan(student_id, material_id, node_ids, start_date, sessions_per_week)`
4. After create_study_plan succeeds, respond with a brief Chinese summary

IMPORTANT:
- DO NOT re-order the nodes - they are already in the correct learning order
- The first node in the list should be the first lesson the student should learn
- The list only contains Level 2 nodes (actual lessons), not chapter headers
- Already completed nodes are already filtered out

SCHEDULING RULES:
- Default to 3 sessions per week unless the student specifies otherwise
- Schedule lessons on weekdays only (skip weekends)

Context:
Student ID: {student_id}
Material ID: {material_id}
Student's Current Health Score: {avg_health_score}
Student's Weakness Summary: {weakness_summary}
"""


async def planner_node(state: AgentState):
    """
    The node representing the Planner Agent logic.
    Reads the knowledge tree and generates a structured study plan.
    """
    print("--- ENTER PLANNER NODE ---")

    # Check if we have incomplete tool calls in the message history
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        # If last message has tool_calls without corresponding ToolMessage, skip LLM call
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            has_tool_response = any(
                isinstance(m, ToolMessage)
                and any(
                    tc.get("id") == last_msg.tool_calls[0].get("id")
                    for tc in last_msg.tool_calls
                )
                for m in messages
            )
            if not has_tool_response:
                print(
                    "--- PLANNER: DETECTED INCOMPLETE TOOL CALLS, SKIPPING LLM INVOKE ---"
                )
                return {}

    # 1. Build the LLM with the planning tools bound
    model = get_heavy_model(temperature=0.2)
    tools = [create_study_plan, get_material_node_list]
    model_with_tools = model.bind_tools(tools)

    # 2. Compile the Prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    # 3. Read context
    tutor_ctx = state.get("tutor_context", {})

    chain = prompt | model_with_tools

    try:
        response = await chain.ainvoke(
            {
                "messages": state["messages"],
                "student_id": state["student_id"],
                "material_id": state["material_id"] or "Unknown",
                "avg_health_score": tutor_ctx.get("current_health_score", 50),
                "weakness_summary": tutor_ctx.get("historical_mistakes", "暂无"),
            }
        )
        return {"messages": [response]}
    except Exception as e:
        print(f"--- PLANNER ERROR: {e} ---")
        return {"messages": []}
