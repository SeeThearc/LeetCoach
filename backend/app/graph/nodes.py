"""
Node functions — the actual AI logic.

Each function here is a "node" in our LangGraph workflow.
Every node:
  1. Receives the full state (TutorState)
  2. Does its job (usually calls Google Gemini)
  3. Returns a dict with ONLY the fields it wants to update

Example: classify_intent reads the latest message, asks Gemini to classify it,
and returns {"intent": "hint"} — this updates ONLY the intent field in state.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph.prompts import (
    CLASSIFY_INTENT_PROMPT,
    CODE_REVIEW_SYSTEM_PROMPT,
    HINT_SYSTEM_PROMPT,
    TUTOR_SYSTEM_PROMPT,
)
from app.graph.state import TutorState

logger = get_logger(__name__)


def _to_str(content) -> str:
    """Safely convert LLM response content to a string.

    Google Gemini returns content in different formats:
    - A plain string: "hello"
    - A list of dicts: [{"type": "text", "text": "hello", "extras": {...}}]
    This handles all cases and extracts just the text.
    """
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return " ".join(parts)
    return str(content)


def _get_llm() -> ChatGoogleGenerativeAI:
    """Create a Google Gemini LLM instance.

    Called inside each node so the API key is read from settings
    at runtime (not at import time).
    """
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.7,  # Slightly creative but not too random
    )


def _get_problem_context(state: TutorState) -> dict:
    """Extract problem info from state for use in prompts.

    Returns a dict with title, difficulty, tags, content, language, user_code
    that can be used to fill in prompt template placeholders.
    """
    problem = state.get("problem", {})
    # Extract topic tag names from the tags list
    tags_list = problem.get("topicTags", [])
    tag_names = ", ".join(tag.get("name", "") for tag in tags_list) if tags_list else "Unknown"

    return {
        "title": problem.get("title", "Unknown"),
        "difficulty": problem.get("difficulty", "Unknown"),
        "tags": tag_names,
        "content": problem.get("content", "No description available"),
        "language": state.get("language", "python"),
        "user_code": state.get("user_code", ""),
    }


# --------------------------------------------------------------------------
# Node 1: classify_intent
# Looks at the user's latest message and decides: teach, hint, or review
# --------------------------------------------------------------------------
async def classify_intent(state: TutorState) -> dict:
    """Figure out what the user wants.

    Reads the latest message, asks Gemini to classify it as
    'teach', 'hint', or 'review', and stores the result in state.

    Returns:
        {"intent": "teach" | "hint" | "review"}
    """
    llm = _get_llm()

    # Get the latest message from the user
    messages = state.get("messages", [])
    latest_message = messages[-1].content if messages else ""

    logger.info("Classifying intent", message_preview=latest_message[:80])

    # Ask Gemini to classify the intent
    response = await llm.ainvoke([
        SystemMessage(content=CLASSIFY_INTENT_PROMPT),
        HumanMessage(content=latest_message),
    ])

    # Parse the response — should be one word: teach, hint, or review
    intent = _to_str(response.content).strip().lower()

    # If the user shared code, assume they want a review
    user_code = state.get("user_code", "")
    if user_code and intent == "teach":
        intent = "review"

    # Default to 'teach' if we got something unexpected
    if intent not in ("teach", "hint", "review"):
        logger.warning("Unexpected intent from LLM", raw_intent=intent)
        intent = "teach"

    logger.info("Intent classified", intent=intent)
    return {"intent": intent}


# --------------------------------------------------------------------------
# Node 2: teach
# Explains concepts using the Socratic method — NEVER gives the answer
# --------------------------------------------------------------------------
async def teach(state: TutorState) -> dict:
    """Teach the student about the problem.

    Uses Socratic method — asks guiding questions, breaks down
    the problem, explains concepts. Never gives the full solution.

    Returns:
        {"messages": [AIMessage with the teaching response]}
    """
    llm = _get_llm()
    context = _get_problem_context(state)

    logger.info("Teaching", problem=context["title"])

    # Build the system prompt with problem context
    system_prompt = TUTOR_SYSTEM_PROMPT.format(**context)

    # Include conversation history so the AI knows what was already discussed
    chat_messages = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", []):
        chat_messages.append(msg)

    # Call Gemini
    response = await llm.ainvoke(chat_messages)

    logger.info("Teaching response generated", length=len(response.content))

    # Return the AI's response — it gets appended to messages automatically
    return {"messages": [response]}


# --------------------------------------------------------------------------
# Node 3: give_hint
# Gives progressively more detailed hints (level 1 → 2 → 3)
# --------------------------------------------------------------------------
async def give_hint(state: TutorState) -> dict:
    """Give a hint at the current level, then increment the level.

    Level 1: Gentle nudge ("Think about hash maps")
    Level 2: Approach ("Use a hash map to store seen values")
    Level 3: Near-solution ("For each num, check if target-num is in the map")

    Returns:
        {"messages": [AIMessage with the hint], "hint_level": incremented}
    """
    llm = _get_llm()
    context = _get_problem_context(state)

    # Get current hint level (0 means no hints given yet, start at 1)
    current_level = state.get("hint_level", 0) + 1
    # Cap at level 3
    if current_level > 3:
        current_level = 3

    context["hint_level"] = current_level

    logger.info("Generating hint", problem=context["title"], level=current_level)

    # Build the prompt with hint level
    system_prompt = HINT_SYSTEM_PROMPT.format(**context)

    chat_messages = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", []):
        chat_messages.append(msg)

    # Call Gemini
    response = await llm.ainvoke(chat_messages)

    logger.info("Hint generated", level=current_level)

    return {
        "messages": [response],
        "hint_level": current_level,  # Save the updated level
    }


# --------------------------------------------------------------------------
# Node 4: review_code
# Reviews the student's code without rewriting it
# --------------------------------------------------------------------------
async def review_code(state: TutorState) -> dict:
    """Review the student's code.

    Checks for correctness, edge cases, complexity, and style.
    Points out issues but doesn't rewrite the code.

    Returns:
        {"messages": [AIMessage with the review]}
    """
    llm = _get_llm()
    context = _get_problem_context(state)

    user_code = context["user_code"]

    logger.info("Reviewing code", problem=context["title"])

    # If no code was provided, ask the student to share it
    if not user_code:
        return {
            "messages": [AIMessage(
                content="I'd love to review your code! "
                        "Please share your current solution and I'll give you feedback."
            )]
        }

    # Build the review prompt with the student's code
    system_prompt = CODE_REVIEW_SYSTEM_PROMPT.format(**context)

    chat_messages = [SystemMessage(content=system_prompt)]
    for msg in state.get("messages", []):
        chat_messages.append(msg)

    # Call Gemini
    response = await llm.ainvoke(chat_messages)

    logger.info("Code review generated")

    return {"messages": [response]}
