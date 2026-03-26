# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TreeEdu Agent (智慧教育平台) is a full-stack educational AI platform. The backend is FastAPI (Python) with a LangGraph multi-agent system. The frontend is React 19 + TypeScript + Vite.

## Build/Lint/Test Commands

### Backend (from `backend/` directory)

```bash
# Development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest
pytest test_integration.py
pytest test_integration.py::test_full_pipeline  # single test
pytest -v test_integration.py

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Frontend (from `frontend/` directory)

```bash
npm run dev      # Start Vite dev server
npm run build    # Production build
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Docker

```bash
docker-compose up --build
docker-compose down
```

## High-Level Architecture

### Multi-Agent System (LangGraph)

The agent system is in `backend/app/agent/` and uses a **supervisor pattern** with conditional routing:

```
START → supervisor → tutor | assessor | planner | variant | reporter
                            ↓
                         tools ←→ agents → END
```

- **Supervisor**: Routes to appropriate agent based on intent
- **Tutor**: Socratic teaching with 5-step guided learning
- **Assessor**: Evaluates student answers
- **Planner**: Creates study plans
- **Variant**: Generates question variants
- **Reporter**: Generates learning reports

Session state is persisted via `MemorySaver` checkpointer.

### 5-Step Guided Learning State Machine

Each knowledge node learning follows this progression (tracked in `LessonProgress`):

```
IMPORT → EXPLAIN → EXAMPLE → PRACTICE → SUMMARY → COMPLETED
```

On completion, `guided_learning.py` updates `StudentNodeState.health_score` and unlocks the next node.

### Multi-Model LLM Strategy

LLM model selection by task complexity (`backend/app/utils/llm_router.py`):

| Tier | Model | Use Cases |
|------|-------|-----------|
| `fast` | qwen-plus | Intent routing, simple tasks |
| `medium` | qwen-turbo | Example generation, summaries |
| `heavy` | qwen-max-latest | Deep reasoning, Socratic teaching, assessment |
| `vision` | qwen-vl-max-latest | OCR tasks |

### Memory Overlay Pattern

Student learning profile is aggregated from `StudentNodeState` and `StudentMistake` tables, then injected into agent prompts as "Expert Preference" for personalized tutoring. See `backend/app/services/memory_overlay.py`.

### Frontend SSE Streaming

`frontend/src/hooks/useSSE.ts` uses `@microsoft/fetch-event-source`. Event types: `token` | `node` | `tool` | `done` | `error`. Uses `AbortController` for cancellation.

### Axios Interceptor Pattern

`frontend/src/api/client.ts` sets up interceptors:
- **Request**: Injects `Authorization: Bearer {token}` from `useAuthStore.getState().token`
- **Response 401**: Calls `logout()` and redirects to `/login`

### PDF Parsing Cascade

`backend/app/services/tree_builder.py` tries parsers in order:
```
PyPDF2 (fast) → PyMuPDF → EasyOCR (~4s/page) → LLM OCR (expensive)
```

EasyOCR results are cached to `backend/cache/page_cache/{pdf_hash}.json` for reuse.

## Key File Locations

### Backend
| Purpose | File |
|---------|------|
| FastAPI entry | `backend/app/main.py` |
| Config (env vars) | `backend/app/config.py` |
| Database connection | `backend/app/database.py` |
| Agent graph definition | `backend/app/agent/graph.py` |
| Agent state types | `backend/app/agent/state.py` |
| Guided learning service | `backend/app/services/guided_learning.py` |
| Memory overlay | `backend/app/services/memory_overlay.py` |
| Quiz generation | `backend/app/services/quiz_generator.py` |
| Tree builder (PDF parsing) | `backend/app/services/tree_builder.py` |
| LLM router | `backend/app/utils/llm_router.py` |

### Frontend
| Purpose | File |
|---------|------|
| App routing | `frontend/src/App.tsx` |
| API client | `frontend/src/api/client.ts` |
| SSE hook | `frontend/src/hooks/useSSE.ts` |
| Auth store | `frontend/src/stores/useAuthStore.ts` |
| Lesson store | `frontend/src/stores/useLessonStore.ts` |
| Chat store | `frontend/src/stores/useChatStore.ts` |
| Main layout | `frontend/src/components/layout/MainLayout.tsx` |

## Database

SQLite (`treeedu.db`) with async SQLAlchemy 2.0. Models are in `backend/app/models/`. Alembic migrations in `backend/alembic/versions/`.

## Environment Setup

Copy `backend/.env.example` to `backend/.env` and configure at minimum one LLM API key (OpenAI, Gemini, DeepSeek, or Aliyun).

## No-Comments Policy

Do NOT add comments to code unless explicitly requested. The codebase follows a no-comments convention.
