"""LangGraph state definitions for the evaluator."""

from typing import Literal, TypedDict

from typing_extensions import NotRequired

# Intent categories for classification
IntentCategory = Literal[
    "curriculum_adoption",
    "instructional_materials",
    "pilot_evaluation",
    "budget_allocation",
    "vendor_dissatisfaction",
    "learning_gaps",
    "personalization_pbl",
    "strategic_plan",
    "teacher_workload",
    "none",
]

# Recommended next steps
NextStep = Literal["reach_out_now", "research_more", "monitor"]


class ChunkData(TypedDict):
    """Data for a single text chunk from a board meeting document."""

    artifact_id: str
    chunk_id: str
    district: str
    meeting_date: str | None
    source_url: str
    board_page_url: str
    text: str


class ClassificationResult(TypedDict):
    """Result from the classification node."""

    category: IntentCategory
    confidence: float
    evidence_snippet: str
    rationale: str


class ScoreBreakdown(TypedDict):
    """Breakdown of opportunity score components."""

    intent_strength: int
    time_window: int
    eduquest_fit: int
    evidence_quality: int


class ScoringResult(TypedDict):
    """Result from the scoring node."""

    opportunity_score: int
    score_breakdown: ScoreBreakdown
    summary: str
    recommended_next_step: NextStep


class SignalRecord(TypedDict):
    """Final normalized signal record for export."""

    chunk_id: str
    artifact_id: str
    district: str
    meeting_date: str | None
    source_url: str
    board_page_url: str
    category: IntentCategory
    confidence: float
    opportunity_score: int
    evidence_snippet: str
    summary: str
    recommended_next_step: NextStep
    rationale: str
    generated_at: str


class EvaluatorState(TypedDict):
    """Main state for the LangGraph evaluator.

    This state flows through the graph, accumulating results from each node.
    Nodes return partial updates that are merged into the state.
    """

    # Input chunk data
    chunk: ChunkData

    # Classification result (set by classify_node)
    classification: NotRequired[ClassificationResult]

    # Scoring result (set by score_node)
    scoring: NotRequired[ScoringResult]

    # Error tracking
    errors: list[str]

    # Final decision: whether to keep this signal
    keep: bool

    # Normalized signal record for export (set by normalize_node)
    signal_record: NotRequired[SignalRecord]
