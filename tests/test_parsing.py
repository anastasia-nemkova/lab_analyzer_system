"""
Тесты парсинга JSON и валидации схемы
"""
import json
from typing import Any

import pytest

from lab_analyzer.errors import INVALID_JSON, SubmissionError
from lab_analyzer.parsing import decode_json, parse_submission
from tests.cases import VALIDATION_CASES


def test_decode_json_reject_duplicate_keys() -> None:
    json_line = '{"student_id": "a", "student_id": "b"}'
    with pytest.raises(SubmissionError) as exc_info:
        decode_json(json_line)

    assert exc_info.value.code == INVALID_JSON
    assert exc_info.value.field == "student_id"

def test_decode_json_reject_nan() -> None:
    json_line ='{"score": NaN}'
    with pytest.raises(SubmissionError) as exc_info:
            decode_json(json_line)

    assert exc_info.value.code == INVALID_JSON

@pytest.mark.parametrize(
    "case_id, raw, expected_code, expected_field",
    VALIDATION_CASES,
    ids=[case[0] for case in VALIDATION_CASES]
)

def test_parse_rejects_invalid_schema(case_id: str, 
                                    raw: dict[str, Any], 
                                    expected_code: str, 
                                    expected_field: str
                                    ) -> None:
    with pytest.raises(SubmissionError) as exc_info:
        parse_submission(raw)

    assert exc_info.value.code == expected_code, f"Failed case: {case_id}"
    assert exc_info.value.field == expected_field, f"Failed case: {case_id}"

def test_parse_accepts_valid_submission(raw_submission: dict[str, Any]) -> None:
    submission = parse_submission(raw_submission)
    assert submission.submission_id == "sub-001"
    assert submission.ai_declaration.used is False

def test_input_not_mutated_on_error(raw_submission: dict[str,Any]) -> None:
    raw_submission["student_id"] = ""
    before = json.dumps(raw_submission, sort_keys=True)
    with pytest.raises(SubmissionError):
        parse_submission(raw_submission)
    after = json.dumps(raw_submission, sort_keys=True)
    assert before == after