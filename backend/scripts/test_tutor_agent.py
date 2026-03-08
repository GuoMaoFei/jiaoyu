import asyncio
import os
import sys
import uuid
import logging
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import treeedu_graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tutor_agent():
    load_dotenv()
    
    if not any([os.getenv("ALIYUN_API_KEY"), os.getenv("GEMINI_API_KEY"), os.getenv("OPENAI_API_KEY")]):
        logger.error("Please set ALIYUN_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY in your .env file to run the AI Tutor.")
        return

    # 1. Prepare an input state
    session_id = str(uuid.uuid4())
    student_id = "student_001"
    
    # We ask a question that triggers the example flow
    initial_message = HumanMessage(content="我已经准备好了，请开始！")
    
    state = {
        "session_id": session_id,
        "student_id": student_id,
        "material_id": "1b3090e4-ad38-4bc4-9476-875a58a9ed24", 
        "lesson_step": "EXAMPLE", 
        "tool_outputs": {"example_content": "这是一道经典的强化学习例题：给定一个 3x3 的迷宫，入口在左上角，出口在右下角，你会怎么设计奖励函数？"},
        "messages": [initial_message]
    }
    
    config = {"configurable": {"thread_id": session_id}}
    
    logger.info("--- STARTING AGENT GRAPH RUN (EXAMPLE STEP) ---")
    
    # 2. Run the graph
    # We use astream to see the output of each node
    async for event in treeedu_graph.astream(state, config=config):
        for node, values in event.items():
            print(f"\n--- Output from node '{node}' ---")
            
            # Print messages if any were added
            if "messages" in values:
                last_msg = values["messages"][-1]
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    print(f"Agent Action (Tool Call): {last_msg.tool_calls}")
                else:
                    print(f"Agent Response: {last_msg.content}")
            
            # Print current intent if routed by supervisor
            if "current_intent" in values:
                print(f"Supervisor routed to: {values['current_intent']}")
            if "tutor_context" in values:
                print(f"Tutor Context injected: lesson_step={values['tutor_context'].get('lesson_step')}")

    logger.info("--- AGENT GRAPH RUN COMPLETE ---")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_tutor_agent())
