"""Доменные ошибки приёма сдач"""

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

    def __rerp__(self) -> str:
        """Подробное представление ошибки (traceback, логи, REPL)"""
        return (
            f"SubmissionError (code = {self.code!r}, field = {self.field!r}, "
            f"message = {self.message!r})"
        )