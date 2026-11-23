"""Проверка результата на границе: score, evidence, связь со сдачей и конфигурацией"""

import json
from dataclasses import replace

import pytest

from lab_analyzer.analyzers import LengthAnalyzer
from lab_analyzer.config import DEFAULT_CONFIG
from lab_analyzer.errors import AnalysisFailure
from lab_analyzer.hashing import stable_hash
from lab_analyzer.models import (
    AnalysisContext,
    AnalysisReport,
    Assignment,
    Evidence,
    Finding,
    Submission,
)
from lab_analyzer.reporting import make_report, report_to_dict, validate_report


@pytest.fixture
def context() -> AnalysisContext:
    return AnalysisContext(Assignment("assignment-01", "from typing import Iterable\n", ("a",)))


def _report(submission: Submission, context: AnalysisContext, finding: Finding) -> AnalysisReport:
    good = LengthAnalyzer().analyze(submission, context)
    return replace(good, findings=(finding,))


def _finding(**updates: object) -> Finding:
    base = Finding("rubric_feedback", None, (), "объяснение")
    return replace(base, **updates)


@pytest.mark.parametrize("score", [True, float("nan"), float("inf"), 1.5, -0.1, "0.5"])
def test_bad_scores_rejected(
    submission: Submission, context: AnalysisContext, score: object
) -> None:
    report = _report(submission, context, _finding(score=score))
    with pytest.raises(AnalysisFailure):
        validate_report(report, submission, context)


@pytest.mark.parametrize("score", [None, 0, 0.0, 0.5, 1, 1.0])
def test_good_scores_accepted(
    submission: Submission, context: AnalysisContext, score: float | None
) -> None:
    validate_report(_report(submission, context, _finding(score=score)), submission, context)


@pytest.mark.parametrize(
    "evidence",
    [
        Evidence("sub-001", "code", 0, 1),  # строка 0
        Evidence("sub-001", "code", 3, 2),  # конец раньше начала
        Evidence("sub-001", "code", 1, 99),  # за границами
        Evidence("sub-001", "diagram", 1, 1),  # отсутствующее поле
        Evidence("other", "code", 1, 1),  # чужая сдача
    ],
)
def test_bad_evidence_rejected(
    submission: Submission, context: AnalysisContext, evidence: Evidence
) -> None:
    report = _report(submission, context, _finding(evidence=(evidence,)))
    with pytest.raises(AnalysisFailure):
        validate_report(report, submission, context)


def test_empty_explanation_rejected(submission: Submission, context: AnalysisContext) -> None:
    report = _report(submission, context, _finding(explanation="  "))
    with pytest.raises(AnalysisFailure):
        validate_report(report, submission, context)


def test_unknown_kind_rejected(submission: Submission, context: AnalysisContext) -> None:
    report = _report(submission, context, _finding(kind="verdict"))
    with pytest.raises(AnalysisFailure):
        validate_report(report, submission, context)


def test_wrong_hash_and_wrong_config_rejected(
    submission: Submission, context: AnalysisContext
) -> None:
    good = LengthAnalyzer().analyze(submission, context)
    with pytest.raises(AnalysisFailure):
        validate_report(replace(good, submission_hash="incorrect"), submission, context)
    with pytest.raises(AnalysisFailure):
        validate_report(replace(good, config_hash="incorrect"), submission, context)


def test_naive_created_at_rejected(submission: Submission, context: AnalysisContext) -> None:
    good = LengthAnalyzer().analyze(submission, context)
    with pytest.raises(AnalysisFailure):
        validate_report(replace(good, created_at="2026-01-01T00:00:00"), submission, context)


def test_findings_must_be_tuple(submission: Submission, context: AnalysisContext) -> None:
    good = LengthAnalyzer().analyze(submission, context)
    with pytest.raises(AnalysisFailure):
        validate_report(replace(good, findings=[]), submission, context)


def test_config_change_changes_config_hash_and_invalidates_old_report(
    submission: Submission, context: AnalysisContext
) -> None:
    old = LengthAnalyzer().analyze(submission, context)
    new_context = replace(context, config_version="2")
    assert stable_hash(new_context.config_payload()) != old.config_hash
    with pytest.raises(AnalysisFailure):
        validate_report(old, submission, new_context)

    new_template = replace(
        context, assignment=replace(context.assignment, allowed_template="import os\n")
    )
    assert stable_hash(new_template.config_payload()) != old.config_hash


def test_make_report_validates(submission: Submission, context: AnalysisContext) -> None:
    bad = Finding("rubric_feedback", 2.0, (), "x")
    with pytest.raises(AnalysisFailure):
        make_report(submission, context, "length", "1.0", (bad,))


def test_report_to_dict_is_json_ready(submission: Submission, context: AnalysisContext) -> None:
    import json

    data = report_to_dict(LengthAnalyzer().analyze(submission, context))
    assert json.loads(json.dumps(data, ensure_ascii=False))["analyzer_id"] == "length"


def test_context_payload_is_json_serialisable_and_has_stable_keys() -> None:
    ctx = AnalysisContext(Assignment("a", "t\n", ("r1", "r2")))
    payload = ctx.config_payload()
    assert set(payload) == {"assignment", "mode", "config_version"}
    json.dumps(payload)


def test_text_evidence_is_validated(submission: Submission) -> None:
    ctx = DEFAULT_CONFIG.context()
    good = Finding("rubric_feedback", None, (Evidence("sub-001", "text", 1, 1),), "ok")
    make_report(submission, ctx, "x", "1", (good,))
    bad = Finding("rubric_feedback", None, (Evidence("sub-001", "text", 2, 2),), "bad")
    with pytest.raises(Exception, match="границы"):
        make_report(submission, ctx, "x", "1", (bad,))
