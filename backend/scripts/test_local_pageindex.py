import os
import sys
import asyncio
import json

# Add backend directory to sys.path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.utils.llm_router import get_heavy_model
from langchain_core.messages import SystemMessage, HumanMessage

settings = get_settings()
# Configure env for local pageindex (which expects ChatGPT environment variables but we map to Aliyun)
os.environ["CHATGPT_API_KEY"] = settings.ALIYUN_API_KEY
os.environ["CHATGPT_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Local PageIndex SDK MUST be imported after setting os.environ
from pageindex.utils import ConfigLoader
from pageindex.page_index import page_index_main

async def main():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                            "jiaocai", "（根据2022年版课程标准修订）义务教育教科书·语文一年级上册.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    print(f"=== 1. 开始调用本地 PageIndex 处理教材 PDF ===")
    config_loader = ConfigLoader()
    user_opt = {
        'model': 'qwen-max', 
        'if_add_node_summary': 'yes',
        'if_add_doc_description': 'no',
        'if_add_node_text': 'yes', 
        'if_add_node_id': 'yes',
        # to speed up testing, limit pages if the algorithm allows it
        'toc_check_page_num': 15 
    }
    opt = config_loader.load(user_opt)
    
    # Run the internal algorithm to build the tree
    # Note: For large textbooks this will take a few minutes as it calls LLM for each page
    print("正在抽树... (此步骤将截取目录并递归解析文本，请耐心等待)")
    tree_result = await asyncio.get_event_loop().run_in_executor(
        None, 
        lambda: page_index_main(pdf_path, opt)
    )
    
    structure = tree_result.get('structure', [])
    print(f"\n✅ 建树完成！提取到 {len(structure)} 个根节点。")
    
    # === 2. 模拟数据库落盘与检索（"怎么问" 的核心逻辑）===
    print("\n=== 2. 开始扁平化节点并进行全文/语义检索 ===")
    flat_nodes = []
    
    def _flatten(nodes):
        if isinstance(nodes, list):
            for n in nodes:
                title = n.get('title', '')
                summary = n.get('summary', '')
                text = n.get('text', '')
                flat_nodes.append({
                    "title": title,
                    "content": f"【摘要】{summary}\n【正文】{text}"
                })
                _flatten(n.get('children', []))
                _flatten(n.get('nodes', [])) # depending on pageindex output format

    _flatten(structure)
    print(f"总计提取到 {len(flat_nodes)} 个知识切片。")
    
    # User's Question
    query = "秋天到了，天气凉了，树叶怎么样了？请带我读一下这部分。"
    print(f"\n[学生端提问]: {query}")
    
    # Step 2a: Retrieve context
    search_terms = ["秋", "天气", "凉", "树叶"] # Mocking a simple keyword search similar to pageindex_tools.py
    matched_nodes = []
    for node in flat_nodes:
        if any(term in node["content"] or term in node["title"] for term in search_terms):
            matched_nodes.append(node)
            
    if not matched_nodes:
        print("❌ 未能在教材中检索到相关知识...")
        return
        
    print(f"🔍 检索到 {len(matched_nodes)} 个相关知识块。选取前 2 个进入大模型思维...")
    context_str = ""
    for i, node in enumerate(matched_nodes[:2], 1):
        context_str += f"\n--- 知识卡片 {i} ---\n标题: {node['title']}\n内容: {node['content']}\n"
    
    # === 3. 大模型基于私有知识树生成作答 ===
    print("\n=== 3. 召唤伴读神仙 (Tutor Agent) 基于检索内容生成回答 ===")
    system_prompt = f"""你是一个温柔的一年级语文老师。
请严格基于以下教材检索到的知识卡片来回答学生的问题。如果卡片里没有答案，请告诉学生课本里好像还没讲到这里。

检索到的官方教材内容:
{context_str}
"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]
    
    llm = get_heavy_model(temperature=0.2)
    response = await llm.ainvoke(messages)
    
    print("\n[AI 老师的回答]:")
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
