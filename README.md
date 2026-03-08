# TreeEdu Agent 🌳

一个基于 LangGraph 多智能体架构的智能教育平台，为学生提供个性化、自适应的学习体验。

## 项目简介

TreeEdu Agent 是一个全栈教育 AI 平台，通过多智能体协作实现智能辅导、学习评估、错题管理和学习报告等功能。系统将教材内容解析为知识树结构，并结合学生的实时学习状态提供个性化的学习路径。

### 核心特性

- **📚 智能知识树构建**：基于 PageIndex 技术自动解析 PDF 教材，生成结构化知识节点
- **🤖 多智能体协作**：Supervisor、Tutor、Assessor、Planner、Variant、Reporter 六大智能体协同工作
- **📖 五步导学法**：IMPORT → EXPLAIN → EXAMPLE → PRACTICE → SUMMARY 结构化学习流程
- **📊 学习记忆叠加**：实时追踪学生的知识掌握度（健康分数）和薄弱节点
- **📝 智能出题与评估**：基于知识节点自动生成练习题并评估答题情况
- **📈 学情分析报告**：为家长和学生提供可视化的学习进度和薄弱点分析

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React 19)                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 书架    │ │学习舱   │ │错题本   │ │知识森林 │ ...       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LangGraph Multi-Agent System             │   │
│  │  ┌──────────┐  ┌────────┐  ┌──────────┐              │   │
│  │  │Supervisor│→│ Tutor  │→│ Assessor │              │   │
│  │  └──────────┘  └────────┘  └──────────┘              │   │
│  │  ┌──────────┐  ┌────────┐  ┌──────────┐              │   │
│  │  │ Planner  │  │Variant │  │ Reporter │              │   │
│  │  └──────────┘  └────────┘  └──────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│  ┌─────────────┐  ┌─────────────────┐  ┌────────────────┐   │
│  │   Router    │  │    Service      │  │   SQLAlchemy   │   │
│  │   Layer     │  │     Layer       │  │   Async ORM    │   │
│  └─────────────┘  └─────────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Database (SQLite)                          │
│  Students │ Materials │ KnowledgeNodes │ ChatSessions │ ... │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 编程语言 |
| FastAPI | - | 异步 Web 框架 |
| SQLAlchemy | 2.0 | 异步 ORM |
| LangGraph | - | 多智能体编排框架 |
| Pydantic | v2 | 数据验证 |
| Alembic | - | 数据库迁移 |
| PageIndex | - | PDF 知识树解析 |

### 前端
| 技术 | 版本 | 说明 |
|------|------|------|
| React | 19.2 | UI 框架 |
| TypeScript | 5.9 | 类型安全 |
| Vite | 7.3 | 构建工具 |
| Tailwind CSS | 4.2 | 样式框架 |
| Ant Design | 6.3 | UI 组件库 |
| Zustand | 5.0 | 状态管理 |
| Axios | 1.13 | HTTP 客户端 |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pnpm 或 npm

### 后端设置

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥

# 运行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### Docker 部署

```bash
# 构建并启动所有服务
docker-compose up --build

# 后台运行
docker-compose up -d
```

## 项目结构

```
jiaoyu_agent/
├── backend/
│   ├── app/
│   │   ├── agent/              # LangGraph 多智能体系统
│   │   │   ├── graph.py        # 状态图定义
│   │   │   ├── state.py        # AgentState 类型定义
│   │   │   ├── sub_agents/     # 子智能体实现
│   │   │   └── tools/          # 智能体工具函数
│   │   ├── models/             # SQLAlchemy ORM 模型
│   │   ├── routers/            # FastAPI 路由处理器
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层
│   │   │   ├── tree_builder.py     # 知识树构建服务
│   │   │   ├── guided_learning.py  # 五步导学服务
│   │   │   ├── adaptive_review.py  # 自适应复习服务
│   │   │   └── memory_overlay.py   # 学习记忆叠加
│   │   ├── utils/              # 工具函数
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库连接
│   │   └── main.py             # 应用入口
│   ├── alembic/                # 数据库迁移
│   ├── test_*.py               # 测试文件
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/                # API 客户端
│   │   ├── components/         # 可复用组件
│   │   │   ├── chat/           # 聊天相关组件
│   │   │   ├── layout/         # 布局组件
│   │   │   ├── quiz/           # 测验组件
│   │   │   └── tree/           # 知识树组件
│   │   ├── hooks/              # 自定义 Hooks
│   │   ├── pages/              # 页面组件
│   │   │   ├── auth/           # 认证页面
│   │   │   ├── student/        # 学生页面
│   │   │   └── parent/         # 家长页面
│   │   ├── stores/             # Zustand 状态管理
│   │   ├── types/              # TypeScript 类型定义
│   │   └── App.tsx             # 根组件
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml
├── AGENTS.md                   # AI 编码助手指南
└── README.md
```

## 核心功能模块

### 1. 多智能体系统

系统采用 LangGraph 构建的多智能体架构：

| 智能体 | 职责 |
|--------|------|
| **Supervisor** | 意图识别、任务分发、注入学习上下文 |
| **Tutor** | 苏格拉底式辅导、知识点讲解、答疑解惑 |
| **Assessor** | 答案评估、分数计算、错因诊断 |
| **Planner** | 学习计划生成、知识点排序 |
| **Variant** | 变式题生成、举一反三 |
| **Reporter** | 学情分析、报告生成 |

### 2. 五步导学法

每个知识节点的学习遵循结构化流程：

```
IMPORT (预热导入) → EXPLAIN (深入讲解) → EXAMPLE (典型例题) → PRACTICE (上手实操) → SUMMARY (总结回顾)
```

### 3. 学习记忆叠加

系统实时追踪每个学生对每个知识节点的掌握状态：
- **健康分数 (Health Score)**：0-100 分，反映知识掌握程度
- **薄弱节点识别**：自动识别分数低于阈值的知识点
- **历史错题关联**：追踪学生的错题记录用于个性化辅导

### 4. 知识树构建

通过 PageIndex 技术自动解析 PDF 教材：
1. 上传 PDF 文件
2. PageIndex 提取文档结构和内容
3. VLM 识别真实目录结构
4. 双树映射生成知识节点
5. 存储到数据库供查询使用

## API 端点

### 认证
- `POST /api/auth/login` - 学生/家长登录
- `POST /api/auth/bind-parent` - 绑定家长账户

### 聊天
- `POST /api/chat/send` - 发送消息给智能体
- `POST /api/chat/stream` - SSE 流式响应
- `GET /api/chat/sessions/{student_id}` - 获取会话列表

### 教材
- `GET /api/materials/` - 获取教材列表
- `POST /api/materials/` - 创建新教材
- `POST /api/materials/{id}/upload` - 上传 PDF 并构建知识树

### 学生
- `GET /api/students/{id}` - 获取学生信息
- `GET /api/students/{id}/mistakes` - 获取错题本
- `GET /api/students/{id}/bookshelf` - 获取书架

### 课程
- `POST /api/lesson/start` - 开始学习
- `POST /api/lesson/advance` - 进入下一阶段

### 考试
- `POST /api/exam/generate` - 生成试卷
- `POST /api/exam/submit` - 提交答案

### 报告
- `GET /api/report/parent/{student_id}` - 家长报告
- `POST /api/report/ocr` - OCR 识别

## 环境变量配置

在 `backend/.env` 中配置以下变量：

```env
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./treeedu.db

# LLM API Keys (至少配置一个)
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
DEEPSEEK_API_KEY=your_deepseek_key
ALIYUN_API_KEY=your_aliyun_key

# PageIndex
PAGEINDEX_API_KEY=your_pageindex_key

# JWT
JWT_SECRET_KEY=your_secure_secret_key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# 模型选择
LLM_FAST_MODEL=aliyun
LLM_HEAVY_MODEL=aliyun
LLM_VISION_MODEL=aliyun
```

## 开发指南

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 单个测试文件
pytest test_integration.py

# 详细输出
pytest -v test_integration.py
```

### 代码规范

- **Python**：遵循 PEP 8，使用类型提示，async/await 异步模式
- **TypeScript**：函数式组件，interface/type 类型定义，Zustand 状态管理
- **注释**：除非明确要求，否则不添加注释

详细规范请参考 [AGENTS.md](./AGENTS.md)

## 安全注意事项

⚠️ **生产环境部署前请务必：**

1. 轮换所有 API 密钥，确保 `.env` 不在版本控制中
2. 修改 JWT 密钥为强随机字符串
3. 配置 CORS 允许的源
4. 在敏感端点添加身份认证
5. 实现速率限制
6. 关闭调试日志

详见代码审计报告中的安全建议。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
