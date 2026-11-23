"""
Контракт анализаторов сдач.
"""

from typing import Literal, Protocol, runtime_checkable

from lab_analyzer.errors import AnalysisFailure
from lab_analyzer.models import (
    AnalysisContext,
    AnalysisReport,
    Evidence,
    Finding,
    Submission,
)
from lab_analyzer.reporting import make_report


@runtime_checkable
class Analyzer(Protocol):
    """Синхронный контракт: analyze(submission, context) -> AnalysisReport"""

    @property
    def analyzer_id(self) -> str:
        ...

    @property
    def analyzer_version(self) -> str:
        ...

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        ...

def nonempty_line_numbers(text: str) -> tuple[int, ...]:
    """
    Номера непустых строк (нумерация с 1), исходный текст не изменяется
    """
    return tuple(
        number for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    )

def template_ranges(source_code: str, template: str) -> tuple[tuple[int, int], ...]:
    """
    Точные неперекрывающиеся блоки строк шаблона. Пробелы не нормализуются
    """
    if not template.strip():
        return()

    source_lines = source_code.splitlines()
    template_lines = template.splitlines()
    width = len(template_lines)

    found: list[tuple[int, int]] = []
    index = 0
    while index + width <= len(source_lines):
        if source_lines[index : index + width] == template_lines:
            found.append((index + 1, index + width))
            index += width
        else:
            index += 1
    return tuple(found)

def _line_evidence(
    submission: Submission, field: Literal["text", "code"], numbers: tuple[int, ...]
) -> tuple[Evidence, ...]:
    return tuple(Evidence(submission.submission_id, field, n, n) for n in numbers)


class LengthAnalyzer:
    """
    Анализатор, подсчитывающий непустые строки текста и кода.
    """
    analyzer_id: str = "length"
    analyzer_version: str ="1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        text_lines = nonempty_line_numbers(submission.text)
        code_lines = nonempty_line_numbers(submission.code)

        evidence = _line_evidence(submission, "text", text_lines) + _line_evidence(
            submission, "code", code_lines
        )

        finding = Finding(
            kind="rubric_feedback",
            score = None,
            evidence=evidence,
            explanation=(
            f"Непустые строки: text={len(text_lines)}, code={len(code_lines)}. "
            f"Длина не оценивает корректность решения."
            ),
        )
        return make_report(
            submission=submission,
            context=context,
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            findings=(finding,),
            review_required=False,
        )

class TemplateAnalyzer:
    """
    Анализатор, ищущий точные совпадения с разрешённым шаблоном
    """

    analyzer_id: str = "template"
    analyzer_version: str = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        if submission.assignment_id != context.assignment.assignment_id:
            raise AnalysisFailure(
                f"Контекст относится к другому заданию: "
                f"сдача={submission.submission_id}, контекст={context.assignment.assignment_id}"
            )

        ranges = template_ranges(submission.code, context.assignment.allowed_template)

        evidence = tuple(
            Evidence(
                submission_id=submission.submission_id,
                field="code",
                start_line=start,
                end_line=end,
            )
            for start, end in ranges
        )

        if ranges:
            explanation = (
                f"Найдены разрешённые блоки шаблона: {len(ranges)}. "
                f"Это допустимое совпадение, а не основание санкции."
            )
        else:
            explanation = (
                "Точное совпадение с разрешённым шаблоном не найдено. "
                "Нечёткое сходство не проверялось."
            )

        finding = Finding(
            kind="similarity",
            score=None,
            evidence=evidence,
            explanation=explanation,
        )

        return make_report(
            submission=submission,
            context=context,
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            findings=(finding,),
            review_required=False,
        )

class DeclarationAnalyzer:
    """
    Анализатор AI-декларации.
    Проверяет согласованность декларации использования ИИ
    """
    analyzer_id: str = "declaration"
    analyzer_version: str = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        declaration = submission.ai_declaration
        if declaration.used:
            explanation= (
                f"Использование ИИ заявлено. Инструмент: {declaration.tool}; "
                f"цель: {declaration.purpose}."
            )
        else:
            explanation = (
                "Использование ИИ не заявлено. Авторство текста автоматически не определялось."
            )
        finding = Finding(
            kind="rubric_feedback",
            score=None,
            evidence=(),
            explanation=explanation,
        )
        return make_report(
            submission=submission,
            context=context,
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            findings=(finding,),
            review_required=declaration.used and not declaration.verified_by_student,
        )

class MissingExplanationAnalyzer:
    """
    Анализатор, обнаруживающий отсутствие пояснения при наличии кода
    """
    analyzer_id: str = "missing-explanation"
    analyzer_version: str = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        has_text = bool(submission.text.strip())
        has_code = bool(submission.code.strip())

        if not has_text and has_code:
            explanation = (
                "Пояснение к коду отсутствует: поле text пусто при непустом коде."
            )
        else:
            explanation = (
                "Сдача содержит текстовое пояснение или не содержит кода."
            )
        finding = Finding(
            kind="rubric_feedback",
            score=None,
            evidence=(),
            explanation=explanation,
        )
        return make_report(
            submission=submission,
            context=context,
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            findings=(finding,),
            review_required=False,
        )

        
