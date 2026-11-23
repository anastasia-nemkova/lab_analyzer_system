"""
Реестр фабрик анализаторов.

Создаётся в точке сборки приложения и передаётся сервису; сервис не содержит
ветвлений по конкретным классам и не использует глобальное состояние.
"""

from collections.abc import Callable

from lab_analyzer.analyzers import Analyzer
from lab_analyzer.errors import AnalysisFailure


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Analyzer]] = {}

    def register(self, name: str, factory: Callable[[], Analyzer]) -> None:
        if not name or not name.strip():
            raise AnalysisFailure("Требуется непустое имя анализатора")
        if name in self._factories:
            raise AnalysisFailure(f"Анализатор с именем {name!r} уже зарегистрирован")

        self._factories[name] = factory

    def create(self, name: str) -> Analyzer:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise AnalysisFailure(f"Неизвестный анализатор: {name!r}") from exc

        analyzer = factory()

        if analyzer.analyzer_id != name:
            raise AnalysisFailure(
                f"Имя регистрации {name!r} не совпадает с analyzer_id {analyzer.analyzer_id!r}"
            )

        return analyzer

    def __contains__(self, name: str) -> bool:
        return name in self._factories

    def __len__(self) -> int:
        return len(self._factories)

    def names(self) -> tuple[str, ...]:
        return tuple(self._factories.keys())
