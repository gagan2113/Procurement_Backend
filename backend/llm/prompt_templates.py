from langchain_core.prompts import ChatPromptTemplate

PR_VALIDATION_SYSTEM_PROMPT = """You are a procurement validation expert for an enterprise procurement system.
Your role is to validate and enhance procurement requests to ensure they are complete, accurate, and appropriate.
Always respond with valid JSON only — no markdown, no explanation, no extra text."""

PR_VALIDATION_HUMAN_PROMPT = """Validate the following procurement request and improve it:

Item: {item_name}
Category: {category}
Quantity: {quantity}
Budget: {budget}
Description: {description}

Respond ONLY with a JSON object in the following exact format:
{{
  "improved_description": "<A detailed, professional, and complete description of the procurement request>",
  "missing_fields": ["<field1>", "<field2>"],
  "budget_feedback": "<Detailed feedback on whether the budget is realistic for this item/category/quantity>",
  "status": "<'valid' if the request is complete and budget is reasonable, 'needs_review' otherwise>"
}}

Rules:
- improved_description: Always provide a better, more detailed version of the description (minimum 30 words).
- missing_fields: List any critical missing information (e.g. brand, specifications, delivery timeline). Return empty list [] if nothing is missing.
- budget_feedback: Comment on whether the budget per unit is realistic (budget / quantity = unit cost). Be specific.
- status: Use 'valid' only if description is complete AND budget is reasonable. Otherwise use 'needs_review'."""

PR_VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PR_VALIDATION_SYSTEM_PROMPT),
    ("human", PR_VALIDATION_HUMAN_PROMPT),
])
