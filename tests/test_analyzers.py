"""Семантика и контракт анализаторов"""

import copy
from dataclasses import replace

import pytest

from lab_analyzer.analyzers import (
    Analyzer,
    DeclarationAnalyzer,
    LengthAnalyzer,
    MissingExplanationAnalyzer,
    TemplateAnalyzer,
    nonempty_line_numbers,
    template_ranges,
)
from lab_analyzer.errors import AnalysisFailure
from lab_analyzer.models import AIDeclaration, AnalysisContext, Assignment, Submission
from lab_analyzer.parsing import parse_submission
from lab_analyzer.reporting import validate_report
from tests.cases import changed, declaration


@pytest.fixture
def context() -> AnalysisContext:
    assignment = Assignment("assignment-01", "from typing import Iterable\n", ("solve",))
    return AnalysisContext(assignment)


ALL_ANALYZERS = [
    LengthAnalyzer,
    TemplateAnalyzer,
    DeclarationAnalyzer,
    MissingExplanationAnalyzer,
]


@pytest.mark.parametrize("factory", ALL_ANALYZERS)
def test_analyzer_contract(
    factory: type[Analyzer], submission: Submission, context: AnalysisContext
) -> None:
    analyzer = factory()
    assert isinstance(analyzer, Analyzer)
    before = copy.deepcopy(submission)
    first = analyzer.analyze(submission, context)
    second = analyzer.analyze(submission, context)
    validate_report(first, submission, context)
    validate_report(second, submission, context)
    assert first.findings == second.findings
    assert first.submission_hash == second.submission_hash
    assert first.config_hash == second.config_hash
    assert first.report_id != second.report_id
    assert first.analyzer_id == analyzer.analyzer_id
    assert first.analyzer_version == analyzer.analyzer_version
    assert all(f.explanation.strip() for f in first.findings)
    assert all(f.score is None for f in first.findings)
    assert submission == before


def test_nonempty_line_numbers() -> None:
    assert nonempty_line_numbers("\n a \n\n b\n") == (2, 4)
    assert nonempty_line_numbers("") == ()


def test_length_analyzer_counts_and_evidence(
    submission: Submission, context: AnalysisContext
) -> None:
    report = LengthAnalyzer().analyze(submission, context)
    finding = report.findings[0]
    assert finding.kind == "rubric_feedback"
    assert "text=1, code=3" in finding.explanation
    code_lines = [e.start_line for e in finding.evidence if e.field == "code"]
    assert code_lines == [1, 3, 4]


def test_length_analyzer_does_not_judge_quality(
    submission: Submission, context: AnalysisContext
) -> None:
    explanation = LengthAnalyzer().analyze(submission, context).findings[0].explanation
    assert "не оценивает корректность" in explanation


def test_template_exact_match(submission: Submission, context: AnalysisContext) -> None:
    report = TemplateAnalyzer().analyze(submission, context)
    evidence = report.findings[0].evidence
    assert [(e.start_line, e.end_line) for e in evidence] == [(1, 1)]


def test_template_two_line_cases() -> None:
    template = "import os\nimport sys\n"
    assert template_ranges("import os\nimport sys\nx = 1\n", template) == ((1, 2),)
    assert template_ranges("import os\nimport  sys\n", template) == ()  # пробел изменён
    assert template_ranges("import os\nimport sys\nimport os\nimport sys\n", template) == (
        (1, 2),
        (3, 4),
    )
    assert template_ranges("x = 1\ny = 2\n", template) == ()
    assert template_ranges("a\n", " \n") == ()


def test_template_ranges_do_not_overlap() -> None:
    assert template_ranges("a\na\na\n", "a\na\n") == ((1, 2),)


def test_template_not_found_says_fuzzy_not_checked(context: AnalysisContext) -> None:
    sub = parse_submission(changed(code="def solve(values):\n    return 0\n"))
    finding = TemplateAnalyzer().analyze(sub, context).findings[0]
    assert finding.evidence == ()
    assert "Нечёткое сходство не проверялось" in finding.explanation


def test_template_rejects_other_assignment(submission: Submission) -> None:
    other = AnalysisContext(Assignment("assignment-99", "x\n", ()))
    with pytest.raises(AnalysisFailure):
        TemplateAnalyzer().analyze(submission, other)


def test_declaration_not_used(submission: Submission, context: AnalysisContext) -> None:
    report = DeclarationAnalyzer().analyze(submission, context)
    assert "не заявлено" in report.findings[0].explanation
    assert report.review_required is False


@pytest.mark.parametrize(("verified", "expected"), [(True, False), (False, True)])
def test_declaration_review_required(
    context: AnalysisContext, verified: bool, expected: bool
) -> None:
    sub = parse_submission(
        changed(
            ai_declaration=declaration(
                used=True, tool="помощник", purpose="обсуждение", verified_by_student=verified
            )
        )
    )
    report = DeclarationAnalyzer().analyze(sub, context)
    assert report.review_required is expected
    assert "помощник" in report.findings[0].explanation


def test_missing_explanation(context: AnalysisContext) -> None:
    sub = parse_submission(changed(text="   "))
    finding = MissingExplanationAnalyzer().analyze(sub, context).findings[0]
    assert "отсутствует" in finding.explanation


def test_explanation_present(submission: Submission, context: AnalysisContext) -> None:
    finding = MissingExplanationAnalyzer().analyze(submission, context).findings[0]
    assert "отсутствует" not in finding.explanation.split(":")[0]


def test_hand_built_submission_with_trailing_text_lines(context: AnalysisContext) -> None:
    sub = replace(
        parse_submission(changed()),
        ai_declaration=AIDeclaration(False, None, None, True),
        text="line1\n\nline3",
    )
    report = LengthAnalyzer().analyze(sub, context)
    validate_report(report, sub, context)
