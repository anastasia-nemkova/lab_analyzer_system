"""
Конфигурация приложения и сборка зависимостей
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from lab_analyzer.errors import ConfigError, SubmissionError
from lab_analyzer.models import AnalysisContext, Assignment
from lab_analyzer.parsing import decode_json


class AssignmentInput(BaseModel):
    """
    DTO для строгой валидации задания из конфигурации
    """
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    assignment_id: str
    allowed_template: str
    requirements: list[str]

    @field_validator("assignment_id")
    @classmethod
    def _nonblank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Требуется непустой идентификатор задания")
        return value

class ConfigInput(BaseModel):
    """
    DTO для всей конфигурации: задание, анализаторы, режим, версия
    """
    model_config = ConfigDict(strict=True, extra="forbid",frozen=True)
    assignment: AssignmentInput
    analyzers: list[str]
    mode: Literal["baseline", "stub"] = "baseline"
    config_version: str ="1"

    @field_validator("analyzers")
    @classmethod
    def _analyzer_valid(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Список анализаторов не может быть пустым")
        if any(not name.strip() for name in value):
            raise ValueError("Имя анализатора не может быть пустым")
        if len(set(value)) != len(value):
            raise ValueError("Имена анализаторов должны быть уникальными")
        return value

    @field_validator("config_version")
    @classmethod
    def _nonblank_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("config_version не может быть пустым")
        return value

@dataclass(frozen=True, slots=True)
class AppConfig:
    """
    Проверенная конфигурация: задание, список анализаторов и параметры контекста
    """
    assignment: Assignment
    analyzers: tuple[str, ...]
    mode: Literal["baseline", "stub"] = "baseline"
    config_version: str = "1"

    def context(self) -> AnalysisContext:
        return AnalysisContext(
            assignment=self.assignment,
            mode=self.mode,
            config_version=self.config_version,
        )

DEFAULT_CONFIG = AppConfig(
    assignment=Assignment(
        assignment_id="assignment-01",
        allowed_template="from typing import Iterable\n",
        requirements=("Наличие функции solve",),
    ),
    analyzers=("length", "template", "declaration"),
)

def parse_config(raw: dict[str, Any]) -> AppConfig:
    """
    Строгая проверка словаря конфигурации
    """
    try:
        dto = ConfigInput.model_validate(raw)
    except ValidationError as exc:
        err = exc.errors()[0]
        field = ".".join(str(part) for part in err["loc"])
        raise ConfigError(field, str(err["msg"]).removeprefix("Value error, ")) from exc
    return AppConfig(
        assignment=Assignment(
            assignment_id=dto.assignment.assignment_id,
            allowed_template=dto.assignment.allowed_template,
            requirements=tuple(dto.assignment.requirements),
        ),
        analyzers=tuple(dto.analyzers),
        mode=dto.mode,
        config_version=dto.config_version,
    )

def load_config(path: Path) -> AppConfig:
    """
    Чтение JSON-файл конфигурации
    """
    text = path.read_text(encoding="utf-8")
    try:
        raw = decode_json(text)
    except SubmissionError as exc:
        raise ConfigError("json", exc.message) from exc
    return parse_config(raw)