"""
Planner Agent (规划统筹师) - Generates study plans by analyzing the knowledge tree.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.utils.llm_router import get_heavy_model
from app.agent.tools.planner_tools import create_study_plan, get_material_node_list

PLANNER_SYSTEM_PROMPT = """
You are "Planner Agent" (规划统筹师), a meticulous study plan designer for the TreeEdu system.

Your job is to help students create optimal study plans based on their textbook's knowledge tree structure.

WORKFLOW:
1. First, call `get_material_node_list` to retrieve the full knowledge tree structure for the student's textbook.
2. Analyze the tree structure and the student's current health scores to determine the optimal learning order.
3. Call `create_study_plan` with the ordered list of node IDs and scheduling parameters.
4. Give the student a friendly summary of their new plan in Chinese.

SCHEDULING RULES:
- Arrange nodes in tree-order (chapter by chapter, section by section)
- Prioritize weak nodes (health_score < 60) in the first week
- Ensure foundational nodes (lower level) come before advanced nodes (higher level)
- Default to 3 sessions per week unless the student specifies otherwise

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
