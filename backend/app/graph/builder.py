"""
Graph builder — wires the nodes into a workflow.

This is where we define the FLOWCHART:
  START → classify_intent → (teach | give_hint | review_code) → END

LangGraph concepts used here:
- StateGraph: the flowchart container
- add_node: registers a function as a step in the flowchart
- add_edge: connects two steps with an arrow (A always goes to B)
- add_conditional_edges: connects one step to MULTIPLE possible next steps
                         based on a routing function
- compile: locks the graph and makes it ready to run
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import classify_intent, give_hint, review_code, teach
from app.graph.state import TutorState


def route_by_intent(state: TutorState) -> str:
    """Routing function — decides which node runs next.

    Called after classify_intent. Reads the 'intent' from state
    and returns the name of the next node to run.

    Returns:
        "teach", "give_hint", or "review_code"
    """
    intent = state.get("intent", "teach")

    if intent == "hint":
        return "give_hint"
    elif intent == "review":
        return "review_code"
    else:
        return "teach"


def build_tutor_graph():
    """Build and compile the AI tutor workflow.

    The graph looks like this:

        START
          ↓
        classify_intent  (figures out what the user wants)
          ↓
        route_by_intent  (picks the right handler)
         ╱    │     ╲
      teach  hint  review  (specialist nodes)
         ╲    │     ╱
          ↓   ↓    ↓
          END

    Returns:
        A compiled LangGraph that can be invoked with .ainvoke()
    """
    # Create the graph with our state definition
    graph = StateGraph(TutorState)

    # --- Register nodes ---
    # Each node is a function that takes state and returns updates
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("teach", teach)
    graph.add_node("give_hint", give_hint)
    graph.add_node("review_code", review_code)

    # --- Wire the edges ---

    # Step 1: START always goes to classify_intent
    graph.add_edge(START, "classify_intent")

    # Step 2: After classify_intent, ROUTE to the right handler
    # This is a conditional edge — the routing function decides where to go
    graph.add_conditional_edges(
        "classify_intent",    # Source node
        route_by_intent,      # Function that picks the next node
        {
            # Mapping: function return value → node name
            "teach": "teach",
            "give_hint": "give_hint",
            "review_code": "review_code",
        },
    )

    # Step 3: All specialist nodes go to END
    graph.add_edge("teach", END)
    graph.add_edge("give_hint", END)
    graph.add_edge("review_code", END)

    # --- Compile with memory ---
    # MemorySaver keeps conversation history in memory (lost on restart).
    # Good for development. In production, we'll use SqliteSaver/PostgresSaver.
    memory = MemorySaver()
    compiled_graph = graph.compile(checkpointer=memory)

    return compiled_graph


# Create a single instance of the graph to be used across the app
tutor_graph = build_tutor_graph()
