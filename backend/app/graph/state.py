"""
State = the shared data bag that every node in our AI workflow can read and update.

Think of it like a form being passed between departments:
- Classify Intent fills in the "intent" field
- Hint Generator reads "hint_level" and increments it
- All nodes can read "problem" to know what problem we're helping with

The 'messages' field is special:
- It uses 'add_messages' which means new messages get APPENDED (not replaced)
- This is how conversation history is maintained automatically
- When a node returns {"messages": [new_ai_message]}, it gets added to the list
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class TutorState(TypedDict):
    """All the data that flows through our AI tutor workflow.

    Fields:
        messages:   Conversation history (human + AI messages).
                    Uses add_messages so new messages append automatically.

        problem:    Problem data from the LeetCode API. A dict like:
                    {"title": "Two Sum", "difficulty": "Easy", "content": "...", ...}

        language:   Programming language the user is working in.
                    Example: "python", "javascript", "cpp"

        user_code:  The user's current code (if they shared it).
                    Empty string if no code was shared.

        intent:     What the user wants. Set by the classify_intent node.
                    One of: "teach", "hint", "review"

        hint_level: Tracks how many hints we've given (0, 1, 2, 3).
                    Level 1 = gentle nudge
                    Level 2 = general approach
                    Level 3 = near-solution
    """

    messages: Annotated[list, add_messages]
    problem: dict
    language: str
    user_code: str
    intent: str
    hint_level: int
