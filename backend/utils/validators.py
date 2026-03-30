from typing import Any


def validate_positive_number(value: Any, field_name: str) -> float:
    try:
        num = float(value)
        if num <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")
        return num
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid positive number.")


def validate_positive_int(value: Any, field_name: str) -> int:
    try:
        num = int(value)
        if num < 1:
            raise ValueError(f"{field_name} must be at least 1.")
        return num
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid positive integer.")
