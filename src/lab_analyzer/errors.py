"""Доменные ошибки приёма сдач"""

from typing import Final

INVALID_JSON: Final = "invalid_json"
SCHEMA_ERROR: Final = "schema_error"
UNSUPPORTED_VERSION: Final = "unsupported_version"
CONFLICT: Final = "conflict"

class SubmissionError(Exception):
    """Ожидаемая ошибка обработки одной сдачи"""
    
    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def to_dict(self) -> dict[str, str]:
        """Преобразует ошибку в словарь для сериализации в JSON"""
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message
        }

    def __repr__(self) -> str:
        """Подробное представление ошибки (traceback, логи, REPL)"""
        return (
            f"SubmissionError (code = {self.code!r}, field = {self.field!r}, "
            f"message = {self.message!r})"
        )

class AnalysisFailure(Exception):
    """
    Ошибка, связанная с анализом сдач.
    """
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"AnalysisFailure (message = {self.message!r})"

class ConfigError(Exception):
    """
    Ошибка конфигурации приложения.
    """
    def __init__ (self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": "config_invalid", "field": self.field, "message": self.message}

    def __repr__(self) -> str:
        return f"ConfigError (field = {self.field!r}, message = {self.message!r})"