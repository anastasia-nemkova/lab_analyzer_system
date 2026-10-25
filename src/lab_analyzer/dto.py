"""
Модуль DTO (Data Transfer Object) для строгой валидации входных данных.
DTO описывает контракт внешнего мира. После успешной валидации DTO конвертируется 
в неизменяемую доменную модель (Submission).
"""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from lab_analyzer.models import AIDeclaration, Submission

SUPPORTED_SCHEMA_VERSION = 1

class DeclarationInput(BaseModel):
    """DTO для вложенной декларации использования ИИ"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    used: bool
    tool: str | None
    purpose: str | None
    verified_by_student: bool

    @field_validator("tool", "purpose")
    @classmethod
    def _nonempty_or_none(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Допускается непустая строка или None")
        return value

    @model_validator(mode="after")
    def _check_used_fields(self) -> Self:
        if self.used and (self.tool is None or self.purpose is None):
            raise ValueError("При used=true обязательны tool и purpose")
        return self

    def to_domain(self) -> AIDeclaration:
        return AIDeclaration(
            used=self.used,
            tool=self.tool,
            purpose=self.purpose,
            verified_by_student=self.verified_by_student,
        )

class SubmissionInput(BaseModel):
    """DTO для структуры сдачи (Submission)."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: int
    submission_id: str
    student_id: str
    assignment_id: str
    submitted_at: str
    text: str
    code: str
    template_id: str | None
    ai_declaration: DeclarationInput

    @field_validator("schema_version")
    @classmethod
    def _check_schema_version(cls, value: int) -> int:
        if value != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"Поддерживается версия схемы {SUPPORTED_SCHEMA_VERSION}")
        return value

    @field_validator("submission_id", "student_id", "assignment_id", "template_id")
    @classmethod
    def _nonempty_identifier(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Требуется непустой идентификатор")
        return value

    @field_validator("submitted_at")
    @classmethod
    def _timestamp(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ожидается непустая строка")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Ожидается дата и время ISO 8601 с часовым поясом") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Часовой пояс обязателен")
        return value

    @model_validator(mode="after")
    def _has_content(self) -> Self:
        if not self.text.strip() and not self.code.strip():
            raise ValueError("Поле text или code должно быть непустым")
        return self

    def to_domain(self) -> Submission:
        return Submission(
            schema_version=self.schema_version,
            submission_id=self.submission_id,
            student_id=self.student_id,
            assignment_id=self.assignment_id,
            submitted_at=self.submitted_at,
            text=self.text,
            code=self.code,
            template_id=self.template_id,
            ai_declaration=self.ai_declaration.to_domain(),
        )
    