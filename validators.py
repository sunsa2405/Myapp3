"""실험 결과 입력값 검증 (PRD 3.2절)."""

from __future__ import annotations

import math
from typing import Any

from db import COLUMN_LABELS, CONDITION_COLUMNS, PROPERTIES


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, float):
        return math.isnan(value)
    return False


def _to_number(value: Any) -> float | None:
    """숫자로 바꿀 수 없으면 None을 반환한다."""
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def validate_experiment(data: dict[str, Any]) -> list[str]:
    """입력값을 검증하고 오류 메시지 목록을 반환한다. 빈 목록이면 유효하다."""
    errors: list[str] = []

    if _is_blank(data.get("grade")):
        errors.append("Grade는 필수 입력입니다.")

    for col in CONDITION_COLUMNS:
        label = COLUMN_LABELS[col]
        value = data.get(col)
        if _is_blank(value):
            errors.append(f"{label}은(는) 필수 입력입니다.")
        elif _to_number(value) is None:
            errors.append(f"{label}은(는) 숫자여야 합니다. (입력값: {value})")

    for col in PROPERTIES:
        label = COLUMN_LABELS[col]
        value = data.get(col)
        if _is_blank(value):
            continue
        number = _to_number(value)
        if number is None:
            errors.append(f"{label}은(는) 숫자여야 합니다. (입력값: {value})")
        elif number < 0:
            errors.append(f"{label}은(는) 0 이상이어야 합니다. (입력값: {value})")

    return errors


def normalize_experiment(data: dict[str, Any]) -> dict[str, Any]:
    """검증을 통과한 입력값을 저장 형식(grade는 문자열, 나머지는 float/None)으로 바꾼다."""
    record: dict[str, Any] = {"grade": str(data["grade"]).strip()}
    for col in [*CONDITION_COLUMNS, *PROPERTIES]:
        value = data.get(col)
        record[col] = None if _is_blank(value) else _to_number(value)
    return record
