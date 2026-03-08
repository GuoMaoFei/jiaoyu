import os
import sys
import base64
import asyncio

sys.path.insert(0, os.path.dirname(__file__))
from app.utils.llm_router import get_vision_model
from langchain_core.messages import HumanMessage, SystemMessage

async def test_vlm():
    print("Testing Aliyun Vision API...")
    llm = get_vision_model()
    
    # Just create a small dummy 1x1 png in base64
    dummy_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    
    messages = [
        SystemMessage(content="Describe the image."),
        HumanMessage(content=[
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{dummy_base64}"}}
        ])
    ]
    
    try:
        res = await llm.ainvoke(messages)
        print("Success!")
        print(res.content)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vlm())
