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
        "messages": [HumanMessage(content=request.message)]
    }
    
    config = {"configurable": {"thread_id": session_id}}
    
    # Collect the final response by streaming through all nodes
    final_content = ""
    tool_calls_made = []
    
    try:
        async for event in treeedu_graph.astream(agent_input, config=config):
            for node_name, values in event.items():
                if "messages" in values:
                    last_msg = values["messages"][-1]
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            tool_calls_made.append(tc.get("name", "unknown"))
                    elif hasattr(last_msg, 'content') and last_msg.content:
                        # Keep track of the last non-empty content (final answer)
                        if node_name in ("tutor", "assessor"):
                            final_content = last_msg.content
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
        
        session_list.append(ChatSessionInfo(
            id=s.id,
            student_id=s.student_id,
            session_type=s.session_type.value if s.session_type else "SOCRATIC_QA",
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=msg_count,
        ))
    
    return ChatSessionListResponse(sessions=session_list, total=len(session_list))


@router.post("/stream")
async def stream_message(request: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
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
        "messages": [HumanMessage(content=request.message)]
    }
    config = {"configurable": {"thread_id": session_id}}

    import asyncio
    async def event_generator():
        final_content = ""
        tool_calls_made = []
        
        try:
            stream = treeedu_graph.astream(agent_input, config=config)
            while True:
                try:
                    event = await asyncio.wait_for(stream.__anext__(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                except StopAsyncIteration:
                    break
                    
                for node_name, values in event.items():
                    # Emit node event
                    yield f"event: node\ndata: {json.dumps({'node': node_name})}\n\n"
                    
                    if "messages" in values:
                        last_msg = values["messages"][-1]
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                tool_name = tc.get("name", "unknown")
                                tool_calls_made.append(tool_name)
                                yield f"event: tool\ndata: {json.dumps({'tool': tool_name, 'node': node_name})}\n\n"
                        elif hasattr(last_msg, 'content') and last_msg.content:
                            if node_name in ("tutor", "assessor"):
                                final_content = last_msg.content
                                yield f"event: token\ndata: {json.dumps({'content': last_msg.content, 'role': node_name.upper()})}\n\n"
            
            # Save agent response to DB
            if final_content:
                agent_msg = ChatMessage(
                    session_id=session_id,
                    sender=SenderRole.TUTOR_AGENT,
                    content_md=final_content,
                )
                db.add(agent_msg)
                await db.commit()
            
            # Emit done event
            yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'tool_calls': tool_calls_made})}\n\n"
            
        except Exception as e:
            logger.exception(f"SSE stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
