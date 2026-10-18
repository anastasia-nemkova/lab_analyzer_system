"""
Парсинг JSON и валидация данных
"""

import json
from typing import Any

from pydantic import ValidationError

from lab_analyzer.dto import SubmissionInput
from lab_analyzer.errors import (
    INVALID_JSON,
    SCHEMA_ERROR,
    UNSUPPORTED_VERSION,
    SubmissionError,
)
from lab_analyzer.models import Submission


def _reject_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Отклоняет JSON-объекты с повторяющимися ключами"""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SubmissionError(INVALID_JSON, key, "Повтор ключа в JSON не допускается")
        result[key] = value
    return result

def _reject_invalid_constants(value: str) -> Any:
    """Отклоняет нестандартные значения (NaN, Infinity)"""
    raise SubmissionError(INVALID_JSON, "json", f"Нестандартное значение не допускается: {value}")

def decode_json(line: str) -> dict[str, Any]:
    """Разбирает одну JSON-строку; повтор ключей и NaN/Infinity отклоняются."""
    try:
        parsed = json.loads(
            line,
            object_pairs_hook=_reject_repeated_keys,
            parse_constant=_reject_invalid_constants,
        ) 
    except json.JSONDecodeError as exc:
        raise SubmissionError(
            INVALID_JSON, "json", f"Синтаксическая ошибка JSON: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SubmissionError(INVALID_JSON, "json", "Ожидается JSON-объект (словарь)")
    return parsed

def _convert_validations_error(exc: ValidationError) -> SubmissionError:
    """Преобразует Pydantic ValidationError в структурированный SubmissionError"""
    err = exc.errors()[0]

    field_name = ".".join(str(loc) for loc in err["loc"]) if err["loc"] else "json"
    msg = err["msg"]

    if not err["loc"] and "text" in msg and "code" in msg:
        field_name = "text/code"

    if "версия схемы" in msg.lower() or "version" in msg.lower():
        code = UNSUPPORTED_VERSION
    else:
        code = SCHEMA_ERROR
        
    return SubmissionError(code=code, field=field_name, message=msg)

def parse_submission(raw: dict[str, Any]) -> Submission:
    """Проверяет внешние данные и возвращает новую доменную модель"""
    try:
        dto = SubmissionInput.model_validate(raw)
    except ValidationError as exc:
        raise _convert_validations_error(exc) from exc
    return dto.to_domian()

