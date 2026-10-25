"""
Фикстуры pytest
"""
import copy
from typing import Any

import pytest

from lab_analyzer.models import Submission
from lab_analyzer.parsing import parse_submission
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
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