# TreeEdu Agent (智树) — 全链路联调与自动化测试计划 (Milestone 5)

## 1. 目标与范围

Milestone 5 的核心目标是将前端现有的 9 个 Mock 页面与后端的 19 个 FastAPI 端点进行全面对接，并在对接完成后建立自动化测试防线，确保 V1.0 系统在交付前具备高度的稳定性与可用性。

**测试范围**：
- 前后端全链路联调（API 契约验证、数据格式对齐）
- 大模型 Agent 流式输出（SSE）稳定性验证
- 核心业务流闭环验收（学生使用核心场景）
- 自动化测试（前端 Vitest 组件/Hooks 测试，后端 Pytest 接口与 Agent 逻辑测试）

---

### 1.1 测试资源准备
- **测试真实教材**：`jiaocai/（根据2022年版课程标准修订）义务教育教科书·语文一年级上册.pdf`。我们需要通过 PageIndex 将此 PDF 转换为结构化的知识点大纲（章、节、图谱），并作为核心数据供前端以及各 Agent 调用。

---

## 2. 阶段一：前后端全链路联调 (API Integration)

在此阶段，我们将逐页拆除前端的 Mock 数据，替换为真实的 `axios` 和 `fetch-event-source` 请求。

### 2.1 基础模块对接
- **[ ] Auth / Login**：对接 `/api/students/login`。联调 JWT Token 下发与前端 Header 拦截器装载。
- **[ ] Profile / Dashboard**：对接 `/api/students/{stu_id}/profile`，拉取真实的健康度、结课数量等。
- **[ ] Bookshelf / Outline**：对接 `/api/students/{stu_id}/bookshelf` 与 `/api/materials/{material_id}/outline`，验证真实层级树结构（章 -> 节 -> 考点）的加载。

### 2.2 核心学习流联调 (关键路径)
- **[ ] StudyCabin (学习舱)**：
  - 加载节点状态：`/api/lessons/status`
  - SSE 流式对话：对接 `/api/chat/stream`，验证 Tutor Agent 和 Assessor Agent 的状态流转（`event: node`）、文本块渲染（`event: chunk`，包含 Markdown 和 KaTeX）及最终收尾（`event: done`）。
- **[ ] KnowledgeForest (知识书林)**：
  - 对接 `/api/students/{stu_id}/nodes`，验证 ECharts 树图是否能根据真实的节点 `mastery_level` 渲染红、黄、绿颜色。

### 2.3 闭环与扩展模块联调
- **[ ] MistakeHub (错题枢纽)**：对接 `/api/students/{stu_id}/mistakes`，验证错题记录的获取及根据教材、状态（复习中/未解决等）的过滤。对接变式题生成能力。
- **[ ] StudyPlan (学习计划)**：对接 Planner Agent，验证按月度、按天的学习任务时间表及日历热力图渲染。
- **[ ] ParentReport (家长周报)**：对接 Reporter Agent (`/api/reports/generate`)，验证生成耗时、Markdown 排版及 AI 评价的合理性。
- **[ ] 诊断与考试 (Diagnostic & Exam)**：打通组卷逻辑、提交批改链路（利用 Assessor 校验简答题），并保存 `TestRecord`，记录知识树能力的倒扣或上升。

---

## 3. 阶段二：场景驱动的 E2E 手工验收 (User Journey)

为了证明系统跑通，需要建立一个完整的测试账号（如 `stu_demo`），并以《语文一年级上册》作为主测教材，执行以下生命周期闭环：

| 验收场景 | 预期系统表现 | 验证点 |
|:---|:---|:---|
| 1. **"摸底定位"** | 用户登录后进行入学诊断，错题被记录 | 知识树对应节点由灰变红（薄弱）。|
| 2. **"学新课"** | 进入红色/灰色的底座知识节点阅读图文并进行单轮 QA | Agent 对话稳定，讲解清晰带有数学公式。|
| 3. **"随堂测验"** | Tutor 认为讲清楚后交接给 Assessor 发起微测，用户做错 | 错题本新增一条记录 `is_resolved=False`。节点颜色保持黄或红。|
| 4. **"复习变式"** | 隔天用户在推卷或错题本中遇到变式题，作答正确 | 错题状态流转为 `solved`，原节点颜色升级为绿色。|
| 5. **"全揽学情"** | 周末家长登录/查看学情周报 | 周报精准捕获了步骤 3 的错误和步骤 4 的克服，给出针对性建议。|

---

## 4. 阶段三：自动化测试防线 (Automated Testing)

联调稳定后，用自动化测试代替部分手工劳动，保证长期可维护性。

### 4.1 后端测试 (Pytest)
- **API 契约测试**：针对 19 个 FastAPI API，编写带有 DB Rollback 或 SQLite In-memory 测试（验证 200 返回值与非法入参的 422/400）。
- **Agent 工具测试**：重点对 `pageindex_tools.py`、`variant_tools.py` 的解析与重组逻辑进行纯函数级单测。
- **大模型 Mock 测试**：通过 `unittest.mock` 拦截对 LLM 的真实 HTTPS 调用，返回预设的固定 prompt，验证 Agent 路由图流转逻辑（如 Supervisor -> Assessor 的流转判断）。

### 4.2 前端测试 (Vitest + React Testing Library)
- **Store 逻辑测试**：对 Zustand (`useMistakeStore`, `useTreeStore`) 状态管理的 reducer 单测。
- **复杂组件测试**：
  - 测试 `Markdown/KaTeX` 的渲染挂载。
  - 热力图时间范围换算工具函数的单测。
- *(可选，取决于时间)* E2E 测试 (Playwright/Cypress)：利用录制工具录制"登录->进学习舱->发一句话"的核心主链路。

---

## 5. 项目上线与交付清单 (V1.0 Checklist)
- [ ] 前端打包：移除所有 `#ifdef MOCK` 或冗余假数据，清理 `console.log`。
- [ ] 后端压测：连接池调优（SQLAlchemy `pool_size`），SSE 并发连接验证。
- [ ] O1 提示词封版：确定 Tutor/Assessor prompt 在当前选定模型（GPT-4/Claude3）下的最优形态。
- [ ] 文档沉淀：输出系统使用说明与后端部署 `docker-compose.yml` 示例。 

*(文档持续更新)*
