"""
Chat Router - Handles student-agent conversation interactions.
This is the primary API endpoint for the Student Portal's chat interface.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage

from app.database import get_db
from app.agent.graph import treeedu_graph
from app.schemas.chat import (
    ChatMessageRequest,
    AgentMessageResponse,
    ChatSessionListResponse,
    ChatSessionInfo,
)
from app.models.chat import ChatSession, ChatMessage, SenderRole, SessionType
from app.services.memory_overlay import get_student_memory_overlay
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


def _extract_text_from_message(msg) -> str:
    """Extract text content from a message, filtering out thinking blocks (MiniMax)."""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
            elif hasattr(block, "type") and block.type == "text" and block.text:
                parts.append(block.text)
        return "".join(parts)
    return str(content) if content else ""


def _extract_text_from_chunk(chunk) -> str:
    """Extract text from a streaming chunk, filtering out thinking blocks."""
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
            elif hasattr(block, "type") and block.type == "text" and block.text:
                parts.append(block.text)
        return "".join(parts)
    return ""

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/send", response_model=AgentMessageResponse)
async def send_message(request: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
    """
    Send a message to the TreeEdu Agent and get a response.

    This endpoint:
    1. Creates or reuses a chat session
    2. Persists the student's message to DB
    3. Runs the LangGraph agent pipeline (Supervisor → Tutor → Assessor)
    4. Persists the agent's response to DB
    5. Returns the final agent response
    """
    # 1. Resolve session
    session_id = request.session_id or str(uuid.uuid4())

    # Check if session exists, create if not
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()

    if not session:
        session = ChatSession(
            id=session_id,
            student_id=request.student_id,
            session_type=SessionType.SOCRATIC_QA,
        )
        db.add(session)
        await db.flush()

    # 2. Save student message to DB
    student_msg = ChatMessage(
        session_id=session_id,
        sender=SenderRole.STUDENT,
        content_md=request.message,
    )
    db.add(student_msg)
    await db.commit()

    # 3. Run the LangGraph pipeline
    agent_input = {
        "session_id": session_id,
        "student_id": request.student_id,
        "material_id": request.material_id,
        "node_id": request.node_id,
        "lesson_step": request.lesson_step,
        "subject": None,  # 由 supervisor 从 material_id 派生
        "current_intent": request.intent or "chat",
        "messages": [HumanMessage(content=request.message)],
    }

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # Collect the final response by streaming through all nodes
    final_content = ""
    tool_calls_made = []

    try:
        async for event in treeedu_graph.astream(agent_input, config=config):
            for node_name, values in event.items():
                if "messages" in values:
                    last_msg = values["messages"][-1]
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            tool_calls_made.append(tc.get("name", "unknown"))
                    elif hasattr(last_msg, "content") and last_msg.content:
                        if node_name != "assessor":
                            final_content = _extract_text_from_message(last_msg)
    except Exception as e:
        logger.exception(f"Agent pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent processing error: {str(e)}")

    if not final_content:
        final_content = "抱歉，我现在无法回答这个问题。请稍后再试。"

    # 4. Save agent response to DB
    agent_msg = ChatMessage(
        session_id=session_id,
        sender=SenderRole.TUTOR_AGENT,
        content_md=final_content,
    )
    db.add(agent_msg)
    await db.commit()

    # 5. Get memory overlay for response metadata
    overlay = await get_student_memory_overlay(request.student_id, request.material_id)

    return AgentMessageResponse(
        session_id=session_id,
        role="TUTOR_AGENT",
        content=final_content,
        tool_calls_made=tool_calls_made if tool_calls_made else None,
        health_score=overlay["avg_health_score"],
        weak_nodes_count=len(overlay["weak_nodes"]),
    )


@router.get("/sessions/{student_id}", response_model=ChatSessionListResponse)
async def list_sessions(student_id: str, db: AsyncSession = Depends(get_db)):
    """List all chat sessions for a student."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.student_id == student_id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    session_list = []
    for s in sessions:
        # Count messages
        count_result = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == s.id)
        )
        msg_count = count_result.scalar() or 0

        session_list.append(
            ChatSessionInfo(
                id=s.id,
                student_id=s.student_id,
                session_type=s.session_type.value if s.session_type else "SOCRATIC_QA",
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=msg_count,
            )
        )

    return ChatSessionListResponse(sessions=session_list, total=len(session_list))


@router.post("/stream")
async def stream_message(
    request: ChatMessageRequest, db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the TreeEdu Agent and get a Server-Sent Events (SSE) stream.

    Events emitted:
    - event: node    — which agent node is executing (supervisor, tutor, assessor, tools)
    - event: tool    — a tool call was made (includes tool name)
    - event: token   — a text chunk from the agent response
    - event: done    — stream complete (includes session_id and final metadata)
    - event: error   — an error occurred
    """
    import json

    # 1. Resolve session
    session_id = request.session_id or str(uuid.uuid4())

    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()

    if not session:
        session = ChatSession(
            id=session_id,
            student_id=request.student_id,
            session_type=SessionType.SOCRATIC_QA,
        )
        db.add(session)
        await db.flush()

    # 2. Save student message
    student_msg = ChatMessage(
        session_id=session_id,
        sender=SenderRole.STUDENT,
        content_md=request.message,
    )
    db.add(student_msg)
    await db.commit()

    # 3. Prepare graph input
    agent_input = {
        "session_id": session_id,
        "student_id": request.student_id,
        "material_id": request.material_id,
        "node_id": request.node_id,
        "lesson_step": request.lesson_step,
        "subject": None,  # 由 supervisor 从 material_id 派生
        "current_intent": request.intent or "chat",
        "messages": [HumanMessage(content=request.message)],
    }
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    import asyncio

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def _run_agent():
            """Run LangGraph pipeline with token-level streaming via astream_events."""
            final_content = ""
            seen_nodes = set()
            try:
                async for event in treeedu_graph.astream_events(
                    agent_input, config=config, version="v2"
                ):
                    event_type = event.get("event", "")
                    data = event.get("data", {})
                    metadata = event.get("metadata", {})
                    node_name = metadata.get("langgraph_node", "")

                    if node_name and node_name not in seen_nodes:
                        seen_nodes.add(node_name)
                        await queue.put({"type": "node", "node": node_name})

                    if event_type == "on_chat_model_stream":
                        if node_name in ("import", "explain", "example", "practice", "summary"):
                            chunk = data.get("chunk")
                            if chunk and hasattr(chunk, "content"):
                                text = _extract_text_from_chunk(chunk)
                                if text:
                                    await queue.put({
                                        "type": "token",
                                        "content": text,
                                        "role": node_name.upper(),
                                    })

                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        await queue.put({
                            "type": "tool",
                            "tool": tool_name,
                            "node": node_name,
                        })

                    if event_type == "on_chain_end" and node_name in ("import", "explain", "example", "practice", "summary"):
                        output = data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            msgs = output["messages"]
                            if msgs:
                                last = msgs[-1]
                                if hasattr(last, "content") and not getattr(last, "tool_calls", None):
                                    final_content = _extract_text_from_message(last)

                await queue.put({"type": "_done", "final_content": final_content})
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(f"Agent background task error: {e}")
                await queue.put({"type": "_error", "error": str(e)})
            finally:
                if final_content:
                    try:
                        from app.database import AsyncSessionLocal
                        async with AsyncSessionLocal() as bg_db:
                            bg_db.add(ChatMessage(
                                session_id=session_id,
                                sender=SenderRole.TUTOR_AGENT,
                                content_md=final_content,
                            ))
                            await bg_db.commit()
                    except Exception:
                        logger.exception("Failed to save agent response in background")

        agent_task = asyncio.create_task(_run_agent())

        try:
            yield ": connected\n\n"

            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                if item["type"] == "_done":
                    break
                if item["type"] == "_error":
                    yield f"event: error\ndata: {json.dumps({'error': item['error']})}\n\n"
                    break
                if item["type"] == "node":
                    yield f"event: node\ndata: {json.dumps({'node': item['node']})}\n\n"
                elif item["type"] == "tool":
                    yield f"event: tool\ndata: {json.dumps({'tool': item['tool'], 'node': item['node']})}\n\n"
                elif item["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'content': item['content'], 'role': item['role']})}\n\n"

            yield f"event: done\ndata: {json.dumps({'session_id': session_id})}\n\n"

        except asyncio.CancelledError:
            agent_task.cancel()
            logger.info(f"SSE stream cancelled by client for session {session_id}, agent task cancelled")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
