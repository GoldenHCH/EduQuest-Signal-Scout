"""LangGraph node implementations for the evaluator."""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from graphs.state import (
    ClassificationResult,
    EvaluatorState,
    ScoreBreakdown,
    ScoringResult,
    SignalRecord,
)
from src.config import settings
from src.llm import invoke_llm_json

# Load prompts
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from file."""
    return (PROMPTS_DIR / name).read_text()


# Thresholds
CONFIDENCE_THRESHOLD = settings.confidence_threshold
SCORE_THRESHOLD = settings.score_threshold


def classify_node(state: EvaluatorState) -> dict[str, Any]:
    """Classify the chunk's intent using LLM.

    This node calls the LLM with the classification prompt and expects
    a JSON response with category, confidence, evidence_snippet, and rationale.

    Args:
        state: Current evaluator state containing the chunk.

    Returns:
        Partial state update with classification result or errors.
    """
    try:
        chunk = state["chunk"]
        prompt_template = _load_prompt("classify_prompt.txt")
        prompt = prompt_template.format(text=chunk["text"])

        logger.debug(f"Classifying chunk: {chunk['chunk_id']}")
        result = invoke_llm_json(prompt)

        # Validate required fields
        required_fields = ["category", "confidence", "evidence_snippet", "rationale"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field in classification: {field}")

        classification: ClassificationResult = {
            "category": result["category"],
            "confidence": float(result["confidence"]),
            "evidence_snippet": result["evidence_snippet"],
            "rationale": result["rationale"],
        }

        logger.info(
            f"Classified {chunk['chunk_id']}: "
            f"category={classification['category']}, "
            f"confidence={classification['confidence']:.2f}"
        )

        return {"classification": classification}

    except Exception as e:
        logger.error(f"Classification failed for {state['chunk']['chunk_id']}: {e}")
        return {"errors": state.get("errors", []) + [f"classify_node: {str(e)}"]}


def evidence_validation_node(state: EvaluatorState) -> dict[str, Any]:
    """Validate that evidence_snippet is an exact substring of chunk text.

    This is a critical validation step to ensure the LLM didn't hallucinate
    or paraphrase the evidence.

    Args:
        state: Current evaluator state with classification.

    Returns:
        Partial state update. Sets keep=False if validation fails.
    """
    classification = state.get("classification")
    if not classification:
        return {
            "errors": state.get("errors", []) + ["No classification to validate"],
            "keep": False,
        }

    snippet = classification["evidence_snippet"]
    chunk_text = state["chunk"]["text"]

    # Check for exact substring match
    if snippet not in chunk_text:
        logger.warning(
            f"Evidence validation failed for {state['chunk']['chunk_id']}: "
            f"snippet not found in chunk text"
        )
        return {
            "errors": state.get("errors", [])
            + ["Evidence snippet not found verbatim in chunk text"],
            "keep": False,
        }

    logger.debug(f"Evidence validated for {state['chunk']['chunk_id']}")
    return {}  # Validation passed, no state change needed


def score_node(state: EvaluatorState) -> dict[str, Any]:
    """Score the opportunity based on classification.

    This node is only called if classification passed validation and
    meets the confidence threshold.

    Args:
        state: Current evaluator state with classification.

    Returns:
        Partial state update with scoring result or errors.
    """
    try:
        classification = state["classification"]
        chunk = state["chunk"]

        prompt_template = _load_prompt("scoring_prompt.txt")
        prompt = prompt_template.format(
            district=chunk["district"],
            meeting_date=chunk.get("meeting_date") or "Unknown",
            category=classification["category"],
            confidence=classification["confidence"],
            evidence=classification["evidence_snippet"],
            rationale=classification["rationale"],
        )

        logger.debug(f"Scoring chunk: {chunk['chunk_id']}")
        result = invoke_llm_json(prompt)

        # Validate and construct scoring result
        score_breakdown: ScoreBreakdown = {
            "intent_strength": int(result.get("score_breakdown", {}).get("intent_strength", 0)),
            "time_window": int(result.get("score_breakdown", {}).get("time_window", 0)),
            "eduquest_fit": int(result.get("score_breakdown", {}).get("eduquest_fit", 0)),
            "evidence_quality": int(result.get("score_breakdown", {}).get("evidence_quality", 0)),
        }

        scoring: ScoringResult = {
            "opportunity_score": int(result["opportunity_score"]),
            "score_breakdown": score_breakdown,
            "summary": result["summary"],
            "recommended_next_step": result["recommended_next_step"],
        }

        logger.info(
            f"Scored {chunk['chunk_id']}: "
            f"score={scoring['opportunity_score']}, "
            f"next_step={scoring['recommended_next_step']}"
        )

        return {"scoring": scoring}

    except Exception as e:
        logger.error(f"Scoring failed for {state['chunk']['chunk_id']}: {e}")
        return {"errors": state.get("errors", []) + [f"score_node: {str(e)}"]}


def normalize_node(state: EvaluatorState) -> dict[str, Any]:
    """Create a normalized signal record for export.

    This node consolidates all data into a final signal record format.

    Args:
        state: Current evaluator state with classification and scoring.

    Returns:
        Partial state update with signal_record and keep=True.
    """
    chunk = state["chunk"]
    classification = state["classification"]
    scoring = state["scoring"]

    signal_record: SignalRecord = {
        "chunk_id": chunk["chunk_id"],
        "artifact_id": chunk["artifact_id"],
        "district": chunk["district"],
        "meeting_date": chunk.get("meeting_date"),
        "source_url": chunk["source_url"],
        "board_page_url": chunk.get("board_page_url", ""),
        "category": classification["category"],
        "confidence": classification["confidence"],
        "opportunity_score": scoring["opportunity_score"],
        "evidence_snippet": classification["evidence_snippet"],
        "summary": scoring["summary"],
        "recommended_next_step": scoring["recommended_next_step"],
        "rationale": classification["rationale"],
        "generated_at": datetime.now().isoformat(),
    }

    logger.info(f"Normalized signal for {chunk['chunk_id']}")

    return {"signal_record": signal_record, "keep": True}


def drop_node(state: EvaluatorState) -> dict[str, Any]:
    """Mark the chunk as not kept (dropped).

    Args:
        state: Current evaluator state.

    Returns:
        Partial state update with keep=False.
    """
    logger.debug(f"Dropping chunk: {state['chunk']['chunk_id']}")
    return {"keep": False}


def error_handler_node(state: EvaluatorState) -> dict[str, Any]:
    """Handle errors by marking chunk as not kept.

    Args:
        state: Current evaluator state.

    Returns:
        Partial state update with keep=False.
    """
    errors = state.get("errors", [])
    logger.warning(
        f"Error handler for {state['chunk']['chunk_id']}: "
        f"{len(errors)} error(s) - {errors}"
    )
    return {"keep": False}


# Router functions


def decision_router(state: EvaluatorState) -> str:
    """Route based on classification results.

    Called after evidence validation to decide next step.

    Args:
        state: Current evaluator state.

    Returns:
        Next node name: "score", "drop", or "error_handler".
    """
    # Check for errors
    if state.get("errors"):
        return "error_handler"

    # Check classification exists
    classification = state.get("classification")
    if not classification:
        return "error_handler"

    # Check category
    if classification["category"] == "none":
        logger.debug(f"Dropping {state['chunk']['chunk_id']}: category=none")
        return "drop"

    # Check confidence threshold
    if classification["confidence"] < CONFIDENCE_THRESHOLD:
        logger.debug(
            f"Dropping {state['chunk']['chunk_id']}: "
            f"confidence={classification['confidence']:.2f} < {CONFIDENCE_THRESHOLD}"
        )
        return "drop"

    return "score"


def final_decision_router(state: EvaluatorState) -> str:
    """Final routing after scoring.

    Decides whether to normalize (keep) or drop based on score.

    Args:
        state: Current evaluator state.

    Returns:
        Next node name: "normalize", "drop", or "error_handler".
    """
    # Check for errors
    if state.get("errors"):
        return "error_handler"

    # Check scoring exists
    scoring = state.get("scoring")
    if not scoring:
        return "error_handler"

    # Check score threshold (or reach_out_now recommendation)
    if (
        scoring["opportunity_score"] >= SCORE_THRESHOLD
        or scoring["recommended_next_step"] == "reach_out_now"
    ):
        return "normalize"

    logger.debug(
        f"Dropping {state['chunk']['chunk_id']}: "
        f"score={scoring['opportunity_score']} < {SCORE_THRESHOLD}"
    )
    return "drop"
