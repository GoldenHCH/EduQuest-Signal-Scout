"""LangGraph evaluator graph definition.

This module defines the main evaluation graph that processes chunks through:
1. Classification - Identify intent category and extract evidence
2. Evidence Validation - Verify evidence is exact substring
3. Scoring - Score opportunity (conditional on classification)
4. Normalization - Create export-ready signal record
5. Decision - Keep or drop based on score

Graph structure:
    START → classify → validate_evidence → [decision_router]
                                              ├─ score → [final_decision_router]
                                              │            ├─ normalize → END
                                              │            ├─ drop → END
                                              │            └─ error_handler → END
                                              ├─ drop → END
                                              └─ error_handler → END
"""

from langgraph.graph import END, START, StateGraph
from loguru import logger

from graphs.nodes import (
    classify_node,
    decision_router,
    drop_node,
    error_handler_node,
    evidence_validation_node,
    final_decision_router,
    normalize_node,
    score_node,
)
from graphs.state import ChunkData, EvaluatorState


def build_evaluator_graph() -> StateGraph:
    """Build and compile the evaluator graph.

    Returns:
        Compiled LangGraph StateGraph ready for invocation.
    """
    logger.info("Building evaluator graph...")

    # Initialize graph with state schema
    graph = StateGraph(EvaluatorState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("validate_evidence", evidence_validation_node)
    graph.add_node("score", score_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("drop", drop_node)
    graph.add_node("error_handler", error_handler_node)

    # Add edges

    # START -> classify
    graph.add_edge(START, "classify")

    # classify -> validate_evidence
    graph.add_edge("classify", "validate_evidence")

    # validate_evidence -> decision_router (conditional)
    graph.add_conditional_edges(
        "validate_evidence",
        decision_router,
        {
            "score": "score",
            "drop": "drop",
            "error_handler": "error_handler",
        },
    )

    # score -> final_decision_router (conditional)
    graph.add_conditional_edges(
        "score",
        final_decision_router,
        {
            "normalize": "normalize",
            "drop": "drop",
            "error_handler": "error_handler",
        },
    )

    # Terminal edges -> END
    graph.add_edge("normalize", END)
    graph.add_edge("drop", END)
    graph.add_edge("error_handler", END)

    # Compile the graph
    compiled = graph.compile()
    logger.info("Evaluator graph compiled successfully")

    return compiled


# Create singleton instance
evaluator_graph = build_evaluator_graph()


def evaluate_chunk(chunk: ChunkData) -> EvaluatorState:
    """Evaluate a single chunk through the graph.

    Args:
        chunk: The chunk data to evaluate.

    Returns:
        Final evaluator state after graph execution.
    """
    initial_state: EvaluatorState = {
        "chunk": chunk,
        "errors": [],
        "keep": False,
    }

    logger.debug(f"Evaluating chunk: {chunk['chunk_id']}")
    final_state = evaluator_graph.invoke(initial_state)

    return final_state


def evaluate_chunks(chunks: list[ChunkData]) -> list[dict]:
    """Evaluate multiple chunks and return kept signals.

    Args:
        chunks: List of chunk data to evaluate.

    Returns:
        List of signal records for chunks that were kept.
    """
    signals = []
    total = len(chunks)

    logger.info(f"Starting evaluation of {total} chunks...")

    for i, chunk in enumerate(chunks, 1):
        try:
            final_state = evaluate_chunk(chunk)

            if final_state.get("keep") and final_state.get("signal_record"):
                signals.append(final_state["signal_record"])
                logger.info(
                    f"[{i}/{total}] KEPT: {chunk['chunk_id']} "
                    f"(score={final_state['signal_record']['opportunity_score']})"
                )
            else:
                logger.debug(f"[{i}/{total}] DROPPED: {chunk['chunk_id']}")

        except Exception as e:
            logger.error(f"[{i}/{total}] ERROR: {chunk['chunk_id']} - {e}")

    logger.info(f"Evaluation complete: {len(signals)}/{total} signals kept")
    return signals
