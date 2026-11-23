"""Доменные модели системы"""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AIDeclaration:
    """Декларация использования ИИ при написании работы"""
    used: bool
    tool: str | None
    purpose: str | None
    verified_by_student: bool

@dataclass(frozen=True, slots=True)
class Submission:
    """Неизменяемая версия сданной работы студента"""
    schema_version: int
    submission_id: str
    student_id: str
    assignment_id: str
    submitted_at: str  
    text: str
    code: str
    template_id: str | None
    ai_declaration: AIDeclaration

@dataclass(frozen=True, slots=True)
class Assignment:
    """Требования к лабораторной работе"""
    assignment_id: str
    allowed_template: str
    requirements: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Evidence:
    """Ссылка на строки исходного содержимого"""
    submission_id: str
    field: Literal["text", "code"]
    start_line: int
    end_line: int

@dataclass(frozen=True, slots=True)
class Finding:
    """Наблюдение анализатора о сдаче"""
    kind: Literal["similarity", "rubric_feedback", "processing_error"]
    score: float | None
    evidence: tuple[Evidence, ...]
    explanation: str

@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Отчёт анализатора о результатах проверки сдачи"""
    report_id: str
    submission_id: str
    submission_hash: str
    analyzer_id: str
    analyzer_version: str
    config_hash: str
    findings: tuple[Finding, ...]
    created_at: str
    review_required: bool

@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Контекст выполнения анализа"""
    assignment: Assignment
    mode: Literal["baseline", "stub"] = "baseline"
    config_version: str = "1"

    def config_payload(self) -> dict[str, object]:
        return {
            "assignment": asdict(self.assignment),
            "mode": self.mode,
            "config_version": self.config_version,
        }
