# 知识点树系统开发计划

> 状态：待实施 | 创建日期：2026-04-22

## 1. 背景与动机

### 现状问题

当前系统通过 PageIndex 解析 PDF 教材，产出 `KnowledgeNode`（章节/小节级别，3-8页）+ `KnowledgeContent`（原文内容）。存在三个核心问题：

1. **粒度粗**：KnowledgeNode 按"小节"组织（如"1.2 有理数"），而非按"知识点"组织（如"绝对值的定义"、"绝对值的性质"）。Tutor Agent 需要自行从大段文本中拆解概念，不可控
2. **绑定单教材**：`search_knowledge_tree` 只搜单个 `material_id`，无法跨教材检索。学生学了多本教材后，无法关联不同教材中的同一概念
3. **缺少概念级索引**：没有跨教材的概念级索引，跨 PDF 回答学生问题只能把所有 pi_node 扔给 LLM，token 消耗随教材数量线性增长

### 目标

新增**按学科划分的知识点树**（如：数学一棵、物理一棵），在 PageIndex 构建完成后从每个 KnowledgeNode 的内容中提取概念级知识点，通过映射表关联课程节点。

### 预期收益

| 收益 | 说明 |
|------|------|
| 跨教材检索 | 学生问"绝对值"，系统可从七年级上、八年级上等多本教材中定位相关内容 |
| 精细辅导 | Tutor 可围绕具体知识点（"绝对值的几何意义"）教学，而非整节内容 |
| 跨教材薄弱分析 | Memory Overlay 报告"知识点【绝对值的性质】薄弱（涉及教材：七上、八上）" |
| Token 效率 | 搜索知识点树（compact 索引）而非全量 pi_node 池 |

## 2. 整体架构

### 数据关系图

```
Material (教材)
  └── KnowledgeNode (章节/小节)        ← 现有，文档结构树
        └── KnowledgeContent (原文)

KnowledgePoint (知识点树，按学科)      ← 新增，概念结构树
  └── parent/children (自引用)

KnowledgePointMapping (映射表)         ← 新增，多对多
  ├── knowledge_point_id → KnowledgePoint
  └── knowledge_node_id  → KnowledgeNode
```

### 核心流程

```
PDF 上传
  → PageIndex 构建文档树 → KnowledgeNode + KnowledgeContent (现有流程)
  → KnowledgePointExtractor 提取知识点 (新增)
      → LLM 从节点内容提取概念级知识点
      → 三级去重（hash → Jaccard → LLM验证）
      → 创建/复用 KnowledgePoint + Mapping

学生提问
  → supervisor 从 material_id 获取 subject
  → tutor 系统提示词中包含 subject 值
  → tutor 调用 search_knowledge_points(subject, query, student_id)
      → bigram 预过滤 → 树近邻加分 → 取 top 5
      → 通过 Mapping 查多本教材的内容
      → 按 book_activations 过滤学生已激活的教材
  → 返回跨教材格式化内容给 tutor
```

## 3. 数据库设计

### 3.1 `knowledge_points` 表（知识点树，按学科共享）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | String | PK, UUID | 主键 |
| parent_id | String | FK→knowledge_points.id, indexed | 自引用树结构 |
| subject | String | indexed, NOT NULL | 学科："数学"、"物理" |
| title | String | NOT NULL | 知识点名称，如"绝对值的代数定义" |
| summary | Text | | 一句话概括 |
| keywords | Text | | 逗号分隔，用于 bigram 匹配和去重，如"绝对值,absolute value,\|x\|,非负" |
| level | Integer | NOT NULL, default=1 | 树深度：1=领域 2=主题 3=概念 4=子概念 |
| embedding_hash | String | indexed | 标准化标题 SHA256[:32]，确定性去重键 |
| source_count | Integer | NOT NULL, default=0 | 被多少教材引用 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

SQLAlchemy relationships：
- `parent` / `children`：自引用双向
- `mappings` → `KnowledgePointMapping`（back_populates）

### 3.2 `knowledge_point_mappings` 表（多对多映射）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | String | PK, UUID | 主键 |
| knowledge_point_id | String | FK→knowledge_points.id, indexed | |
| knowledge_node_id | String | FK→knowledge_nodes.id, indexed | |
| relevance_score | Integer | nullable | 0-100，该知识点在此节点中的核心程度 |
| context_snippet | Text | nullable | 内容中体现该知识点的片段 |
| created_at | DateTime | | |

唯一约束：`(knowledge_point_id, knowledge_node_id)`

SQLAlchemy relationships：
- `knowledge_point` → `KnowledgePoint`（back_populates="mappings"）
- `knowledge_node` → `KnowledgeNode`（back_populates="kp_mappings"）

### 3.3 现有模型修改

**`KnowledgeNode`**（`app/models/material.py`）：
```python
kp_mappings = relationship(
    "KnowledgePointMapping",
    back_populates="knowledge_node",
    cascade="all, delete-orphan"
)
```

**`StudentMistake`**（`app/models/testing.py`）：
```python
knowledge_point_id = Column(
    String,
    ForeignKey("knowledge_points.id"),
    nullable=True,
    index=True
)
```

## 4. 实施步骤

### 第1步：数据模型与迁移

| 操作 | 文件 | 内容 |
|------|------|------|
| 新建 | `app/models/knowledge_point.py` | KnowledgePoint + KnowledgePointMapping 模型，完整双向 relationship |
| 修改 | `app/models/__init__.py` | 添加 KnowledgePoint, KnowledgePointMapping 导入 |
| 修改 | `app/models/material.py` | KnowledgeNode 添加 kp_mappings relationship |
| 修改 | `app/models/testing.py` | StudentMistake 添加 knowledge_point_id FK |
| 新建 | `alembic/versions/add_knowledge_point_tables.py` | 创建两张表 + student_mistakes 添加列 |

### 第2步：知识点提取服务

**新建** `app/services/knowledge_point_extractor.py`

#### 核心类设计

```python
class KnowledgePointExtractor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_for_material(self, material_id: str):
        """
        主入口：从教材的所有叶节点中提取知识点。
        """
        # 0. 查询 Material 获取 subject
        # 1. 查询所有叶节点 KnowledgeNode（跳过无 KnowledgeContent 的）
        # 2. 并发提取（Semaphore(5) + retry/backoff）
        # 3. 构建父子关系（通过 parent_title）
        # 4. commit

    def _normalize_title(self, title: str) -> str:
        """去标点、空格、章节号前缀"""

    def _compute_hash(self, title: str) -> str:
        """SHA256[:32]"""

    async def _find_existing(self, subject, hash) -> KnowledgePoint | None:
        """Phase 1：精确 hash 匹配"""

    def _find_by_keywords(self, subject, keywords, threshold=0.7) -> KnowledgePoint | None:
        """Phase 2：keywords Jaccard 相似度"""

    async def _verify_duplicate_llm(self, existing, new) -> bool:
        """Phase 3：LLM 验证（仅 Jaccard 0.4~0.7 时触发）"""
```

#### LLM 提取 Prompt

```
你是一个教材知识点提取引擎。
你将收到一节教材内容（markdown格式）。请从中提取出该节涉及的所有知识点。

输出要求：严格返回 JSON 数组，不要 markdown 代码块。
每个元素包含：
- "title": 知识点名称（简洁，如"绝对值的代数定义"）
- "summary": 一句话概括（50字以内）
- "keywords": 逗号分隔的关键词（用于检索匹配，如"绝对值,absolute value,|x|,非负性"）
- "level": 深度层级（1=知识领域, 2=主题, 3=具体概念, 4=子概念细节）
- "parent_title": 该知识点所属的上级主题名称（用于构建层级关系）
- "relevance": 该知识点在本节内容中的核心程度（0-100）

规则：
1. 粒度要细：不要把"有理数"当成一个知识点，应该拆成"有理数的定义"、"有理数的分类"、"有理数的大小比较"等
2. keywords 必须包含该知识点的常见别称和英文术语
3. 只提取本节明确讲解的知识点，不要推测其他章节的内容
4. 通常一节内容包含 3-8 个知识点
5. title 不要带章节号前缀
```

#### 三级去重策略

```
提取 KP 标题 "绝对值的代数定义"
  │
  ▼
Phase 1: 标准化 → SHA256[:32] → DB 查找 subject + hash
  │
  ├─ 命中 → 复用，创建新 Mapping。结束
  │
  └─ 未命中 → Phase 2
        │
        ▼
      计算 keywords Jaccard 相似度
        │
        ├─ > 0.7 且 parent 匹配 → 合并，追加 keywords。结束
        │
        ├─ 0.4 ~ 0.7 → Phase 3
        │     │
        │     ▼
        │   LLM 验证："这两个知识点是否指同一概念？" → YES/NO
        │     │
        │     ├─ YES → 合并。结束
        │     └─ NO → 新建。结束
        │
        └─ < 0.4 → 新建。结束
```

#### 边界处理

| 场景 | 处理方式 |
|------|---------|
| 节点无 KnowledgeContent | 跳过 |
| 重复解析同一教材 | 先查询旧映射 → 按 KP 分组递减 source_count → 删旧映射 → 重新提取 |
| 首个学科教材（知识点池为空） | 全部新建，正常行为 |
| LLM 调用失败 | retry 3次，失败跳过该节点并记录日志 |
| 提取器整体失败 | 独立 try/except 包裹，不影响树构建状态 |

### 第3步：集成到构建流程

**修改** `app/routers/materials.py`

系统有两条构建路径，知识点提取需要同时覆盖：

| 路径 | 触发端点 | 特点 |
|------|---------|------|
| A: 后台任务 `_run_build_tree()` | `POST /{material_id}/upload` | 异步，后台 asyncio task |
| B: 同步调用 `build_knowledge_tree()` | `POST /build-tree` | 同步，阻塞 HTTP 请求 |

共用辅助函数：

```python
async def _extract_knowledge_points(db: AsyncSession, material_id: str):
    """知识点提取（独立 try/except，失败不影响树构建）"""
    try:
        from app.services.knowledge_point_extractor import KnowledgePointExtractor
        extractor = KnowledgePointExtractor(db)
        await extractor.extract_for_material(material_id)
        await db.commit()
    except Exception as e:
        logger.warning(f"Knowledge point extraction failed for {material_id}: {e}")
```

- 路径 A：在 `_run_build_tree` 的 `await db.commit()` 之后（line 92 之后）、`_update_task(COMPLETED)` 之前（line 96 之前）调用
- 路径 B：在 `build_knowledge_tree` 的 `ingest_material` 返回后（line 322 之后、line 323 构造返回值之前）调用

**设计决策**：提取器不在 `tree_builder.py` 的 `ingest_material` 内部调用，因为：
- `ingest_material` 在调用者的 try 块内执行
- 提取器失败会导致状态/HTTP 响应异常，但树实际已构建成功
- 独立 try/except 包裹，失败只记录日志

### 第4步：材料删除时的清理

**修改** `app/routers/materials.py` 的 `delete_material()`

在删除 KnowledgeNode 之前（`await db.delete(material)` 之前），按顺序执行：

1. 查询该 material 所有 KnowledgeNode 的 id
2. 查询这些 node 关联的所有 KnowledgePointMapping
3. 按 `knowledge_point_id` 分组，对每个 KP：`source_count -= 1`
4. （可选）删除 `source_count=0` 且无子节点的孤立知识点
5. 删除 mappings
6. **删除 Question 记录**（`Question.node_id` 引用 knowledge_nodes，但 KnowledgeNode.questions 无 cascade 设置，必须手动删除）

之后 `await db.delete(material)` 触发 ORM 级联，自动删除 KnowledgeNode → KnowledgeContent → KnowledgePointMapping。步骤 5-6 的手动删除是冗余保护，确保 source_count 已正确维护且无 FK 约束冲突。

### 第5步：跨教材搜索工具

**修改** `app/agent/tools/pageindex_tools.py`

#### 新增缓存

```python
_kp_pool_cache: Dict[str, Tuple[float, List[Dict]]] = {}  # key=subject, TTL=3600s
```

#### 新增工具

```python
class SearchKnowledgePointsParams(BaseModel):
    query: str = Field(description="学生的提问或要搜索的主题")
    subject: str = Field(description="学科名称，如'数学'、'物理'")
    student_id: str = Field(description="学生 ID")

@tool(args_schema=SearchKnowledgePointsParams)
async def search_knowledge_points(query: str, subject: str, student_id: str) -> str:
```

#### 搜索流程

```
输入: query="绝对值和平方根的关系", subject="数学", student_id="abc"
  │
  ▼
1. 加载知识点池（subject="数学" 的所有 KP，带缓存）
  │
  ▼
2. bigram 预过滤 top 20（复用 _extract_bigrams，字段：title + keywords）
  │
  ▼
3. 树近邻加分（当前知识点兄弟/父子优先）
  │
  ▼
4. 取 top 5 知识点
  │
  ▼
5. 通过 mapping → KnowledgeNode → KnowledgeContent 取回原文
  │
  ▼
6. 按 book_activations 过滤（只返回学生已激活教材中的内容）
  │
  ▼
7. 返回格式化内容：
   [绝对值的定义 (来源: 七年级上 - 1.2 有理数)]:
   内容...
   [绝对值的性质 (来源: 八年级上 - 实数复习)]:
   内容...
```

#### 缓存失效

- 提取完成后调用 `invalidate_kp_cache(subject)` 清除该学科的缓存
- 删除教材时也需调用 `invalidate_kp_cache(subject)` 清除缓存（在 delete_material 中，删除 mappings 之后调用）

### 第6步：candidate_filter 增强

**修改** `app/agent/tools/candidate_filter.py`

新增两个函数，复用现有 `_extract_bigrams` 逻辑：

```python
def prefilter_knowledge_points(query, kp_pool, top_k=20):
    """bigram 预过滤，字段用 title + keywords"""

def rank_knowledge_points(query, kp_pool, top_k=5):
    """bigram 分数 + 树近邻加分"""
```

### 第7步：Agent 图集成

#### State 扩展

**修改** `app/agent/state.py`

```python
class AgentState(TypedDict):
    # ... 现有字段 ...
    subject: Optional[str]  # 新增

class TutorContext(TypedDict, total=False):
    # ... 现有字段 ...
    subject: Optional[str]  # 新增，与 AgentState.subject 同步
```

#### Supervisor 传递 subject

**修改** `app/agent/graph.py`

- `all_tools` 添加 `search_knowledge_points`
- `supervisor_node` 额外将 subject 存入 `AgentState`（现有逻辑已在 graph.py:79 设置 `tutor_ctx["subject"]`）
- supervisor 需**同时**设置 `AgentState["subject"]` 和 `tutor_ctx["subject"]`，两者保持同步

#### 工具绑定逻辑重写（关键修复）

**修改** `app/agent/sub_agents/tutor_base.py`

当前逻辑（line 252-257）：`knowledge_prefetched=True` 时**不绑定任何工具**。

修改为：

```python
tools = []
if not ctx.get("knowledge_prefetched"):
    tools.append(search_knowledge_tree)    # 当前教材内搜索（仅未预取时）
tools.append(search_knowledge_points)      # 跨教材搜索（始终可用）
if tools:
    model = model.bind_tools(tools)
```

原因：即使当前节点内容已预取，tutor 仍可能需要跨教材补充内容。

#### 系统提示词更新

```
3. If the provided context is insufficient, you may call tools to retrieve more information:
   - `search_knowledge_tree`: searches within the current textbook only
     (pass student_id, material_id, current_node_id exactly as provided)
   - `search_knowledge_points`: searches across ALL textbooks of the same subject
     (pass subject="{subject}", student_id, and your query).
     Use this when the student's question involves concepts from other chapters or textbooks.
```

#### subject 传递链

```
ChatMessageRequest.material_id (必填)
  → chat.py 构建 agent_input
  → supervisor 从 material_id 查 Material.subject
  → 存入 AgentState.subject + tutor_ctx["subject"]
  → tutor_base.py 从 tutor_ctx 读取填入系统提示词 {subject}
  → LLM 从提示词读取 subject 值传入 tool call
```

**不需要**在 ChatMessageRequest 中额外添加 subject 字段。

#### Chat 路由

**修改** `app/routers/chat.py`

`agent_input` 添加 `"subject": None`（初始值，由 supervisor 填充）

### 第8步：~~ChatMessageRequest 扩展~~

**已取消**。material_id 是必填字段，subject 由 supervisor 自动派生，前端无需改动。

### 第9步：REST API 端点

**修改** `app/schemas/materials.py`

```python
class KnowledgePointBrief(BaseModel):
    id: str
    title: str
    level: int

class KnowledgePointResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str]
    keywords: Optional[str]
    level: int
    source_count: int

class KnowledgePointTreeResponse(BaseModel):
    """递归树结构"""
    id: str
    title: str
    summary: Optional[str]
    level: int
    children: Optional[List["KnowledgePointTreeResponse"]]
```

KnowledgeNodeResponse 添加 `knowledge_points: Optional[List[KnowledgePointBrief]]`

**修改** `app/routers/materials.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/materials/{material_id}/knowledge-points` | GET | 返回该教材关联的知识点列表 |
| `/api/knowledge-points?subject=数学` | GET | 返回某学科的知识点树 |
| `/api/materials/{material_id}/tree` | GET | 返回中附带每个节点的知识点标签 |

### 第10步：Memory Overlay 增强

**修改** `app/services/memory_overlay.py`

`get_student_memory_overlay` 增强逻辑：

1. 查询学生的薄弱节点（`StudentNodeState.health_score < 60`）
2. 对每个薄弱节点，JOIN `KnowledgePointMapping` → `KnowledgePoint`
3. 按 `knowledge_point_id` 跨教材聚合
4. 生成增强版摘要：
   - 旧：`"节点 abc-123: 健康度 45/100"`
   - 新：`"知识点【绝对值的性质】薄弱（涉及教材：七年级上、八年级上，健康度 42/100）"`
5. 当有 `material_id` 时按 subject 过滤

### 第11步：前端类型与 API

**修改** `frontend/src/types/material.ts`

```typescript
interface KnowledgePoint {
  id: string
  parent_id: string | null
  subject: string
  title: string
  summary: string | null
  keywords: string | null
  level: number
  source_count: number
  children?: KnowledgePoint[]
}
```

**修改** `frontend/src/api/materials.ts`

- `getMaterialKnowledgePoints(materialId: string)`: `GET /api/materials/{id}/knowledge-points`
- `getSubjectKnowledgeTree(subject: string)`: `GET /api/knowledge-points?subject=...`

**修改** `frontend/src/pages/student/KnowledgeForest.tsx`

- 每个 KnowledgeNode 旁显示关联的知识点标签
- 后续可扩展：切换为学科级知识点树视图

### 第12步：引导学习增强

**修改** `app/services/guided_learning.py`

`get_or_create_lesson` 增强：
- 查询当前 `node_id` 关联的知识点列表（通过 KnowledgePointMapping）
- 返回数据添加 `knowledge_points: List[KnowledgePointBrief]`
- IMPORT 阶段的 `step_prompt` 包含知识点标题列表

IMPORT 阶段 prompt 模板修改：
```
旧："节点标题：{node_title}\n内容摘要：{content_preview}"
新："节点标题：{node_title}\n内容摘要：{content_preview}\n本节知识点：{knowledge_point_titles}"
```

其中 `knowledge_point_titles` 格式为 `"绝对值的定义、绝对值的性质、绝对值的几何意义"`（逗号分隔）。

**修改** `frontend/src/pages/student/StudyCabin.tsx`

- IMPORT 阶段显示知识点标签卡片（从 lesson 数据中获取）

## 5. 文件变更清单

| 操作 | 文件 | 改动说明 |
|------|------|---------|
| 新建 | `app/models/knowledge_point.py` | KnowledgePoint + KnowledgePointMapping ORM 模型 |
| 新建 | `app/services/knowledge_point_extractor.py` | 知识点提取、去重、映射服务 |
| 新建 | `alembic/versions/add_knowledge_point_tables.py` | 数据库迁移脚本 |
| 修改 | `app/models/__init__.py` | 导入新模型 |
| 修改 | `app/models/material.py` | KnowledgeNode 添加 kp_mappings relationship |
| 修改 | `app/models/testing.py` | StudentMistake 添加 knowledge_point_id FK |
| 修改 | `app/routers/materials.py` | 两条构建路径调用提取器 + 删除清理 + 新 API 端点 |
| 修改 | `app/services/memory_overlay.py` | 知识点级别的薄弱聚合 |
| 修改 | `app/services/guided_learning.py` | IMPORT 阶段展示知识点 |
| 修改 | `app/agent/tools/pageindex_tools.py` | 新增跨教材搜索工具 + 缓存 |
| 修改 | `app/agent/tools/candidate_filter.py` | 知识点过滤/排名函数 |
| 修改 | `app/agent/graph.py` | 注册新工具，supervisor 传递 subject |
| 修改 | `app/agent/state.py` | AgentState 添加 subject |
| 修改 | `app/agent/sub_agents/tutor_base.py` | 工具绑定逻辑重写 + 提示词更新 |
| 修改 | `app/routers/chat.py` | agent_input 添加 subject 初始值 |
| 修改 | `app/schemas/materials.py` | 知识点响应 schemas |
| 修改 | `frontend/src/types/material.ts` | KnowledgePoint TS 类型 |
| 修改 | `frontend/src/api/materials.ts` | 知识点 API 调用 |
| 修改 | `frontend/src/pages/student/StudyCabin.tsx` | IMPORT 展示知识点 |
| 修改 | `frontend/src/pages/student/KnowledgeForest.tsx` | 知识点标签展示 |

共计：**3 个新建文件 + 17 个修改文件**

## 6. 验证方式

| 编号 | 验证项 | 预期结果 |
|------|--------|---------|
| 1 | `alembic upgrade head` | 迁移成功，knowledge_points 和 knowledge_point_mappings 表存在 |
| 2 | 上传教材 A | knowledge_points 和 knowledge_point_mappings 表有数据，知识点粒度为概念级 |
| 3 | 上传同学科教材 B | 去重生效：相同概念复用（source_count 递增），新概念新建 |
| 4 | 删除教材 A | mappings 清理、source_count 递减、无 FK 约束错误 |
| 5 | 调用 `search_knowledge_points` | 返回来自多本教材的内容，且仅包含学生已激活的教材 |
| 6 | 前端 IMPORT 阶段 | 显示当前节点关联的知识点标签列表 |
| 7 | Memory Overlay 报告 | 包含知识点标题（"绝对值的性质"而非 "节点 abc-123"） |
| 8 | 现有功能回归 | 5 步教学流、出题、评估不受影响 |

## 7. 已知限制与后续优化

| 项目 | 说明 |
|------|------|
| `ingest_material` 不清理旧 KnowledgeNode | 重复上传同一教材会创建重复节点（已有问题，不在本方案范围内修复） |
| ~~`delete_material` 中 Question 表缺少级联~~ | **已修复**：已在 delete_material 的手动删除循环中添加 `(Question, Question.node_id)` |
| ~~非流式 chat 端点缺少 `current_intent`~~ | **已修复**：已在 `chat.py` 非流式端点的 `agent_input` 中添加 `"current_intent": request.intent or "chat"` |
| ~~`search_knowledge_tree` 未验证教材激活~~ | **已修复**：已在搜索前查询 `BookActivation` 验证学生是否激活了该教材 |
| ~~`ingest_material` 返回值缺少 `node_count`~~ | **已修复**：已在 commit 后查询 KnowledgeNode 计数并返回 |
| 知识点提取质量依赖 LLM | 提取的粒度和一致性取决于 fast model 的能力，可能需要迭代 prompt |
| 知识点树需要人工校验 | 自动构建的树可能有分类不当，后续可加管理界面人工调整 |

## 8. 与现有功能的对接点

| 现有实现 | 对接方式 |
|---------|---------|
| SUMMARY 阶段 LLM 提炼"知识点考向标签" | 可将 SUMMARY 输出的标签与 KnowledgePoint 关联，形成闭环（后续优化） |
| `QuestionGenerate.knowledge_points: List[str]` | 出题时已有关联知识点的概念，可与 KnowledgePoint.id 对接（后续优化） |
| `KnowledgeNode.is_key_node` | 知识点提取器可优先从重点章节（is_key_node=1）的节点提取，提高提取质量 |
| `StudyCabin.tsx` IMPORT 提示"回顾前置知识" | 可用知识点树的 parent 关系提供结构化的前置知识点列表 |
