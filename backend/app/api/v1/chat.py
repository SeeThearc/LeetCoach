"""
Chat endpoint — the main API the Chrome Extension talks to.

Flow:
1. Extension sends: message + problem_slug + session_id
2. We fetch problem data from LeetCode API
3. We run the LangGraph tutor workflow
4. We return the AI's response

The session_id enables conversation continuity:
- Same session_id = same conversation thread (AI remembers context)
- New session_id = fresh conversation
- LangGraph's checkpointer handles this automatically via thread_id
"""

import uuid

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.core.exceptions import AIError
from app.core.logging import get_logger
from app.graph.builder import tutor_graph
from app.services.leetcode import fetch_problem

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# --------------------------------------------------------------------------
# Request & Response schemas (kept here since they're only used in this file)
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """What the Chrome Extension sends us."""

    message: str = Field(
        ...,  # ... means this is Required
        min_length=1,
        description="The student's message",
        examples=["I'm stuck on Two Sum, can you help?"],
    )
    problem_slug: str = Field(
        ...,
        description="LeetCode problem slug or ID",
        examples=["two-sum", "1"],
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Conversation session ID. Same ID = same conversation thread.",
    )
    language: str = Field(
        default="cpp",
        description="Programming language the student is using",
        examples=["python", "javascript", "cpp", "java"],
    )
    user_code: str = Field(
        default="",
        description="Student's current code (optional, for code review)",
    )


class ChatResponse(BaseModel):
    """What we send back to the Chrome Extension."""

    response: str = Field(description="The AI tutor's response")
    intent: str = Field(description="Classified intent: teach, hint, or review")
    hint_level: int = Field(description="Current hint level (0-3)")
    session_id: str = Field(description="Session ID for continuing this conversation")
    problem_title: str = Field(description="Title of the problem being discussed")


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Main chat endpoint.

    The Chrome Extension calls this with the student's message.
    We fetch the problem, run the AI tutor, and return the response.

    The session_id keeps conversations going — send the same session_id
    to continue a conversation, or a new one to start fresh.
    """
    logger.info(
        "Chat request received",
        problem=request.problem_slug,
        session_id=request.session_id[:8],  # Log just first 8 chars
    )

    # Step 1: Fetch problem data from LeetCode API
    problem = await fetch_problem(request.problem_slug)

    # Step 2: Run the LangGraph tutor workflow
    try:
        result = await tutor_graph.ainvoke(
            # Input state — only include what comes from the user
            # hint_level and intent are managed by the graph internally
            {
                "messages": [HumanMessage(content=request.message)],
                "problem": problem,
                "language": request.language,
                "user_code": request.user_code,
            },
            # Config — thread_id enables conversation memory
            config={"configurable": {"thread_id": request.session_id}},
        )
    except Exception as e:
        logger.error("LangGraph execution failed", error=str(e))
        raise AIError(f"AI processing failed: {str(e)}")

    # Step 3: Extract the AI's response (last message in the list)
    ai_response = result["messages"][-1].content

    logger.info(
        "Chat response generated",
        intent=result.get("intent", "unknown"),
        response_length=len(ai_response),
    )

    return ChatResponse(
        response=ai_response,
        intent=result.get("intent", "teach"),
        hint_level=result.get("hint_level", 0),
        session_id=request.session_id,
        problem_title=problem.get("title", "Unknown"),
    )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str) -> dict:
    """Get conversation history for a session.

    Reads the stored messages from LangGraph's checkpointer.
    Useful for restoring a conversation when the side panel reopens.
    """
    try:
        # Get the latest state from the checkpointer
        state = await tutor_graph.aget_state(
            config={"configurable": {"thread_id": session_id}},
        )

        if not state.values:
            return {"session_id": session_id, "messages": []}

        # Convert LangChain messages to simple dicts
        messages = []
        for msg in state.values.get("messages", []):
            messages.append({
                "role": "user" if msg.type == "human" else "assistant",
                "content": msg.content,
            })

        return {
            "session_id": session_id,
            "messages": messages,
            "hint_level": state.values.get("hint_level", 0),
            "problem_title": state.values.get("problem", {}).get("title", ""),
        }

    except Exception as e:
        logger.error("Failed to get history", error=str(e))
        return {"session_id": session_id, "messages": []}
