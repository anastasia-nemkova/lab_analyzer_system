"""Доменные модели системы"""

from dataclasses import dataclass


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