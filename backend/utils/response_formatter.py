from typing import Any, Optional
from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[Any] = None


def success_response(data: Any = None, message: str = "Success") -> dict:
    return APIResponse(success=True, message=message, data=data).model_dump()


def error_response(message: str, errors: Any = None) -> dict:
    return APIResponse(success=False, message=message, errors=errors).model_dump()
