import asyncio
import os
import sys
import uuid
import logging
from langchain_core.messages import HumanMessage, AIMessage, ToolCall

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import treeedu_graph

# We need to mock the LLM router to return a fake model that yields a tool call then a final message
from app.utils import llm_router
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

# MOCK SETUP
mock_tool_call = ToolCall(
    name="search_knowledge_tree",
    args={"query": "DeepSeek-R1-Zero 训练原理", "material_id": "1b3090e4-ad38-4bc4-9476-875a58a9ed24", "expert_preference": "该生在几何证明中经常忽略辅助线的构建。"},
    id="call_mock123"
)

mock_responses = [
    AIMessage(content="", tool_calls=[mock_tool_call]),
    AIMessage(content="我注意到你对 DeepSeek-R1-Zero 的训练方式很好奇。根据课程资料，这篇论文提到了它是在没有经过『监督微调 (SFT)』的情况下直接使用强化学习的。考虑到你平时容易忽略隐藏的辅助步骤，你认为在这没有 SFT 的情况下，它是如何凭空学会把推理过程变长的呢？不妨回顾一下第二章的内容。")
]

# Override the heavy model router inside the tutor module to use the fake model
import app.agent.sub_agents.tutor

class MyFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

fake_model = MyFakeModel(responses=mock_responses)
app.agent.sub_agents.tutor.get_heavy_model = lambda temperature=0: fake_model

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tutor_agent_mock():
    session_id = str(uuid.uuid4())
    student_id = "student_001"
    
    initial_message = HumanMessage(content="我不太懂什么是 DeepSeek-R1-Zero，你能直接告诉我它是怎么训练出来的吗？")
    
    state = {
        "session_id": session_id,
        "student_id": student_id,
        "material_id": "1b3090e4-ad38-4bc4-9476-875a58a9ed24", 
        "messages": [initial_message]
    }
    
    config = {"configurable": {"thread_id": session_id}}
    
    logger.info("--- STARTING MOCK AGENT GRAPH RUN ---")
    logger.info(f"Student asks: {initial_message.content}")
    
    async for event in treeedu_graph.astream(state, config=config):
        for node, values in event.items():
            print(f"\n--- Output from node '{node}' ---")
            
            if "messages" in values:
                last_msg = values["messages"][-1]
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    print(f"Agent Action (Thinking & Tool Call): {last_msg.tool_calls}")
                else:
                    last_msg_content = getattr(last_msg, 'content', str(last_msg))
                    # For ToolMessages, show what the tool returned
                    if node == "tools":
                       print(f"Tool Result -> {last_msg_content[:200]}...")
                    else:
                        print(f"Agent Response: {last_msg_content}")
            
            if "current_intent" in values:
                print(f"Supervisor routed to: {values['current_intent']}")
                print(f"Tutor Context injected: {values.get('tutor_context')}")

    logger.info("--- MOCK AGENT GRAPH RUN COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_tutor_agent_mock())
