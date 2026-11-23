"""Парсинг JSON, DTO и валидация схемы: типы, время, декларация ИИ, структурированные ошибки"""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from lab_analyzer.dto import DeclarationInput, SubmissionInput
from lab_analyzer.errors import INVALID_JSON, SubmissionError
from lab_analyzer.models import AIDeclaration
from lab_analyzer.parsing import decode_json, parse_submission
from tests.cases import RAW_EXAMPLE, VALIDATION_CASES, changed, declaration


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


def test_dto_is_frozen_and_strict() -> None:
    dto = SubmissionInput.model_validate(RAW_EXAMPLE)
    with pytest.raises(ValidationError):
        dto.text = "x"


def test_dto_to_domain_is_independent_of_input() -> None:
    raw = changed()
    sub = parse_submission(raw)
    raw["text"] = "mutated"
    raw["ai_declaration"]["used"] = True
    assert sub.text == RAW_EXAMPLE["text"]
    assert sub.ai_declaration.used is False


@pytest.mark.parametrize(
    "updates",
    [
        {"used": True, "tool": "t", "purpose": None},
        {"used": True, "tool": None, "purpose": "p"},
        {"used": False, "tool": " ", "purpose": None},
        {"used": False, "tool": None, "purpose": "\n"},
    ],
)
def test_declaration_invalid_combinations(updates: dict[str, Any]) -> None:
    with pytest.raises(SubmissionError) as caught:
        parse_submission(changed(ai_declaration=declaration(**updates)))
    assert caught.value.code == "schema_error"
    assert caught.value.field.startswith("ai_declaration")


def test_declaration_used_with_tool_and_purpose_ok() -> None:
    sub = parse_submission(
        changed(ai_declaration=declaration(used=True, tool="помощник", purpose="идея"))
    )
    assert sub.ai_declaration.tool == "помощник"


def test_declaration_dto_to_domain() -> None:
    dto = DeclarationInput(used=False, tool=None, purpose=None, verified_by_student=True)
    assert dto.to_domain() == AIDeclaration(False, None, None, True)


@pytest.mark.parametrize("stamp", ["2026-09-01T07:01:00Z", "2026-09-01T10:01:00+03:00"])
def test_timestamp_with_zone_accepted(stamp: str) -> None:
    assert parse_submission(changed(submitted_at=stamp)).submitted_at == stamp


@pytest.mark.parametrize("stamp", ["", "   ", "вчера", "2026-13-40T00:00:00+00:00", 20260901])
def test_timestamp_invalid(stamp: object) -> None:
    with pytest.raises(SubmissionError) as caught:
        parse_submission(changed(submitted_at=stamp))
    assert caught.value.field == "submitted_at"


@pytest.mark.parametrize("version", [0, -1, 1.0, "1", None])
def test_schema_version_must_be_exactly_int_one(version: object) -> None:
    with pytest.raises(SubmissionError) as caught:
        parse_submission(changed(schema_version=version))
    assert caught.value.field == "schema_version"


def test_text_only_and_code_only_submissions_are_valid() -> None:
    assert parse_submission(changed(code="")).code == ""
    assert parse_submission(changed(text="")).text == ""


def test_text_and_code_are_not_normalised() -> None:
    sub = parse_submission(changed(text="  a\r\n\tb  \n", code="\n\nx = 1  "))
    assert sub.text == "  a\r\n\tb  \n" and sub.code == "\n\nx = 1  "


def test_template_id_may_be_none() -> None:
    assert parse_submission(changed(template_id=None)).template_id is None


def test_decode_json_ok_and_unicode() -> None:
    assert decode_json('{"a": "дом", "n": [1, 2]}') == {"a": "дом", "n": [1, 2]}


@pytest.mark.parametrize("line", ["", "   ", "{", "{'a': 1}", '{"a": 1,}', "nul"])
def test_decode_json_syntax_errors(line: str) -> None:
    with pytest.raises(SubmissionError) as caught:
        decode_json(line)
    assert caught.value.code == INVALID_JSON


@pytest.mark.parametrize("line", ["[]", "1", '"text"', "null", "true"])
def test_decode_json_requires_object(line: str) -> None:
    with pytest.raises(SubmissionError) as caught:
        decode_json(line)
    assert caught.value.code == INVALID_JSON


@pytest.mark.parametrize("constant", ["Infinity", "-Infinity", "NaN"])
def test_decode_json_rejects_nonstandard_constants(constant: str) -> None:
    with pytest.raises(SubmissionError) as caught:
        decode_json(f'{{"x": {constant}}}')
    assert caught.value.code == INVALID_JSON


def test_decode_json_rejects_nested_duplicate_keys() -> None:
    with pytest.raises(SubmissionError) as caught:
        decode_json('{"outer": {"k": 1, "k": 2}}')
    assert caught.value.field == "k"


def test_submission_error_to_dict_and_repr() -> None:
    err = SubmissionError("c", "f", "m")
    assert err.to_dict() == {"code": "c", "field": "f", "message": "m"}
    assert "code = 'c'" in repr(err) and str(err) == "m"


def test_parse_error_chains_original_exception() -> None:
    with pytest.raises(SubmissionError) as caught:
        parse_submission(changed(code=1))
    assert caught.value.__cause__ is not None
