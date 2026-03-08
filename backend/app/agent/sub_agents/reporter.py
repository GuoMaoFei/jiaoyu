"""
Reporter Agent (学情观察员) - Generates structured learning reports for parents.
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.state import AgentState
from app.utils.llm_router import get_heavy_model
from app.agent.tools.reporter_tools import get_chapter_health_report, get_mistake_summary

REPORTER_SYSTEM_PROMPT = """
You are "Reporter Agent" (学情观察员), a caring and insightful learning analytics reporter for the TreeEdu system.

Your job is to generate clear, structured weekly learning reports for parents in Chinese.

WORKFLOW:
1. Call `get_chapter_health_report` to get chapter-level health data.
2. Call `get_mistake_summary` to see recent mistake patterns.
3. Synthesize the data into a warm, professional report in Chinese Markdown format.

REPORT STRUCTURE:
1. 📊 总评：一句话概括本周学习状况
2. 🌳 知识树健康度：按章节列出红黄绿灯
3. ❗ 薄弱环节分析：指出需要重点关注的知识点
4. ✨ 闪光点：表扬做得好的地方
5. 💡 建议：给家长 2-3 条具体的辅导建议

TONE:
- 语气温暖但客观，避免过度批评或过度表扬
- 用数据说话，但表达要通俗易懂
- 站在家长角度，给出可操作的建议

Context:
Student ID: {student_id}
Material ID: {material_id}
"""


def reporter_node(state: AgentState):
    """
    The node representing the Reporter Agent logic.
    Queries learning data and generates a structured parent report.
    """
    print("--- ENTER REPORTER NODE ---")
    
    model = get_heavy_model(temperature=0.3)
    tools = [get_chapter_health_report, get_mistake_summary]
    model_with_tools = model.bind_tools(tools)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORTER_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    chain = prompt | model_with_tools
    
    response = chain.invoke({
        "messages": state["messages"],
        "student_id": state["student_id"],
        "material_id": state["material_id"] or "all",
    })
    
    return {"messages": [response]}
