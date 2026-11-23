"""
Создание и валидация отчётов анализаторов.
"""

import math
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lab_analyzer.errors import AnalysisFailure
from lab_analyzer.hashing import stable_hash, submission_hash
from lab_analyzer.models import (
    AnalysisContext,
    AnalysisReport,
    Evidence,
    Finding,
    Submission,
)

FINDING_KINDS = frozenset({"similarity", "rubric_feedback", "processing_error"})
EVIDENCE_FIELDS = frozenset({"text", "code"})

def _validate_evidence(evidence: Evidence, submission: Submission) -> None:
    if evidence.submission_id != submission.submission_id:
        raise AnalysisFailure("Evidence ссылается на другую сдачу")
    if evidence.field not in EVIDENCE_FIELDS:
        raise AnalysisFailure("Evidence ссылается на неизвестное поле")
    if type(evidence.start_line) is not int or type(evidence.end_line) is not int:
        raise AnalysisFailure("Номер строки должен быть int")
    lines = getattr(submission, evidence.field).splitlines()
    if not 1 <= evidence.start_line <= evidence.end_line <= len(lines):
        raise AnalysisFailure(
            f"Evidence выходит за границы исходного текста: "
            f"строки {evidence.start_line}-{evidence.end_line}, "
            f"всего строк {len(lines)}"
        )


def _validate_finding(finding: Finding, submission: Submission) -> None:
    if finding.kind not in FINDING_KINDS:
        raise AnalysisFailure("Неизвестный kind")

    if finding.score is not None:
        if type(finding.score) not in (int, float):
            raise AnalysisFailure("score должен быть числом")
        if not math.isfinite(finding.score):
            raise AnalysisFailure("score должен быть конечным числом")
        if not 0 <= finding.score <= 1:
            raise AnalysisFailure("score должен быть в диапазоне 0–1")

    if not isinstance(finding.explanation, str) or not finding.explanation.strip():
        raise AnalysisFailure("Объяснение наблюдения обязательно")
    if not isinstance(finding.evidence, tuple):
        raise AnalysisFailure("evidence должен быть кортежем")
    for evidence in finding.evidence:
        _validate_evidence(evidence, submission)


def validate_report(
    report: AnalysisReport,
    submission: Submission,
    context: AnalysisContext
) -> None:
    if not isinstance(report, AnalysisReport):
        raise AnalysisFailure("Ожидается AnalysisReport")
    if report.submission_id != submission.submission_id:
        raise AnalysisFailure("Отчёт ссылается на другую сдачу")
    if report.submission_hash != submission_hash(submission):
        raise AnalysisFailure("Отчёт ссылается на другую версию сдачи")
    
    if report.config_hash != stable_hash(context.config_payload()):
        raise AnalysisFailure("Отчёт использует другую конфигурацию")
    
    if not report.report_id or not report.analyzer_id or not report.analyzer_version:
        raise AnalysisFailure("Идентификаторы отчёта и анализатора обязательны")
    
    if type(report.review_required) is not bool:
        raise AnalysisFailure("review_required должен быть bool")
    
    try:
        created = datetime.fromisoformat(report.created_at)
    except (ValueError, TypeError) as exc:
        raise AnalysisFailure("Время отчёта имеет неверный формат") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        raise AnalysisFailure("Часовой пояс времени отчёта обязателен")
    
    if not isinstance(report.findings, tuple):
        raise AnalysisFailure("findings должен быть кортежем")
    for finding in report.findings:
        _validate_finding(finding, submission)

def make_report(
    submission: Submission,
    context: AnalysisContext,
    analyzer_id: str,
    analyzer_version: str,
    findings: tuple[Finding, ...],
    *,
    review_required: bool = False,
) -> AnalysisReport:
    report = AnalysisReport(
        report_id=str(uuid4()),
        submission_id=submission.submission_id,
        submission_hash=submission_hash(submission),
        analyzer_id=analyzer_id,
        analyzer_version=analyzer_version,
        config_hash=stable_hash(context.config_payload()),
        findings=findings,
        created_at=datetime.now(UTC).isoformat(),
        review_required=review_required,
    )

    validate_report(report, submission, context)

    return report

def report_to_dict(report: AnalysisReport) -> dict[str, Any]:
    """Сериализуемое представление отчёта"""
    return asdict(report)

