"""
Фикстуры pytest
"""
import copy
from typing import Any

import pytest

from tests.cases import RAW_EXAMPLE


@pytest.fixture
def raw_submission() -> dict[str, Any]:
    return copy.deepcopy(RAW_EXAMPLE)