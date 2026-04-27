from app.agent.state import AgentState
from app.agent.sub_agents.tutor_base import invoke_step_agent, STEP_TEACHING_DIRECTIVES
from app.utils.llm_router import get_fast_model

DIRECTIVE = STEP_TEACHING_DIRECTIVES["PRACTICE"]


async def practice_agent(state: AgentState):
    print("--- ENTER PRACTICE AGENT ---")
    model = get_fast_model(temperature=0.5)
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    print(f"--- [MODEL] PRACTICE: {model_name}, temp=0.5 ---")
    return await invoke_step_agent(model, DIRECTIVE, state)
