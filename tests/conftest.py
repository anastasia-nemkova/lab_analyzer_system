"""Фикстуры pytest"""

import copy
from pathlib import Path
from typing import Any

import pytest

from lab_analyzer.app import Application, build_application
from lab_analyzer.importer import import_source
from lab_analyzer.models import Submission
from lab_analyzer.parsing import parse_submission
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
from lab_analyzer.sources import JSONLSource
from tests.cases import RAW_EXAMPLE


@pytest.fixture
def raw_submission() -> dict[str, Any]:
    return copy.deepcopy(RAW_EXAMPLE)

@pytest.fixture
def submission(raw_submission: dict[str, Any]) -> Submission:
    return parse_submission(raw_submission)

@pytest.fixture
def repository() -> InMemorySubmissionRepository:
    return InMemorySubmissionRepository()

@pytest.fixture
def service(repository: InMemorySubmissionRepository) -> SubmissionService:
    return SubmissionService(repository)

@pytest.fixture
def loaded_app() -> Application:
    corpus = Path(__file__).resolve().parent.parent / "data" / "submissions.jsonl"
    app = build_application()
    import_source(JSONLSource(corpus), app.submission_service)
    return app