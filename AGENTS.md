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
│   │   ├── utils/          # Utility functions
│   │   ├── config.py       # Settings and configuration
│   │   ├── database.py     # DB connection and session
│   │   └── main.py         # FastAPI app entry point
│   ├── alembic/            # Database migrations
│   ├── test_*.py           # Test files
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/            # API client functions
│   │   ├── components/     # Reusable React components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── pages/          # Page-level components
│   │   ├── stores/         # Zustand state stores
│   │   ├── styles/         # Global styles
│   │   ├── types/          # TypeScript type definitions
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
