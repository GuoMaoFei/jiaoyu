"""
Variant Agent (变式出卷机) - Generates variant questions based on knowledge tree nodes.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.state import AgentState
from app.utils.llm_router import get_heavy_model
from app.agent.tools.variant_tools import get_node_questions, save_variant_question

VARIANT_SYSTEM_PROMPT = """
You are "Variant Agent" (变式出卷机), an expert question generator for the TreeEdu system.

Your job is to create high-quality variant questions based on existing questions and knowledge node content.

WORKFLOW:
1. First call `get_node_questions` to see existing questions for the target node.
2. Generate a NEW question that tests the SAME knowledge points but with DIFFERENT context/numbers/scenario.
3. Include a detailed step-by-step solution.
4. Call `save_variant_question` to persist the question.
5. Present the question to the student in Chinese, formatted in Markdown.

VARIANT RULES:
- The variant MUST test the exact same knowledge point as the reference questions.
- Change the surface-level details (numbers, names, scenarios) but keep the deep structure.
- Always provide questions and answers in Chinese.
- Use LaTeX notation (wrapped in $...$ or $$...$$) for mathematical expressions.
- Set difficulty 1-5 based on: 1=直接套公式, 2=简单变换, 3=标准难度, 4=综合应用, 5=竞赛难度.

Context:
Student ID: {student_id}
Target Node ID: {node_id}
"""


async def variant_node(state: AgentState):
    """
    The node representing the Variant Agent logic.
    Generates variant questions based on existing questions and knowledge node content.
    """
    print("--- ENTER VARIANT NODE ---")

    model = get_heavy_model(
        temperature=0.7
    )  # Higher temperature for creative variation
    tools = [get_node_questions, save_variant_question]
    model_with_tools = model.bind_tools(tools)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", VARIANT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    # Determine target node
    assessor_ctx = state.get("assessor_context", {})
    node_id = assessor_ctx.get("target_node_id", "unknown")

    chain = prompt | model_with_tools

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "student_id": state["student_id"],
            "node_id": node_id,
        }
    )

    return {"messages": [response]}
