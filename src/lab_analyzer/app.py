"""
Явная сборка приложения
"""

from dataclasses import dataclass

from lab_analyzer.analyzers import (
    DeclarationAnalyzer,
    LengthAnalyzer,
    MissingExplanationAnalyzer,
    TemplateAnalyzer,
)
from lab_analyzer.config import DEFAULT_CONFIG, AppConfig
from lab_analyzer.errors import AnalysisFailure, ConfigError
from lab_analyzer.models import AnalysisContext, AnalysisReport
from lab_analyzer.registry import AnalyzerRegistry
from lab_analyzer.repositories import InMemorySubmissionRepository, SubmissionRepository
from lab_analyzer.services import AnalysisService, SubmissionService


def default_registry() -> AnalyzerRegistry:
    """
    Реестр встроенных анализаторов
    """
    registry = AnalyzerRegistry()
    registry.register("length", LengthAnalyzer)
    registry.register("template", TemplateAnalyzer)
    registry.register("declaration", DeclarationAnalyzer)
    registry.register("missing-explanation", MissingExplanationAnalyzer)
    return registry

@dataclass
class Application:
    config: AppConfig
    repository: SubmissionRepository
    registry: AnalyzerRegistry
    submission_service: SubmissionService
    analysis_service: AnalysisService

    @property
    def context(self) -> AnalysisContext:
        return self.config.context()

    def analyze_all(self, submission_id: str) -> list[AnalysisReport]:
        return [
            self.analysis_service.run(submission_id, name, self.context)
            for name in self.config.analyzers
        ]

def build_application(
    config: AppConfig | None = None,
    *,
    registry: AnalyzerRegistry | None = None,
    repository: SubmissionRepository | None = None,
) -> Application:
    """
    Собирает приложение и проверяет конфигурацию анализаторов до первого вызова
    """
    cfg = DEFAULT_CONFIG if config is None else config
    reg = default_registry() if registry is None else registry
    repo = InMemorySubmissionRepository() if repository is None else repository

    for name in cfg.analyzers:
        if name not in reg:
            raise ConfigError("analyzers", f"Неизвестный анализатор: {name}")
        try:
            reg.create(name)
        except AnalysisFailure as exc:
            raise ConfigError("analyzers", exc.message) from exc

    return Application(
        config=cfg,
        repository=repo,
        registry=reg,
        submission_service=SubmissionService(repo),
        analysis_service=AnalysisService(repo, reg),
    )