"""
Сервис приёма сдач. Оркестрирует парсинг, хеширование и сохранение
"""

from dataclasses import dataclass
from typing import Any, Literal

from lab_analyzer.errors import CONFLICT, AnalysisFailure, SubmissionError
from lab_analyzer.hashing import submission_hash
from lab_analyzer.models import AnalysisContext, AnalysisReport, Submission
from lab_analyzer.parsing import parse_submission
from lab_analyzer.registry import AnalyzerRegistry
from lab_analyzer.reporting import validate_report
from lab_analyzer.repositories import SubmissionRepository

AcceptanceStatus = Literal["accepted", "duplicate"]

@dataclass(frozen=True, slots=True)
class Acceptance:
    """Результат попытки приёма сдачи"""
    status: AcceptanceStatus
    submission_id: str
    content_hash: str

class SubmissionService:
    """Сервис, реализующий логику приёма работ"""
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def accept(self, raw: dict[str, Any]) -> Acceptance:
        """Принимает сырой объект: валидирует его и сохраняет"""
        submission = parse_submission(raw)
        return self.accept_submission(submission)

    def accept_submission(self,submission: Submission) -> Acceptance:
        """Принимает уже валидированную модель"""
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

class AnalysisService:
    """
    Находит сдачу, создаёт анализатор по имени и проверяет его отчёт на границе
    """
    def __init__(self, repository: SubmissionRepository, registry: AnalyzerRegistry) -> None:
        self._repository = repository
        self._registry = registry

    def run(
        self, 
        submission_id: str, 
        analyzer_name: str, 
        context: AnalysisContext
    ) -> AnalysisReport:
        submission = self._repository.get(submission_id)
        if submission is None:
            raise AnalysisFailure(
                f"Сдача {submission_id!r} не найдена. Анализ возможен после приёма."
            )
        if submission.assignment_id != context.assignment.assignment_id:
            raise AnalysisFailure(
                f"Контекст относится к заданию {context.assignment.assignment_id!r}, "
                f"а сдача — к {submission.assignment_id!r}. "
                "Требуется контекст соответствующего задания"
            )

        analyzer = self._registry.create(analyzer_name)
        report = analyzer.analyze(submission, context)
        validate_report(report, submission, context)

        if report.analyzer_id != analyzer.analyzer_id:
            raise AnalysisFailure(
                f"Отчёт не соответствует вызванному анализатору. "
                f"Отчёт имеет analyzer_id={report.analyzer_id!r}, "
                f"но вызван анализатор с analyzer_id={analyzer.analyzer_id!r}"
            )
        if report.analyzer_version != analyzer.analyzer_version:
            raise AnalysisFailure(
                "Версия анализатора в отчёте не совпадает с заявленной. "
                f"Отчёт имеет analyzer_version={report.analyzer_version!r}, "
                f"но анализатор сообщает версию {analyzer.analyzer_version!r}"
            )

        return report
        