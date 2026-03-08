import os
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.config import get_settings

async def test_qwen_vl():
    settings = get_settings()
    llm = ChatOpenAI(
        api_key=settings.ALIYUN_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-vl-max",
        temperature=0.0
    )
    
    dummy_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    msg = HumanMessage(content=[
        {"type": "text", "text": "What is this?"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{dummy_base64}"}}
    ])
    
    try:
        res = await llm.ainvoke([msg])
        print("Success:", res.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_qwen_vl())
