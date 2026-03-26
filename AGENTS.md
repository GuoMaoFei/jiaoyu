# AGENTS.md - TreeEdu Agent Project Guide

This document provides essential information for AI coding agents working on this codebase.

## Project Overview

TreeEdu Agent is a full-stack educational AI platform with:
- **Backend**: FastAPI (Python) with LangGraph AI agents, SQLAlchemy async ORM
- **Frontend**: React 19 + TypeScript + Vite with Tailwind CSS and Ant Design

## Build/Lint/Test Commands

### Frontend (from `frontend/` directory)

```bash
npm run dev          # Start development server (Vite)
npm run build        # Production build (TypeScript + Vite)
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

### Backend (from `backend/` directory)

```bash
# Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest

# Run a single test file
pytest test_integration.py

# Run a single test function
pytest test_integration.py::test_full_pipeline

# Run tests with verbose output
pytest -v test_integration.py

# Database migrations
alembic upgrade head      # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

### Docker

```bash
docker-compose up --build   # Build and start all services
docker-compose down         # Stop all services
```

## Code Style Guidelines

### Python Backend

#### Imports
```python
# Standard library first
import logging
import uuid
from typing import Optional, List

# Third-party packages
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

# Local imports (absolute paths from app/)
from app.database import get_db
from app.models.chat import ChatSession
from app.schemas.chat import ChatMessageRequest
```

#### Naming Conventions
- **Files**: `snake_case.py` (e.g., `chat.py`, `tree_builder.py`)
- **Classes**: `PascalCase` (e.g., `ChatSession`, `TreeBuilderService`)
- **Functions/Methods**: `snake_case` (e.g., `get_db`, `send_message`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `SESSION_TYPE`)
- **Private methods**: Prefix with `_` (e.g., `_internal_helper`)

#### Type Hints
- Always use type hints for function parameters and return types
- Use `Optional[T]` for optional parameters
- Use Pydantic models for API schemas

```python
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> ChatSession:
    ...
```

#### Error Handling
- Use HTTPException for API errors with appropriate status codes
- Log exceptions with `logger.exception()` for stack traces

```python
try:
    result = await db.execute(query)
except Exception as e:
    logger.exception(f"Database error: {e}")
    raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
```

#### Async Patterns
- Use `async/await` for all database operations and external API calls
- Use `AsyncSession` from SQLAlchemy for async DB operations

#### Pydantic Schemas
- Place request/response schemas in `app/schemas/`
- Use `Field()` for validation and documentation

```python
class ChatMessageRequest(BaseModel):
    student_id: str = Field(..., description="Student's unique ID")
    message: str = Field(..., min_length=1, description="Message text")
```

### TypeScript Frontend

#### Imports
```typescript
// React and third-party first
import { type ReactNode, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { message } from 'antd';

// Local imports (relative paths)
import { useAuthStore } from '../stores/useAuthStore';
import type { User } from '../types/auth';
```

#### Naming Conventions
- **Files**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Components**: `PascalCase` (e.g., `ChatBubble`, `MainLayout`)
- **Functions/Variables**: `camelCase` (e.g., `handleSubmit`, `isLoading`)
- **Constants**: `UPPER_SNAKE_CASE` or `camelCase` for object constants
- **Types/Interfaces**: `PascalCase` (e.g., `AuthState`, `ChatMessage`)
- **Store hooks**: Prefix with `use` (e.g., `useAuthStore`, `useChatStore`)

#### Type Definitions
- Use `interface` for object shapes, `type` for unions/intersections
- Prefer `type` keyword with explicit naming
- Use `type` keyword for importing types: `import type { X }`

```typescript
export interface User {
    id: string;
    name: string;
    role: 'student' | 'parent' | 'admin';
}

export type AuthState = {
    token: string | null;
    user: User | null;
    isAuthenticated: boolean;
};
```

#### React Components
- Use functional components with arrow functions
- Define props interface above component

```typescript
interface ChatBubbleProps {
    message: ChatMessage;
    isStreaming?: boolean;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isStreaming }) => {
    // Component logic
};

export default ChatBubble;
```

#### State Management (Zustand)
- Stores in `src/stores/` with `use` prefix
- Use `persist` middleware for localStorage persistence

```typescript
export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            token: null,
            setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
        }),
        { name: 'storage-key' }
    )
);
```

#### API Calls (Axios)
- API functions in `src/api/`
- Use the centralized `apiClient` from `client.ts`
- Handle errors in interceptors, not in individual calls

#### Styling
- Use Tailwind CSS utility classes
- Use `className` with template literals for conditional styles
- Use Ant Design components for complex UI elements

```typescript
<div className={`max-w-[75%] px-4 py-3 rounded-2xl ${isActive ? 'bg-blue-600' : 'bg-gray-200'}`}>
```

## Project Structure

```
jiaoyu_agent/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph agent definitions
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic layer
│   │   │   ├── quiz_generator.py    # 微测生成服务
│   │   │   ├── guided_learning.py   # 五步导学服务
│   │   │   └── adaptive_review.py   # 自适应复习服务
│   │   ├── utils/         # Utility functions
│   │   │   ├── llm_router.py        # LLM 模型路由
│   │   │   ├── vision_ocr.py        # OCR 视觉识别
│   │   │   └── vlm_catalog.py       # 目录提取
│   │   ├── config.py       # Settings and configuration
│   │   ├── database.py     # DB connection and session
│   │   └── main.py         # FastAPI app entry point
│   ├── alembic/            # Database migrations
│   ├── test_*.py           # Test files
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/            # API client functions
│   │   │   ├── auth.ts     # 认证相关 API
│   │   │   ├── lessons.ts  # 课程/学习计划 API
│   │   │   ├── quiz.ts     # 微测 API
│   │   │   └── client.ts   # Axios 客户端
│   │   ├── components/     # Reusable React components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── pages/          # Page-level components
│   │   │   ├── student/    # 学生端页面
│   │   │   │   ├── StudyPlan.tsx    # 学习计划页面
│   │   │   │   ├── NodeQuiz.tsx     # 微测页面
│   │   │   │   ├── StudyCabin.tsx   # 学习舱页面
│   │   │   │   └── ...
│   │   │   └── parent/     # 家长端页面
│   │   ├── stores/         # Zustand state stores
│   │   ├── types/          # TypeScript type definitions
│   │   │   └── lesson.ts   # 课程相关类型定义
│   │   ├── App.tsx         # Root component
│   │   └── main.tsx        # Entry point
│   ├── package.json
│   └── tsconfig.json
└── docker-compose.yml
```

## Key Technologies

### Backend
- **FastAPI**: Async web framework
- **SQLAlchemy 2.0**: Async ORM with `AsyncSession`
- **Pydantic v2**: Data validation and settings
- **LangGraph**: Multi-agent orchestration
- **Alembic**: Database migrations

### Frontend
- **React 19**: UI framework
- **TypeScript 5.9**: Type safety
- **Vite 7**: Build tool
- **Tailwind CSS 4**: Styling
- **Ant Design 6**: UI components
- **Zustand 5**: State management
- **Axios**: HTTP client

## Important Notes

1. **Comments**: Do NOT add comments unless explicitly requested
2. **Async**: All backend DB operations must use async/await
3. **Environment**: Copy `.env.example` to `.env` and configure API keys
4. **Database**: SQLite for development (`treeedu.db`)
5. **Chinese UI**: Frontend contains Chinese text - preserve it

## API Reference

### 学习计划 API (`/api/lessons/plans`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/plans/{student_id}` | GET | 获取学生的学习计划，支持 `?material_id=` 筛选参数 |
| `/plans/generate` | POST | 触发 Planner Agent 生成学习计划，需传 `student_id`, `material_id`, `start_date`, `sessions_per_week` |
| `/plans/{student_id}` | DELETE | 删除学习计划，支持 `?material_id=` 删除单个教材计划 |

### 学习计划数据模型 (PlanItem)

```python
class PlanItem(Base):
    id: str                    # UUID
    student_id: str            # 学生 ID
    material_id: str           # 教材 ID (V1.2 新增)
    node_id: str               # 知识节点 ID
    scheduled_date: date       # 计划日期
    task_type: TaskType        # NEW_KNOWLEDGE / REVIEW
    status: PlanStatus         # PENDING / IN_PROGRESS / COMPLETED / MISSED
    created_at: datetime
    completed_at: datetime     # 完成时间
```

### 生成学习计划流程
1. 前端调用 `POST /api/lessons/plans/generate` 传入 `student_id`, `material_id`, `start_date`, `sessions_per_week`
2. 后端触发 Planner Agent (LangGraph)
3. Planner Agent 调用 `get_material_node_list(material_id, student_id)` 获取知识树结构
4. `get_material_node_list` 只返回 Level 2 的节点（实际课文），按章节顺序排序
5. Planner Agent 调用 `create_study_plan` 创建计划项（含 `material_id`）
6. 返回成功消息，前端刷新计划列表

### Planner Agent 工具

#### get_material_node_list
- **功能**: 获取教材中未完成的课文节点列表
- **参数**: `material_id`, `student_id` (可选)
- **返回**: 按章节顺序排列的未完成节点列表
- **排序规则**: 先按父章节的 seq_num，再按自身 seq_num
- **过滤**: 只返回 Level 2 节点（有实际内容的课文），排除已完成节点

#### create_study_plan
- **功能**: 创建学习计划
- **参数**: `student_id`, `material_id`, `node_ids`, `start_date`, `sessions_per_week`
- **返回**: 创建成功的消息和计划项数量

### 五步学习完成状态同步
- 五步学习完成后，`guided_learning.py` 会自动更新 `PlanItem.status = COMPLETED`
- 同时记录 `completed_at` 时间戳

### 物料上传限制
- PDF 文件最大限制: 200MB
- 配置文件: `backend/app/routers/materials.py` 中的 `MAX_FILE_SIZE`

### 物料解析与缓存机制

#### PDF 解析流程

系统支持自动检测 PDF 类型并选择最佳解析方式：

```
1. PyPDF2 (文本PDF，最快)
   ↓ 失败（平均文字 < 100 字符）
2. PyMuPDF (文本PDF备选)
   ↓ 失败
3. EasyOCR (扫描PDF，免费深度学习OCR)
   ↓ 失败
4. LLM OCR (最后手段，昂贵)
```

#### OCR 缓存机制

系统为扫描版 PDF 提供缓存机制，避免重复 OCR 耗时：

- **缓存位置**: `backend/cache/page_cache/{pdf_hash}.json`
- **缓存内容**: 526 页 OCR 文本 + tokens
- **首次上传**: 运行 EasyOCR（~36 分钟）+ 保存缓存
- **失败后重试**: 从缓存加载（0 秒），节省大量时间
- **清理时机**: 教材解析完成被人激活后自动清除

##### 缓存相关 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/materials/{id}/cache` | DELETE | 清除指定教材的 OCR 缓存 |

##### 使用示例

```bash
# 首次上传（会运行 EasyOCR + 保存缓存）
POST /api/materials/{id}/upload
# → 处理失败

# 失败后重试（从缓存加载，0 秒）
POST /api/materials/{id}/upload
# → 节省 36 分钟！

# 手动清理缓存
DELETE /api/materials/{id}/cache
```

#### EasyOCR 集成

- **位置**: `backend/pageindex/utils.py`
- **模型**: `easyocr.Reader(['ch_sim', 'en'])`
- **GPU 支持**: 默认 CPU 模式（Windows 兼容性问题）
- **性能**: ~4 秒/页，526 页约 36 分钟

#### 依赖更新

`backend/requirements.txt` 新增依赖：

```
easyocr==1.7.2
torch==2.10.0
torchvision==0.25.0
opencv-python-headless==4.13.0.92
scikit-image==0.26.0
```
