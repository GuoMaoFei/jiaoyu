# 智树 (TreeEdu) Agent - 后端核心架构与详细设计文档

## 1. 系统定位与开发起点

智树 (TreeEdu) Agent 的后端旨在构建一个**严格遵循教纲边界**、**提供 24 小时苏格拉底式启发**的教育智能体平台。

> **当前状态**：后端全部完成 ✅。五大 Agent + 10 个 LangGraph 工具 + 19 个 FastAPI 端点 + SSE 流式对话 + OCR 视觉 + 艾宾浩斯复习引擎。**V1.1 重构**：完成 KnowledgeNode/KnowledgeContent 骨肉分离 + 推理型 RAG 四步检索链 + 统一书架改造。**V1.2 优化**：实现方案 C 动态 LLM 选择（根据五步教学阶段分级调度模型）+ 学习舱自动讲解。

### 1.1 核心技术栈与架构模式
- **Web 框架**: FastAPI - 提供全异步的基础架构与 Swagger API 支持。
- **持久层**: SQLAlchemy 2.0 (Async) + Alembic + SQLite/PostgreSQL - 支撑 6 大教育领域复杂模型。
- **知识树构建与检索中枢**: **PageIndex (已实现纯本地化私有部署)**
  - **建树阶段 (Ingestion)**：解析 PDF 教材，提取结构化特征，构建无向量"章-节-知识点"物理树。骨架存入 `KnowledgeNode`（轻量索引 + `pi_nodes_json`），内容存入 `KnowledgeContent`（富文本正文）。
  - **检索阶段 (Reasoning RAG)**：四步推理检索——① 聚合当前章节及前序章节的 `pi_nodes_json` 摘要池 → ② LLM 路由推理选出目标 `pi_node_id` → ③ 精准取回 `KnowledgeContent` 全文 → ④ 喂给 Tutor Agent 生成引导式回答。
- **智能体控制流**: **LangGraph**
  - 使用 `StateGraph` 构建循环推理图替代传统的单链 Prompt。
  - **采用多 Agent 协同网络 (Multi-Agent System)**：为了应对复杂多变的教育场景，摒弃“一个全能超大模型包打天下”的做法。采用 **Supervisor-Worker** 模式，由主控总线根据场景路由分发给专职的 Sub-Agent（如专门负责规划的 Planner Agent、负责出题的 Assessment Agent、负责共情陪伴的 Tutor Agent），各自携带专属的 Prompt 与可用工具。


## 2. Multi-Agent 架构与 PageIndex 的深度联动

在真正的复杂教育系统中，不可能用一个简单的 Prompt 完成所有的教务功能。智树后端的 Agent 层采用 **Multi-Agent 协作网络**（基于 LangGraph 的 Multi-Agent 模式或 Sub-Graphs 封装）：

### 2.1 智能体兵营 (Sub-Agents) 设计
为了应对 PRD 的五大核心业务流，我们至少切分出以下几类专业 Agent：

1. **Planner Agent (规划统筹师)**：
   - **职责**：不带任何解题能力，只负责统筹大局。
   - **工具/能力**：接收当前可用时间、读取剩余知识点占比，能够调用时间规划 API，排布生成 `STUDY_PLAN` 与 `PLAN_ITEM`。
2. **Tutor Agent (苏格拉底讲师)**：
   - **职责**：专门处理“引导式课程学习”与“拍题答疑”。
   - **能力机制**：手里**必定挂载 PageIndex 工具**。接收到学生提问后，先去 PageIndex 锚定教材树知识点坐标，再结合 `STUDENT_NODE_STATE.health_score`（知道这孩子哪里薄弱），发出“基于教材原文”的启发反问。
3. **Assessment Agent (冷酷阅卷人)**：
   - **职责**：不和学生闲聊。专门负责隐式评估与显式测验的批改。
   - **能力机制**：接管学生的话语片段或试卷结果，只输出严厉且客观的 `score_delta` 和诊断结论（如错因：公式展开漏项），最后无情写回数据库 `TEST_RECORD` 或 `CHAT_ASSESSMENT`。
4. **Variant Agent (变式考官)**：
   - **职责**：专门负责出卷（场景5）和打捞错题魔改（场景4）。
   - **能力机制**：接收一个薄弱的 `node_id` 和原题文本，剥离原题核心考察点，随机套用新的生活情景或稍微改换数字，输出一套确保结构正确的 Markdown 题目供前台展卷。
5. **Report Agent (学情观察员) [补漏]**：
   - **职责**：不直接面对学生，专职为家长服务。
   - **能力机制**：每周或按需被 CRON 唤醒，拉取学生一周内在 `CHAT_ASSESSMENT` 和 `TEST_RECORD` 中的表现，总结出柔性的 Markdown 周报，写入 `PARENT_WEEKLY_REPORT`。

### 2.2 引擎协作工作流 (The Flow)
1. **主控路由 (Supervisor/Router Node)**：统一接收前端的 Payload (可能是“我进主页了”、“这题不会做”、“我要自测”等不同意图)。
2. **场景分发**：
   - 若是“进主页领任务”，唤醒 **Planner Agent**。
   - 若是“这道题我不会”，系统将题目文本和历史错题画像扔给 **Tutor Agent**。
3. **调用 PageIndex 检索中枢 (以 Tutor Agent 为例)**：
   - Tutor Agent 调用 PageIndex 的 Tree-Search 接口，在特定的教材树（通过 `material_id`）中向下遍历，精准命中对应的叶子节点。
4. **内部交接棒 (Sub-Agent Handoff)**：
   - Tutor Agent 问了一轮，学生答对了。Supervisor 切断 Tutor 流，将学生的话术传给内置的 **Assessment Agent** 进行打分评价入库，随后再切回 Tutor 继续新知识点。
5. **图状态持久化 (Checkpointing)**：无论在哪个 Sub-Agent 里缠斗，LangGraph 的 Checkpointer 全盘接管所有会话记忆入库，无缝支持中断恢复。

### 2.3 大模型多业态网关与配置管理 (Model Config & Gateway)
在复杂的教育智能体中，让一个顶级大模型处理所有事务会导致延迟和算力成本灾难。系统在 `utils/llm_router.py` 内部引入了**模型工厂与业态管理层**，按需供给：
1. **轻型调度流 (Fast, 如 qwen-plus)**：
   - **使用方**：Supervisor 意图路由节点、Planner 计划排期生成、Reporter 家长周报生成、**Tutor Agent 的 IMPORT/PRACTICE 阶段**。
   - **特性**：JSON 结构化输出极快，极其适合“数据处理与任务分发”这种不涉及重度逻辑推演的业务。
2. **中型推理流 (Medium, 如 qwen-turbo)**：
   - **使用方**：Tutor Agent 的 EXAMPLE/SUMMARY 阶段。
   - **特性**：平衡成本与效果，适合需要一定推理但不需要最顶级模型的任务。
3. **重度推理与共情流 (Heavy, 如 qwen-max-latest / DeepSeek-R1)**：
   - **使用方**：Tutor Agent 的 EXPLAIN 深入讲解阶段、Assessor 客观评分员的答案对齐。
   - **特性**：需要吃透知识树的绝对定位与历史错因（Structural Memory），给出极为高商且丝滑的教学引导。
4. **多模态视觉流 (Vision-Language, 如 qwen-vl-max-latest)**：
   - **使用方**：专门支持 `vision_ocr.py` 的手写体图片转录与 LaTeX 公式识别。

#### 2.3.1 五步教学法动态模型调度策略
为了进一步优化成本和响应速度，系统针对 Tutor Agent 的五步闯关教学阶段实现了**动态模型选择**：
| 教学阶段 | 模型类型 | 具体模型 | Temperature | 特点 |
|---------|---------|---------|-------------|------|
| IMPORT (🔥 基础预热) | Fast | qwen-plus | 0.7 | 生活化类比、激发兴趣、响应速度快 |
| EXPLAIN (📖 深入讲解) | Heavy | qwen-max | 0.2 | 深度讲解、知识准确性、逻辑严密 |
| EXAMPLE (✏️ 典型例题) | Medium | qwen-turbo | 0.3 | 逻辑推理、步骤清晰 |
| PRACTICE (🎯 上手实操) | Fast | qwen-plus | 0.5 | 快速评判、简洁反馈 |
| SUMMARY (🏆 总结复盘) | Medium | qwen-turbo | 0.3 | 结构化总结、知识点提炼 |

**预期效果**：响应速度提升约 40%，API 成本降低约 35%，同时保证核心教学阶段（EXPLAIN）的质量。

系统通过环境配置文件 (`config.py` 与 `.env`) 建立多通道管理机制，使得四大业态模型可以随时独立替换供应商。目前系统已**全面切换至阿里云通义千问大模型阵列**，在保证顶级推理效果的情况下实现了极大成本节约和国内访问稳定性。


## 3. 分阶段开发拆解 (Long-Term Sprint Roadmap)

鉴于这是一个长周期的强业务后端项目，不能一蹴而就。我们将其严格拆分为 **5 个 Sprint (约 5-6 周)** 进行循序渐进的交付：

### Sprint 1：基础设施骨架与基底能力 (Week 1)
这是整个万里长征的第一步，重塑干净的底盘。
1. **环境与容器化**：初始化基于 `FastAPI` / `uvicorn` 的标准异步后端结构，确立 `requirements.txt` 和 `.env` 鉴权标准。
2. **大模型网关 (`utils/llm_router.py`)**：率先封装 Fast(调度) / Medium(中等推理) / Heavy(推理) / Vision(视觉) 四通道模型 API 接口，并写单元测试跑通。
3. **ORM 物理层建立**：部署 `database.py` 引擎，并通过 `Alembic` 建表拉起最基础的三大模型文件 (教材树 `material.py`、身份 `user.py`、跨端对话 `chat.py`)。

### Sprint 2：跨模态知识树构建与长时记忆引擎入库 (Week 2)
真正攻克第一道智能体门槛：让机器读懂课本，建立精准视觉大纲上帝视角。
1. **视觉大纲提取 (V-Catalog)**：使用 `PyMuPDF` 截取教材前 N 页目录图像，接入核心视觉大模型 (VLM, 如通义千问VL) 提取结构化、符合人类排版的真实大纲 JSON 树，落库为 `KNOWLEDGE_NODE` 主树。
2. **PageIndex 黑盒建树**：完整上传 PDF 至 PageIndex，获取其自动聚类生成的内部隐式树节点集合及其节点摘要。
3. **双树映射桥接 (Dual-Tree Mapping)**：通过 LLM 异步执行，将 PageIndex 散乱的隐式节点 (Node_ID) 语义关联软挂载到 `KNOWLEDGE_NODE.mapped_pi_nodes` 字段中。完美解决图文排版导致的提取歧义，并保留强大的 PageIndex 树溯源能力。
4. **核心 API 开放**：完成上传、混合查树的基础 CRUD 路由。
5. **ORM 第二梯队落地**：完成业务排期、随堂测试相关表结构 (`lesson.py`, `testing.py`) 的落库。
4. **长时记忆覆写层 (Memory Overlay) 雏形**：在 ORM 侧构建专门的 Hook，尝试在提取 `KNOWLEDGE_NODE` 时能左连获取 `STUDENT_NODE_STATE`。

### Sprint 3：LangGraph 多智能体兵营主核研发 (Week 3) (开发中)
最核心的 AI 编排层，决定了智能体“有多聪明不惹祸”。
1. **状态黑板定义 (`agent/state.py`)**：精巧划定 Global Graph State，放入意图锁、历史画像摘要。
2. **Supervisor 总线搭建 (`agent/graph.py`)**：编写 LangGraph 的 Router 节点，实现按意图分发。
3. **伴读神仙 (Tutor Agent) 攻坚**：编写 `tutor.py`。它将成为第一个实质落地的 Sub-Agent，**深度联动 PageIndex**: 通过绑定的 LangChain Tool，结合传入的 Memory Overlay (历史错因)，去 PageIndex 映射的本地库中提取对应的无向量树干原文，最终发出高智商反问。
4. **铁血阅卷人 (Assessor Agent)**：构建客观评分与诊断机制。**深度联动 PageIndex**: 每次批改结束，自动将解析出的“结构化错因”和“得分变化”写回到对应的 PageIndex Node ID（`STUDENT_NODE_STATE`）上，完成**长时记忆的物理闭环覆写**。

### Sprint 4：上层业务五大场景串联 (Week 4) ✅ 已完成
底层机制备齐后，向上供给前端五大业务场景 API 路由。
1. **破冰与规划 (Planner Agent)**：打通 `services/onboarding.py`。**深度联动 PageIndex**: Planner Agent 会遍历 PageIndex 解析构建的 `KNOWLEDGE_NODE` 全量实体树（比如从“必修第一章”到“第五章”的全部节点级联关系），匹配可用课时，生成严丝合缝的树状排期表 `PLAN_ITEM`。
2. **引导式进度控制**：对接 `services/guided_learning.py` 的五步状态机。确保学生在闯关时，系统通过当前关卡的 PageIndex Node ID 追踪进度。
3. **流式会话网关**：定版 WebSocket 或 Streaming Response HTTP 接口，让前端能够打字交互。
4. **OCR 视觉通路验证**：开发 `utils/vision_ocr.py`，验证从图片到 LaTeX 公式到大模型解析的高可用。

### Sprint 5：变式题库、复查机制与封测联调 (Week 5+) ✅ 已完成
查漏补缺与高阶功能的下发。
1. **变式出卷机 (Variant Agent)**：打通 `services/testing_gen.py`。**深度联动 PageIndex**: 根据传入的薄弱 `node_id`，利用 PageIndex 树状检索找出同一叶子节点下的"官方标准题源"，基于同构知识树模型，大模型剥离原考点，生成全新的 Markdown 物理快照试卷。
2. **微测生成模块**：实现 `services/quiz_generator.py`。基于知识节点动态生成微测试卷，包含：
   - LLM 分析节点复杂度、学生历史表现，决定出题策略
   - 动态生成题目数量、题型分布、时间限制
   - 支持单选题、填空题、简答题等多种题型
   - 答题进度保存与恢复
3. **自动学情观察员 (Reporter Agent)**：**深度联动 PageIndex**: Agent 会按需扫表，根据 PageIndex 教材树的章节聚类结构（例如发现 Chapter 1 下属的 5 个 Concept Node 均变红），自动总结出结构化的家长 Markdown 报告（"第一章代数基础极不牢固，集中在解方程节点"）。
4. **艾宾浩斯打捞**：实现 `services/adaptive_review.py` 定时触发器，强行注入旧错题。
5. **并发抢占处理**：在核心接口中补充并发压测，必要时升级为悲观锁。

---

## 4. 目录结构设计 (最终定本)

鉴于 `backend/` 目录从零开始重构，我们将严格建立如下拓扑以容纳上述设计：

```text
backend/
├── app/
│   ├── main.py             # FastAPI App 构建与中间件
│   ├── config.py           # Pydantic Settings
│   ├── database.py         # SQLAlchemy Engine & SessionMaker
│   ├── models/             # ORM 模型定义 (PRD 中的六大领域)
│   │   ├── lesson.py       # 学习计划、进度相关模型
│   │   └── quiz.py         # 微测题目、成绩模型
│   ├── schemas/            # Request/Response Pydantic 校验类
│   ├── routers/            # 统管 API 入口
│   │   ├── materials.py    # 包含树查询，建树触发
│   │   ├── lesson.py       # 学习计划、学习进度 API
│   │   ├── quiz.py         # 微测生成、提交 API
│   │   ├── chat.py         # LangGraph 会话交互路由
│   │   └── testing.py      # 生成试卷与复习管理 API
│   ├── services/           # 核心业务组件
│   │   ├── tree_builder.py # PageIndex 知识树构建任务
│   │   ├── quiz_generator.py # 微测生成服务
│   │   ├── guided_learning.py # 五步导学服务
│   │   ├── adaptive_review.py # 艾宾浩斯遗忘算法
│   │   └── memory_overlay.py  # 学习记忆叠加
│   ├── agent/              # LangGraph Multi-Agent 核心大脑群 🧠
│   │   ├── state.py        # 全局协同 State 定义 (持全局黑板)
│   │   ├── graph.py        # Supervisor 路由主干图编译
│   │   └── sub_agents/     # 专职 Sub-Agents
│   │       ├── tutor.py    # 伴读/苏格拉底讲师 Agent (挂载 PageIndex 武器)
│   │       ├── planner.py  # 学情规划排期 Agent
│   │       ├── assessor.py # 铁血评分判定 Agent
│   │       ├── variant.py  # 变式造题引擎 Agent
│   │       └── reporter.py # 家长周报生成 Agent
│   └── utils/              # 通用功能 (OCR连接、日志等)
│       ├── llm_router.py   # 大模型业态网关，分发快慢模型
│       ├── vision_ocr.py   # 封装大模型 Vision 能力解析手写错题
│       └── vlm_catalog.py  # VLM 目录提取工具
├── alembic/                # DB Migration 脚本目录
├── requirements.txt        # 最新版核心生态全家桶
└── .env.example
```

---

## 5. 架构复盘：当前设计中“不够完美”的妥协

作为架构师，没有任何系统是完美的。为了贴合 V1.0 的极速验证诉求并兼顾未来，本架构有以下 3 个显著的“已知妥协”与“待解痛点”：

### 5.1 知识树版本控制（缺乏 Immutable 设计）
**当前状况**：我们允许通过 `tree_builder.py` 覆盖更新一本书的 `KNOWLEDGE_NODE`。
**风险**：如果系统发版半年后，官方教材改版（合并了第一章和第二章）。如果在原表上直接 DELETE/UPDATE，那千万学生挂载在其上的 `STUDENT_MISTAKE` 和 `LESSON_PROGRESS` 外键将发生级联惨案或产生孤儿错题。
**未来演进**：必须引入 `material_version` 概念。教材变更是发新版，旧版树变成只读属性（Read-only Archive）。

### 5.2 大会话上下文长时记忆 (Token Window 膨胀) 的终极解法：PageIndex 学情覆写 (Memory Overlay)
**原有痛点**：LangGraph 的 Checkpointer 会记录无限长的对话历史。随着时间推移，不仅撑爆 LLM 上限，还会引发不可控的幻觉。传统的做法是让 LLM 定期做文本摘要。
**终极架构解法（您的提议）**：**「用结构化记忆代替自然语言记忆」**。
结合我们的底层设计，我们不需要也不能强行给大模型喂长达半年的闲聊记录。我们利用 **PageIndex** 的强结构属性，建立一层 **"Student Profile Overlay (学生个人学情覆写层)"**：
1. **记忆剥离入库**：当 Assessor Agent 每次对学生的回答做出评价后，切断该对话在上下文中的驻留，而是将其提炼为客观数据（对/错、错因、耗时），写入 `STUDENT_NODE_STATE`（个人知识点掌握表）和 `STUDENT_MISTAKE`。
2. **检索时的动态附魔 (Expert Preference Injection)**：根据 PageIndex 的 LLM Tree Search 特性，它允许在检索 Prompt 中注入“专家知识/用户偏好”。当学生下一次提问，Tutor Agent 去 PageIndex 检索时，我们直接将该学生近期的**薄弱知识点标签和历史错因作为 Expert Preference 注入到 PageIndex 的检索入参中**。这样 PageIndex 在树搜索时就会物理上偏向于寻找该生容易犯错的关联节点。
3. **结构化 Prompt 投喂**：发给大模型进行最终回复的 Context 将不再是长篇大论的旧聊天记录，而是精准且冰冷的结构化态势感知：
   > "当前讨论知识点：全等三角形 (节点 402)"
   > "PageIndex 官方教案：[公式原文...]"
   > "该生当前健康度：40/100 (薄弱)"
   > "该生在此节点下的历史核心错因：忽略了边长对应条件、计算两次出错。"
   
通过将**“对话历史”**转化为**“挂载在 PageIndex 树上的属性字段”**，我们彻底根除了 Token 膨胀灾难，让 Agent 真正拥有了永不褪色、永不膨胀的“上帝视角”。

### 5.3 并发写库状态竞争 (Race Condition)
**当前状况**：当学生进行连环快问快答时，Tutor Agent 尚未走完评估流，Assessor Agent 还在异步计算 `health_score`，极容易因为 SQLAlchemy AsyncSession 未显式加锁导致 `health_score` 计算回跳（脏读脏写）。 
**未来演进**：如果是读多写多的状态（如健康度），后期需要引入 Redis 拦截变更池或在 PG/SQLAlchemy 层使用 `SELECT ... FOR UPDATE` 加悲观锁。但在 V1.0 SQLite PoC 阶段，目前架构全盘交由单体锁承受，存在并发性能天花板。

### 5.4 PageIndex 树检索的全面完全私有化部署 (已完成 ✅)
**原有痛点**：长期运营如果依赖 PageIndex 外部 API 会存在大基座极大的教育数据隐私风险，且计费高昂。
**当前解决 (V1.0 末期已提前攻克)**：我们已经完全卸载了官方闭源 SDK，将 PageIndex 的核心开源算法库克隆并深层集成至了本地 `backend/pageindex` 模块下。现在的后端在建树和抽取阶段，将**直接拉起本地线程池，驱动配置好的阿里云（Qwen-Max）通过内部算法对教材进行混合 MCTS 构建**。
**里程碑意义**：系统彻底摆脱了强外部供应商依赖，实现了 **数据 100% 本地脱网流转 + 模型接口自主切换 + API 费用断崖式下跌**。这标志着智树 Agent 具备了被私有化部署至全封闭校园内网或培训机构机房的终极底座技术实力。
