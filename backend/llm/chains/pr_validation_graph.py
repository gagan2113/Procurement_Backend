"""
LangGraph-based PR Validation Workflow

Graph state flows through 3 nodes:
  1. validate_input  → basic field checks
  2. ai_enhance      → call Azure OpenAI for improvement & validation
  3. format_output   → produce final AIValidationResult

The graph is compiled once and reused for all requests.
"""

from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END

from backend.schemas.request_schema import AIValidationResult
from backend.config.constants import AIStatus
from backend.llm.llm_provider import get_llm
from backend.llm.prompt_templates import PR_VALIDATION_PROMPT
from backend.llm.output_parsers import PRValidationOutputParser
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Graph State ─────────────────────────────────────────────────────────────

class PRValidationState(TypedDict):
    # Input
    item_name: str
    category: str
    quantity: int
    budget: float
    description: str

    # Intermediate
    validation_errors: List[str]

    # Output
    result: Optional[AIValidationResult]
    error: Optional[str]


# ─── Nodes ────────────────────────────────────────────────────────────────────

def validate_input_node(state: PRValidationState) -> PRValidationState:
    """Node 1: Validate that required fields are non-empty and sane."""
    errors = []

    if not state.get("item_name", "").strip():
        errors.append("item_name is required")
    if not state.get("category", "").strip():
        errors.append("category is required")
    if state.get("quantity", 0) < 1:
        errors.append("quantity must be >= 1")
    if state.get("budget", 0) <= 0:
        errors.append("budget must be > 0")
    if len(state.get("description", "").strip()) < 10:
        errors.append("description must be at least 10 characters")

    logger.info("Input validation: %d errors found", len(errors))
    return {**state, "validation_errors": errors}


def ai_enhance_node(state: PRValidationState) -> PRValidationState:
    """Node 2: Call Azure OpenAI to enhance and validate the PR."""
    if state.get("validation_errors"):
        # Skip AI call if basic validation failed
        logger.warning("Skipping AI call due to validation errors: %s", state["validation_errors"])
        result = AIValidationResult(
            improved_description=state.get("description", ""),
            missing_fields=state["validation_errors"],
            budget_feedback="Cannot assess budget — input validation failed.",
            status=AIStatus.NEEDS_REVIEW,
        )
        return {**state, "result": result, "error": None}

    try:
        llm = get_llm()
        parser = PRValidationOutputParser()

        chain = PR_VALIDATION_PROMPT | llm

        logger.info("Calling Azure OpenAI for PR: item=%s category=%s", state["item_name"], state["category"])

        response = chain.invoke({
            "item_name": state["item_name"],
            "category": state["category"],
            "quantity": state["quantity"],
            "budget": state["budget"],
            "description": state["description"],
        })

        result = parser.parse(response.content)
        logger.info("AI validation complete: status=%s", result.status)

        return {**state, "result": result, "error": None}

    except Exception as e:
        logger.error("Azure OpenAI call failed: %s", str(e))
        fallback = AIValidationResult(
            improved_description=state.get("description", ""),
            missing_fields=[],
            budget_feedback="AI service temporarily unavailable. Manual review recommended.",
            status=AIStatus.NEEDS_REVIEW,
        )
        return {**state, "result": fallback, "error": str(e)}


def format_output_node(state: PRValidationState) -> PRValidationState:
    """Node 3: Final output formatting/logging."""
    result = state.get("result")
    if result:
        logger.info(
            "PR validation complete | status=%s | missing=%s",
            result.status,
            result.missing_fields,
        )
    return state


# ─── Graph Construction ───────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(PRValidationState)

    graph.add_node("validate_input", validate_input_node)
    graph.add_node("ai_enhance", ai_enhance_node)
    graph.add_node("format_output", format_output_node)

    graph.set_entry_point("validate_input")
    graph.add_edge("validate_input", "ai_enhance")
    graph.add_edge("ai_enhance", "format_output")
    graph.add_edge("format_output", END)

    return graph.compile()


# Compiled graph — singleton for reuse
pr_validation_graph = _build_graph()


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_pr_validation(
    item_name: str,
    category: str,
    quantity: int,
    budget: float,
    description: str,
) -> AIValidationResult:
    """Execute the LangGraph PR validation pipeline and return AIValidationResult."""
    initial_state: PRValidationState = {
        "item_name": item_name,
        "category": category,
        "quantity": quantity,
        "budget": budget,
        "description": description,
        "validation_errors": [],
        "result": None,
        "error": None,
    }

    final_state = await pr_validation_graph.ainvoke(initial_state)

    result = final_state.get("result")
    if result is None:
        raise RuntimeError("PR validation graph returned no result")

    return result
