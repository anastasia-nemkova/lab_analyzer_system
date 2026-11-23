"""
Адаптер внешнего интерфейса
"""

from dataclasses import dataclass
from typing import Any, Final

from lab_analyzer.errors import (
    CONFLICT,
    INVALID_JSON,
    SCHEMA_ERROR,
    UNSUPPORTED_VERSION,
    SubmissionError,
)
from lab_analyzer.parsing import parse_submission
from lab_analyzer.services import SubmissionService

STATUS_BY_ERROR_CODE: Final[dict[str, int]] = {
    INVALID_JSON: 400,
    SCHEMA_ERROR: 400,
    UNSUPPORTED_VERSION: 400,
    CONFLICT: 409,
}

@dataclass(frozen=True, slots=True)
class PayloadResponse:
    status: int
    body: dict[str, Any]

def accept_payload(service: SubmissionService, payload: dict[str, Any]) -> PayloadResponse:
    """Валидирует DTO один раз и принимает готовую доменную модель"""
    try:
        submission = parse_submission(payload)
        result = service.accept_submission(submission)
    except SubmissionError as exc:
        return PayloadResponse(STATUS_BY_ERROR_CODE.get(exc.code, 400), {"error": exc.to_dict()})
    status = 201 if result.status == "accepted" else 200
    return PayloadResponse(
        status,
        {
            "status": result.status,
            "submission_id": result.submission_id,
            "content_hash": result.content_hash,
        },
    )
