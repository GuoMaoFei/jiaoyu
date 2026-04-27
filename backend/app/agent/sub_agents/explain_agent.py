from app.agent.state import AgentState
from app.agent.sub_agents.tutor_base import invoke_step_agent, STEP_TEACHING_DIRECTIVES
from app.utils.llm_router import get_heavy_model

DIRECTIVE = STEP_TEACHING_DIRECTIVES["EXPLAIN"]


async def explain_agent(state: AgentState):
    print("--- ENTER EXPLAIN AGENT ---")
    model = get_heavy_model(temperature=0.2)
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    print(f"--- [MODEL] EXPLAIN: {model_name}, temp=0.2 ---")
    return await invoke_step_agent(model, DIRECTIVE, state)
