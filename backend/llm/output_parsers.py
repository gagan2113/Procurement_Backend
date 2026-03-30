import json
import re
from langchain_core.output_parsers import BaseOutputParser
from backend.schemas.request_schema import AIValidationResult
from backend.config.constants import AIStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PRValidationOutputParser(BaseOutputParser[AIValidationResult]):
    """Parse LLM output JSON into AIValidationResult Pydantic model."""

    def parse(self, text: str) -> AIValidationResult:
        logger.debug("Raw LLM output: %s", text)

        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s | raw: %s", e, cleaned)
            # Return a safe fallback
            return AIValidationResult(
                improved_description=text,
                missing_fields=["Unable to fully parse AI response"],
                budget_feedback="AI parsing error — manual review required.",
                status=AIStatus.NEEDS_REVIEW,
            )

        # Normalise status field
        raw_status = str(data.get("status", "needs_review")).lower().replace(" ", "_")
        if raw_status not in (AIStatus.VALID.value, AIStatus.NEEDS_REVIEW.value):
            raw_status = AIStatus.NEEDS_REVIEW.value

        return AIValidationResult(
            improved_description=data.get("improved_description", ""),
            missing_fields=data.get("missing_fields", []),
            budget_feedback=data.get("budget_feedback", ""),
            status=AIStatus(raw_status),
        )

    @property
    def _type(self) -> str:
        return "pr_validation_parser"
