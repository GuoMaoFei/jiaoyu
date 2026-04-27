from app.agent.state import AgentState
from app.agent.sub_agents.tutor_base import invoke_step_agent, STEP_TEACHING_DIRECTIVES
from app.utils.llm_router import get_fast_model

DIRECTIVE = STEP_TEACHING_DIRECTIVES["IMPORT"]


async def import_agent(state: AgentState):
    print("--- ENTER IMPORT AGENT ---")
    model = get_fast_model(temperature=0.7)
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    print(f"--- [MODEL] IMPORT: {model_name}, temp=0.7 ---")
    return await invoke_step_agent(model, DIRECTIVE, state)
