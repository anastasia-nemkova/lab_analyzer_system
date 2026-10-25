"""
Контракт репозитория и in-memory реализация
"""

from typing import Protocol

from lab_analyzer.errors import CONFLICT, SubmissionError
from lab_analyzer.models import Submission


class SubmissionRepository(Protocol):
    """Контракт для хранения сдач"""

    def get(self, submission_id: str) -> Submission | None:
        ...

    def add(self, submission: Submission) -> None:
        ...

class InMemorySubmissionRepository:
    """Хранит версии сдач в памяти процесса"""

    def __init__(self) -> None:
        self._items: dict[str, Submission] = {}

    def get(self, submission_id: str) -> Submission | None:
        return self._items.get(submission_id)

    def add(self, submission: Submission) -> None:
        if submission.submission_id in self._items:
            raise SubmissionError(
                CONFLICT, 
                "submission_id", 
                "Сдача с таким идентификатором уже сохранена"
            )
        self._items[submission.submission_id] = submission

    def __len__(self) -> int:
        return len(self._items)