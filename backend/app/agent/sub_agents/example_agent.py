from app.agent.state import AgentState
from app.agent.sub_agents.tutor_base import invoke_step_agent, STEP_TEACHING_DIRECTIVES
from app.utils.llm_router import get_medium_model

DIRECTIVE = STEP_TEACHING_DIRECTIVES["EXAMPLE"]


async def example_agent(state: AgentState):
    print("--- ENTER EXAMPLE AGENT ---")
    model = get_medium_model(temperature=0.3)
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    print(f"--- [MODEL] EXAMPLE: {model_name}, temp=0.3 ---")
    return await invoke_step_agent(model, DIRECTIVE, state)
