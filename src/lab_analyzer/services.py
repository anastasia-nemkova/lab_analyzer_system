"""
Сервис приёма сдач. Оркестрирует парсинг, хеширование и сохранение
"""

from dataclasses import dataclass
from typing import Any, Literal

from lab_analyzer.errors import CONFLICT, SubmissionError
from lab_analyzer.hashing import submission_hash
from lab_analyzer.parsing import parse_submission
from lab_analyzer.repositories import SubmissionRepository

AcceptanceStatus = Literal["accepted", "duplicate"]

@dataclass(frozen=True, slots=True)
class Acceptance:
    """Результат попытки приёма сдачи"""
    status: AcceptanceStatus
    submission_id: str
    content_hash: str

class SubmissionService:
    """Сервис, реализующий бизнес-логику приёма работ"""
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def accept(self, raw: dict[str, Any]) -> Acceptance:
        submission = parse_submission(raw)
        digest = submission_hash(submission)

        existing = self._repository.get(submission.submission_id)
        if existing is None:
            self._repository.add(submission)
            return Acceptance("accepted", submission.submission_id, digest)

        if submission_hash(existing) == digest:
            return Acceptance("duplicate", submission.submission_id, digest)

        raise SubmissionError(
            CONFLICT, 
            "submission_id",  
            "Для новой версии работы требуется новый submission_id",
        )