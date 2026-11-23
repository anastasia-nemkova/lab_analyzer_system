"""Реестр анализаторов, контракт Analyzer, AnalysisService и подключение анализатора регистрацией"""

from dataclasses import replace
from pathlib import Path

import pytest

from lab_analyzer.analyzers import Analyzer, LengthAnalyzer
from lab_analyzer.app import build_application, default_registry
from lab_analyzer.config import DEFAULT_CONFIG
from lab_analyzer.errors import AnalysisFailure, ConfigError
from lab_analyzer.importer import import_source
from lab_analyzer.models import AnalysisContext, AnalysisReport, Finding, Submission
from lab_analyzer.registry import AnalyzerRegistry
from lab_analyzer.reporting import make_report
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import AnalysisService, SubmissionService
from lab_analyzer.sources import JSONLSource
from tests.cases import RAW_EXAMPLE


def test_default_registry_names() -> None:
    expected = {"declaration", "length", "missing-explanation", "template"}
    assert set(default_registry().names()) == expected


def test_every_builtin_satisfies_analyzer_protocol() -> None:
    registry = default_registry()
    for name in registry.names():
        assert isinstance(registry.create(name), Analyzer)


def test_object_without_analyze_is_not_analyzer() -> None:
    class Fake:
        analyzer_id = "x"
        analyzer_version = "1"

    assert not isinstance(Fake(), Analyzer)


ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "submissions.jsonl"
CONTEXT = DEFAULT_CONFIG.context()


def test_register_and_create() -> None:
    registry = AnalyzerRegistry()
    registry.register("length", LengthAnalyzer)
    assert isinstance(registry.create("length"), LengthAnalyzer)
    assert registry.create("length") is not registry.create("length")  # новый экземпляр


@pytest.mark.parametrize("name", ["", "  "])
def test_register_rejects_blank_name(name: str) -> None:
    with pytest.raises(AnalysisFailure):
        AnalyzerRegistry().register(name, LengthAnalyzer)


def test_register_rejects_duplicate() -> None:
    registry = AnalyzerRegistry()
    registry.register("length", LengthAnalyzer)
    with pytest.raises(AnalysisFailure):
        registry.register("length", LengthAnalyzer)


def test_unknown_analyzer() -> None:
    with pytest.raises(AnalysisFailure, match="Неизвестный"):
        AnalyzerRegistry().create("nope")


def test_name_must_match_analyzer_id() -> None:
    registry = AnalyzerRegistry()
    registry.register("other-name", LengthAnalyzer)
    with pytest.raises(AnalysisFailure, match="не совпадает"):
        registry.create("other-name")


def test_late_binding_fixed_in_factory_loop() -> None:
    registry = AnalyzerRegistry()
    for cls in (LengthAnalyzer,):
        registry.register(cls.analyzer_id, lambda cls=cls: cls())  # type: ignore[misc]
    assert registry.create("length").analyzer_id == "length"


@pytest.fixture
def populated() -> tuple[InMemorySubmissionRepository, AnalysisService, Submission]:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repo)
    service.accept(RAW_EXAMPLE)
    stored = repo.get("sub-001")
    assert stored is not None
    return repo, AnalysisService(repo, default_registry()), stored


def test_run_returns_validated_report(
    populated: tuple[InMemorySubmissionRepository, AnalysisService, Submission],
) -> None:
    _, analysis, stored = populated
    report = analysis.run("sub-001", "length", CONTEXT)
    assert report.submission_id == stored.submission_id


def test_run_requires_accepted_submission(
    populated: tuple[InMemorySubmissionRepository, AnalysisService, Submission],
) -> None:
    _, analysis, _ = populated
    with pytest.raises(AnalysisFailure, match="после приёма"):
        analysis.run("missing", "length", CONTEXT)


def test_run_rejects_other_assignment_context(
    populated: tuple[InMemorySubmissionRepository, AnalysisService, Submission],
) -> None:
    _, analysis, _ = populated
    other = AnalysisContext(replace(CONTEXT.assignment, assignment_id="assignment-99"))
    with pytest.raises(AnalysisFailure):
        analysis.run("sub-001", "length", other)


class BrokenAnalyzer:
    analyzer_id = "broken"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        return replace(LengthAnalyzer().analyze(submission, context), submission_hash="incorrect")


class ImpostorAnalyzer:
    analyzer_id = "impostor"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        return LengthAnalyzer().analyze(submission, context)  # id в отчёте — "length"


def test_defective_plugin_rejected_and_state_unchanged(
    populated: tuple[InMemorySubmissionRepository, AnalysisService, Submission],
) -> None:
    repo, _, stored = populated
    registry = default_registry()
    registry.register("broken", BrokenAnalyzer)
    registry.register("impostor", ImpostorAnalyzer)
    analysis = AnalysisService(repo, registry)
    with pytest.raises(AnalysisFailure, match="другую версию"):
        analysis.run("sub-001", "broken", CONTEXT)
    with pytest.raises(AnalysisFailure, match="не соответствует"):
        analysis.run("sub-001", "impostor", CONTEXT)
    assert repo.get("sub-001") == stored


def test_build_fails_fast_on_mismatched_registration() -> None:
    registry = AnalyzerRegistry()
    registry.register("length", ImpostorAnalyzer)
    with pytest.raises(ConfigError):
        build_application(replace(DEFAULT_CONFIG, analyzers=("length",)), registry=registry)


def test_third_analyzer_added_without_changing_central_service() -> None:
    """Проверка расширяемости на защите: анализатор подключается только регистрацией."""
    from lab_analyzer.models import AnalysisContext, AnalysisReport

    class NonEmptyDeclaration:
        analyzer_id = "declaration-nonempty"
        analyzer_version = "1.0"

        def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
            d = submission.ai_declaration
            ok = not d.used or bool((d.tool or "").strip() and (d.purpose or "").strip())
            text = "Декларация непуста при used=true." if ok else "Декларация пуста."
            return make_report(
                submission, context, self.analyzer_id, self.analyzer_version,
                (Finding("rubric_feedback", None, (), text),),
            )

    registry = default_registry()
    registry.register("declaration-nonempty", NonEmptyDeclaration)
    config = replace(DEFAULT_CONFIG, analyzers=(*DEFAULT_CONFIG.analyzers, "declaration-nonempty"))
    app = build_application(config, registry=registry)
    import_source(JSONLSource(CORPUS), app.submission_service)
    reports = app.analyze_all("sub-003")
    assert reports[-1].analyzer_id == "declaration-nonempty"
    assert "непуста" in reports[-1].findings[0].explanation
