import asyncio
import os
import sys
import uuid
import logging
from langchain_core.messages import HumanMessage, AIMessage, ToolCall, ToolMessage

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need to mock BEFORE importing graph (which triggers model instantiation)
from app.utils import llm_router
from app.agent.sub_agents import tutor as tutor_module
from app.agent.sub_agents import assessor as assessor_module
from app.services import memory_overlay as memory_overlay_module
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

# === MOCK SETUP ===

# -- Mock the memory overlay to return controlled test data --
async def mock_get_student_memory_overlay(student_id, material_id=None):
    return {
        "avg_health_score": 45,
        "weak_nodes": ["node_deepseek_r1"],
        "historical_mistakes_summary": "该生在几何证明中经常忽略辅助线的构建。",
        "weakest_node_id": "node_deepseek_r1"
    }

memory_overlay_module.get_student_memory_overlay = mock_get_student_memory_overlay

# Patch in graph.py's reference too
import app.agent.graph as graph_module
graph_module.get_student_memory_overlay = mock_get_student_memory_overlay

# -- Tutor Mock: first call triggers search_knowledge_tree, second call gives final answer --
tutor_tool_call = ToolCall(
    name="search_knowledge_tree",
    args={
        "query": "DeepSeek-R1-Zero 训练原理",
        "material_id": "test-material-001",
        "expert_preference": "该生在几何证明中经常忽略辅助线的构建。"
    },
    id="call_tutor_search"
)

tutor_responses = [
    AIMessage(content="", tool_calls=[tutor_tool_call]),
    AIMessage(content="根据课程资料，DeepSeek-R1-Zero 是直接使用强化学习训练的。你觉得没有监督微调的情况下，它是如何学会推理的呢？")
]

# -- Assessor Mock: calls save_assessment tool, then gives final summary --
assessor_tool_call = ToolCall(
    name="save_assessment",
    args={
        "student_id": "student_001",
        "node_id": "node_deepseek_r1",
        "is_correct": 1,
        "score_delta": 0,
        "diagnosis": "学生提问阶段，暂无评估"
    },
    id="call_assessor_save"
)

assessor_responses = [
    AIMessage(content="", tool_calls=[assessor_tool_call]),
    AIMessage(content="评估完成。学生处于提问阶段，暂不扣分。")
]

class FakeModelWithTools(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

# Inject mocks
tutor_fake = FakeModelWithTools(responses=tutor_responses)
assessor_fake = FakeModelWithTools(responses=assessor_responses)

tutor_module.get_heavy_model = lambda temperature=0: tutor_fake
assessor_module.get_heavy_model = lambda temperature=0: assessor_fake

# NOW we can import the graph (it will use our mocked models)
from app.agent.graph import treeedu_graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_assessor_flow():
    """
    Tests the complete flow: 
    Supervisor (real Memory Overlay query) -> Tutor -> (tool: search_knowledge_tree) 
    -> Tutor (final answer) -> Assessor -> (tool: save_assessment) -> Assessor (done) -> END
    """
    session_id = str(uuid.uuid4())
    student_id = "student_001"
    
    initial_message = HumanMessage(
        content="我不太懂什么是 DeepSeek-R1-Zero，你能直接告诉我它是怎么训练出来的吗？"
    )
    
    state = {
        "session_id": session_id,
        "student_id": student_id,
        "material_id": "test-material-001",
        "messages": [initial_message]
    }
    
    config = {"configurable": {"thread_id": session_id}}
    
    logger.info("=" * 60)
    logger.info("STARTING FULL ASSESSOR MOCK TEST (with Memory Overlay)")
    logger.info("Expected flow: supervisor -> tutor -> tools -> tutor -> assessor -> tools -> assessor -> END")
    logger.info("=" * 60)
    logger.info(f"Student asks: {initial_message.content}")
    
    node_sequence = []
    
    async for event in treeedu_graph.astream(state, config=config):
        for node, values in event.items():
            node_sequence.append(node)
            print(f"\n{'=' * 40}")
            print(f"Node: '{node}'")
            print(f"{'=' * 40}")
            
            if "messages" in values:
                last_msg = values["messages"][-1]
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        print(f"  Tool Call: {tc.get('name', tc)} -> args: {tc.get('args', '')}")
                elif isinstance(last_msg, ToolMessage):
                    content_preview = last_msg.content[:200] if last_msg.content else "(empty)"
                    print(f"  Tool Result: {content_preview}")
                else:
                    print(f"  Response: {last_msg.content}")
            
            if "current_intent" in values:
                print(f"  Intent: {values['current_intent']}")
                ctx = values.get('tutor_context', {})
                print(f"  Memory Overlay -> health_score: {ctx.get('current_health_score')}")
                print(f"  Memory Overlay -> mistakes: {ctx.get('historical_mistakes', '')[:80]}")
                print(f"  Assessor target: {values.get('assessor_context', {}).get('target_node_id')}")
    
    # Verify the node execution order
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"Node execution order: {' -> '.join(node_sequence)}")
    
    expected_nodes = ["supervisor", "tutor", "tools", "tutor", "assessor", "tools", "assessor"]
    
    if node_sequence == expected_nodes:
        print("✅ PASS: Node execution order matches expected flow!")
    else:
        print(f"❌ FAIL: Expected {expected_nodes}, got {node_sequence}")
    
    logger.info("MOCK TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(test_assessor_flow())
