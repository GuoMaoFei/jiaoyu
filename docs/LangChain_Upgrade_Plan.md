# LangChain 生态全面升级文档

> 目标：将 LangChain 全家桶从 0.x 升级到 1.x，利用 `init_chat_model()` 统一接口重构 llm_router，并将 5 个教学阶段拆分为独立 agent。

---

## 1. 版本升级矩阵

| 包 | 当前版本 | 目标版本 | 变化级别 |
|---|---------|---------|----------|
| `langchain-core` | 0.3.30 | **1.3.0** | 主版本 |
| `langgraph` | 0.2.64 | **1.1.8** | 主版本（无 0.3/0.4，直接到 1.x） |
| `langchain-openai` | 0.2.14 | **1.1.14** | 主版本 |
| `langchain-anthropic` | 0.3.2 | **1.4.1** | 主版本 |
| `langchain-google-genai` | 未固定 | **新增固定** | 新增 |
| `langchain-community` | 0.3.14 | 按需保留 | — |

> `langgraph` 没有 0.4.x，从 0.2.x 直接跳到 1.x。

---

## 2. 新版本关键特性

### 2.1 `init_chat_model()` — 统一模型接口（最重要）

用一个函数替代所有 provider-specific 的 import 和构造：

```python
from langchain.chat_models import init_chat_model

# OpenAI
model = init_chat_model("gpt-4o-mini", model_provider="openai", temperature=0.7)

# DeepSeek（自定义 base_url）
model = init_chat_model("deepseek-chat", model_provider="openai",
                        api_key="...", base_url="https://api.deepseek.com/v1")

# Aliyun（自定义 base_url）
model = init_chat_model("qwen-plus", model_provider="openai",
                        api_key="...", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

# MiniMax（Anthropic 兼容接口）
model = init_chat_model("MiniMax-M2.5", model_provider="anthropic",
                        api_key="...", base_url="https://api.minimaxi.com/anthropic")

# Gemini
model = init_chat_model("gemini-2.0-flash", model_provider="google-genai")
```

**效果**：`llm_router.py` 从 120+ 行 if/elif 缩减到 ~50 行。

### 2.2 StateGraph API — 向后兼容

`StateGraph`、`add_node`、`add_edge`、`add_conditional_edges`、`END`、`START`、`MemorySaver`、`ToolNode` — 全部向后兼容，无需改动。

### 2.3 标准化内容块

消息新增 `content_blocks` 属性，提供跨 provider 的规范化内容（text、reasoning、tool_call、image 等）。可简化 `strip_thinking_blocks()` 手动解析。

### 2.4 其他不变项

| API | 状态 |
|-----|------|
| `@tool` 装饰器 + `args_schema` | 不变 |
| `ChatPromptTemplate` / `MessagesPlaceholder` | 不变 |
| LCEL chain (`prompt \| model`) | 不变 |
| `astream_events version="v2"` | 不变（当前推荐 API） |
| `HumanMessage` / `AIMessage` / `SystemMessage` / `ToolMessage` | 不变 |

### 2.5 Python 要求

新版本要求 **Python 3.10+**，确认项目满足。

---

## 3. 影响范围

### 3.1 核心重构（变化大）

| 文件 | 改动说明 |
|------|---------|
| `requirements.txt` | 更新版本号，新增 `langchain-google-genai` |
| `app/utils/llm_router.py` | **完全重写**：用 `init_chat_model()` 替代 if/elif 链 |
| `app/agent/graph.py` | **大幅重构**：tutor 拆为 5 个 node，更新路由 |
| `app/agent/sub_agents/tutor.py` | **拆分为 6 个文件**（见 §4.3） |

### 3.2 适配调整（变化小，验证 import 路径）

| 文件 | 用到的 API |
|------|-----------|
| `app/agent/state.py` | `BaseMessage`, `AIMessage`, `operator.add` |
| `app/agent/sub_agents/assessor.py` | `ChatPromptTemplate`, `MessagesPlaceholder`, `AIMessage` |
| `app/agent/sub_agents/planner.py` | `ChatPromptTemplate`, `MessagesPlaceholder`, `AIMessage`, `ToolMessage` |
| `app/agent/sub_agents/reporter.py` | `ChatPromptTemplate`, `MessagesPlaceholder` |
| `app/agent/sub_agents/variant.py` | `ChatPromptTemplate`, `MessagesPlaceholder` |
| `app/agent/tools/*.py`（5 files） | `@tool` |
| `app/routers/chat.py` | `HumanMessage`, `astream`, `astream_events` |
| `app/routers/lesson.py` | `HumanMessage`（lazy import）, `astream` |
| `app/routers/report.py` | `HumanMessage`（lazy import）, `astream` |
| `app/routers/exam.py` | `SystemMessage`, `HumanMessage`, `model.ainvoke` |
| `app/utils/vlm_catalog.py` | `SystemMessage`, `HumanMessage`, `model.ainvoke` |
| `app/utils/vision_ocr.py` | `HumanMessage`, `model.ainvoke` |
| `app/services/quiz_generator.py` | `SystemMessage`, `HumanMessage`, `model.ainvoke` |
| `app/main.py` | `set_debug` from `langchain_core.globals` |

### 3.3 测试脚本（7 files）

| 文件 | 关注点 |
|------|-------|
| `scripts/test_tutor_mock.py` | `FakeMessagesListChatModel` 可能改名/移位 |
| `scripts/test_assessor_mock.py` | 同上 |
| 其他 5 个脚本 | 验证 import 路径 |

---

## 4. 详细实施方案

### 4.1 Phase 1：依赖升级

**`requirements.txt` 更新为：**

```
langchain-core==1.3.0
langgraph==1.1.8
langchain-openai==1.1.14
langchain-anthropic==1.4.1
langchain-google-genai>=2.0.0
```

移除 `langchain-community`（如果没有直接使用）。

**操作步骤：**

```bash
cd backend
pip install -r requirements.txt
python -c "from langchain.chat_models import init_chat_model; print('OK')"
```

### 4.2 Phase 2：重构 `llm_router.py`

**当前**：135 行，4 个 tier 函数各含 6 个 provider 的 if/elif，大量重复。

**目标**：~50 行，用 `init_chat_model()` + 配置映射表。

```python
from functools import lru_cache
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import get_settings

settings = get_settings()

_PROVIDER_MAP = {
    # (tier, provider_setting) -> {model, provider, base_url, api_key_attr}
    ("fast", "openai"):     {"model": "gpt-4o-mini", "provider": "openai", "key": "OPENAI_API_KEY"},
    ("fast", "deepseek"):   {"model": "deepseek-chat", "provider": "openai", "key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1"},
    ("fast", "gemini"):     {"model": "gemini-2.0-flash", "provider": "google-genai", "key": "GEMINI_API_KEY"},
    ("fast", "aliyun"):     {"model": "qwen-plus", "provider": "openai", "key": "ALIYUN_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    ("fast", "openrouter"): {"model": "qwen/qwen3-4b:free", "provider": "openai", "key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1"},
    ("fast", "minimax"):    {"model": "MiniMax-M2.5", "provider": "anthropic", "key": "MINIMAX_API_KEY", "base_url": "https://api.minimaxi.com/anthropic"},

    ("medium", "openai"):     {"model": "gpt-4o-mini", "provider": "openai", "key": "OPENAI_API_KEY"},
    ("medium", "deepseek"):   {"model": "deepseek-chat", "provider": "openai", "key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1"},
    ("medium", "gemini"):     {"model": "gemini-2.0-flash", "provider": "google-genai", "key": "GEMINI_API_KEY"},
    ("medium", "aliyun"):     {"model": "qwen/qwen3-4b", "provider": "openai", "key": "ALIYUN_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    ("medium", "openrouter"): {"model": "google/gemma-3-27b-it:free", "provider": "openai", "key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1"},
    ("medium", "minimax"):    {"model": "MiniMax-M2.5", "provider": "anthropic", "key": "MINIMAX_API_KEY", "base_url": "https://api.minimaxi.com/anthropic"},

    ("heavy", "openai"):     {"model": "gpt-4o", "provider": "openai", "key": "OPENAI_API_KEY"},
    ("heavy", "gemini"):     {"model": "gemini-2.5-pro", "provider": "google-genai", "key": "GEMINI_API_KEY"},
    ("heavy", "aliyun"):     {"model": "qwen-max-latest", "provider": "openai", "key": "ALIYUN_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    ("heavy", "openrouter"): {"model": "stepfun/step-3.5-flash:free", "provider": "openai", "key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1"},
    ("heavy", "minimax"):    {"model": "MiniMax-M2.7", "provider": "anthropic", "key": "MINIMAX_API_KEY", "base_url": "https://api.minimaxi.com/anthropic"},

    ("vision", "aliyun"):     {"model": "qwen-vl-max-latest", "provider": "openai", "key": "ALIYUN_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    ("vision", "openrouter"): {"model": "nvidia/nemotron-nano-12b-v2-vl:free", "provider": "openai", "key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1"},
    ("vision", "minimax"):    {"model": "MiniMax-M2.7", "provider": "openai", "key": "MINIMAX_API_KEY", "base_url": "https://api.minimaxi.com/anthropic/v1"},
}

_TIMEOUT = {"fast": 60.0, "medium": 120.0, "heavy": 180.0, "vision": 120.0}

_TIER_SETTING = {
    "fast": "LLM_FAST_MODEL",
    "medium": "LLM_MEDIUM_MODEL",
    "heavy": "LLM_HEAVY_MODEL",
    "vision": "LLM_VISION_MODEL",
}


def _build_model(tier: str, temperature: float) -> BaseChatModel:
    provider = getattr(settings, _TIER_SETTING[tier]).lower().strip()
    cfg = _PROVIDER_MAP.get((tier, provider))
    if not cfg:
        raise ValueError(f"Unknown config for tier={tier}, provider={provider}")

    kwargs = {
        "model": cfg["model"],
        "model_provider": cfg["provider"],
        "api_key": getattr(settings, cfg["key"]),
        "temperature": temperature,
        "max_retries": 3,
        "timeout": _TIMEOUT[tier],
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]

    return init_chat_model(**kwargs)


@lru_cache(maxsize=16)
def get_fast_model(temperature: float = 0.0) -> BaseChatModel:
    return _build_model("fast", temperature)

@lru_cache(maxsize=16)
def get_medium_model(temperature: float = 0.3) -> BaseChatModel:
    return _build_model("medium", temperature)

@lru_cache(maxsize=16)
def get_heavy_model(temperature: float = 0.2) -> BaseChatModel:
    return _build_model("heavy", temperature)

@lru_cache(maxsize=4)
def get_vision_model(temperature: float = 0.0) -> BaseChatModel:
    return _build_model("vision", temperature)
```

> **注意**：需验证 `init_chat_model` 对 MiniMax 的 Anthropic 兼容接口是否支持自定义 `base_url`。如果不支持，MiniMax 分支需要保留手动构造 `ChatAnthropic`。

### 4.3 Phase 3：拆分 Tutor 为 5 个 Step Agent

#### 目标文件结构

```
app/agent/sub_agents/
├── tutor_base.py       # 公共逻辑：prompt 构建、context 注入、thinking 过滤
├── import_agent.py     # IMPORT 阶段（fast model, temp=0.7）→ END
├── explain_agent.py    # EXPLAIN 阶段（heavy model, temp=0.2）→ assessor
├── example_agent.py    # EXAMPLE 阶段（medium model, temp=0.3）→ assessor
├── practice_agent.py   # PRACTICE 阶段（fast model, temp=0.5）→ assessor
├── summary_agent.py    # SUMMARY 阶段（medium model, temp=0.3）→ END
├── assessor.py         # 不变
├── planner.py          # 不变
├── reporter.py         # 不变
└── variant.py          # 不变
```

#### `tutor_base.py` — 提取公共逻辑

从 `tutor.py` 提取：

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
from app.agent.state import AgentState, strip_thinking_blocks
from app.agent.tools.pageindex_tools import search_knowledge_tree

TUTOR_SYSTEM_PROMPT_BASE = """
You are "Tutor Agent" (伴读神仙), an expert Socratic teacher...
{step_directive}

Context from Supervisor Memory:
Student ID: {student_id}
Material ID: {material_id}
Current Node ID: {node_id}
Current Node Title: {node_title}
Current Node Content (Curriculum snippet):
{node_content}

Example Content (If applicable):
{example_content}

Current Health Score: {health_score} / 100
Historical Mistakes (Expert Preference): {historical_mistakes}
"""


def build_tutor_prompt(step_directive: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", TUTOR_SYSTEM_PROMPT_BASE),
        MessagesPlaceholder(variable_name="messages"),
    ])


def extract_invoke_args(state: AgentState) -> dict:
    ctx = state.get("tutor_context", {})
    return {
        "step_directive": "",  # 由各 agent 自己填
        "messages": state["messages"],
        "student_id": state["student_id"],
        "material_id": state["material_id"] or "Unknown",
        "node_id": state.get("node_id") or "Unknown",
        "node_title": ctx.get("node_title", "General Topic"),
        "node_content": ctx.get("node_content", "No content."),
        "example_content": ctx.get("example_content", "No example provided."),
        "health_score": ctx.get("current_health_score", 50),
        "historical_mistakes": ctx.get("historical_mistakes", "无记录"),
    }


async def invoke_step_agent(model, prompt, invoke_args) -> dict:
    chain = prompt | model
    response = await chain.ainvoke(invoke_args)
    response = strip_thinking_blocks(response)
    return {"messages": [response]}
```

#### 各 Step Agent 示例

**`import_agent.py`：**

```python
from app.agent.sub_agents.tutor_base import build_tutor_prompt, extract_invoke_args, invoke_step_agent
from app.utils.llm_router import get_fast_model
from app.agent.tools.pageindex_tools import search_knowledge_tree
from app.agent.state import AgentState

DIRECTIVE = """【当前教学阶段：基础预热 🔥】..."""  # 从 tutor.py STEP_TEACHING_DIRECTIVES["IMPORT"] 迁移

async def import_agent(state: AgentState):
    model = get_fast_model(temperature=0.7).bind_tools([search_knowledge_tree])
    prompt = build_tutor_prompt(DIRECTIVE)
    args = extract_invoke_args(state)
    args["step_directive"] = DIRECTIVE
    return await invoke_step_agent(model, prompt, args)
```

**`explain_agent.py`、`example_agent.py`、`practice_agent.py`、`summary_agent.py`** 结构相同，仅 model/directive 不同：

| Agent | Model | Temperature | 之后路由 |
|-------|-------|-------------|---------|
| `import_agent` | `get_fast_model` | 0.7 | END |
| `explain_agent` | `get_heavy_model` | 0.2 | assessor |
| `example_agent` | `get_medium_model` | 0.3 | assessor |
| `practice_agent` | `get_fast_model` | 0.5 | assessor |
| `summary_agent` | `get_medium_model` | 0.3 | END |

### 4.4 Phase 4：重构 `graph.py`

#### Supervisor 路由更新

```python
def router_after_supervisor(state: AgentState) -> str:
    intent = state.get("current_intent")
    if intent in ("planner", "variant", "reporter", "assessor"):
        return intent

    lesson_step = state.get("lesson_step") or "EXPLAIN"
    step_map = {
        "IMPORT": "import",
        "EXPLAIN": "explain",
        "EXAMPLE": "example",
        "PRACTICE": "practice",
        "SUMMARY": "summary",
        "COMPLETED": END,
    }
    return step_map.get(lesson_step, "explain")
```

#### Step Agent 路由（统一的 `router_after_step`）

```python
def router_after_step(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END  # 默认 END，由 graph 配置决定是否路由到 assessor
```

#### Graph 构建

```python
builder.add_node("import", import_agent)
builder.add_node("explain", explain_agent)
builder.add_node("example", example_agent)
builder.add_node("practice", practice_agent)
builder.add_node("summary", summary_agent)

builder.add_conditional_edges("supervisor", router_after_supervisor, {
    "import": "import", "explain": "explain", "example": "example",
    "practice": "practice", "summary": "summary",
    "planner": "planner", "variant": "variant", "reporter": "reporter",
    END: END,
})

# IMPORT / SUMMARY → END（不做评估）
builder.add_conditional_edges("import", router_after_step, {"tools": "tools", END: END})
builder.add_conditional_edges("summary", router_after_step, {"tools": "tools", END: END})

# EXPLAIN / EXAMPLE / PRACTICE → assessor（评估学生回答）
builder.add_conditional_edges("explain", router_after_step, {"tools": "tools", "assessor": "assessor", END: END})
builder.add_conditional_edges("example", router_after_step, {"tools": "tools", "assessor": "assessor", END: END})
builder.add_conditional_edges("practice", router_after_step, {"tools": "tools", "assessor": "assessor", END: END})
```

### 4.5 Phase 5：SSE 流式端点适配

`chat.py` 中的 node 名称过滤需要更新：

```python
# 之前
if node_name in ("tutor",):

# 之后
if node_name in ("import", "explain", "example", "practice", "summary"):
```

同样，`/send` 端点中的内容收集也要更新：

```python
# 之前
if node_name != "assessor":

# 之后（不变，仍排除 assessor）
if node_name != "assessor":
```

---

## 5. 实施顺序

```
Phase 1: 依赖升级
  └── requirements.txt → pip install → 验证 import

Phase 2: 重构 llm_router.py
  └── init_chat_model() 替代 if/elif → 单元验证

Phase 3: 拆分 Tutor
  └── tutor_base.py + 5 个 step agent → graph.py 路由更新

Phase 4: 端点适配
  └── chat.py / lesson.py / report.py 的 node 名称过滤

Phase 5: 集成测试
  └── 完整 pipeline → SSE 流式 → 各阶段独立验证
```

---

## 6. 验证清单

- [ ] `pip install -r requirements.txt` 成功
- [ ] `uvicorn app.main:app --reload` 启动无报错
- [ ] `init_chat_model` 对所有 6 个 provider 正常工作
- [ ] IMPORT 阶段：supervisor → import_agent → END（不触发 assessor）
- [ ] EXPLAIN 阶段：supervisor → explain_agent → assessor → END
- [ ] `search_knowledge_tree` 工具正常调用（26ms，无 LLM 路由）
- [ ] SSE 流式推送正常，token 事件可见
- [ ] Assessor 仅在 EXPLAIN/EXAMPLE/PRACTICE 阶段触发
- [ ] 客户端断开 SSE 后，后台 agent 任务被取消

---

## 7. 风险与回退

| 风险 | 影响 | 应对 |
|------|------|------|
| `init_chat_model` 不支持 MiniMax 自定义 `anthropic_api_url` | MiniMax provider 无法使用 | 保留手动 `ChatAnthropic` 构造 |
| `FakeMessagesListChatModel` 在新版改名或移除 | 测试脚本报错 | 查找替代或 mock |
| `langgraph 1.x` StateGraph 细微行为差异 | graph 路由异常 | 逐 node 测试 |
| OpenRouter `extra_headers` 不被 `init_chat_model` 支持 | OpenRouter 请求缺少 header | 保留手动 `ChatOpenAI` 构造 |

**回退方案**：在 `feature/langchain-upgrade` 分支开发，出问题时回退到 `main`。
