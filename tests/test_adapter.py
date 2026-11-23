"""Адаптер accept_payload: DTO → домен → приём, отображение ошибок домена в статусы"""

import json

import pytest

from lab_analyzer.adapters import STATUS_BY_ERROR_CODE, PayloadResponse, accept_payload
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
from tests.cases import changed


def test_status_table_covers_all_domain_codes() -> None:
    assert STATUS_BY_ERROR_CODE == {
        "invalid_json": 400, "schema_error": 400, "unsupported_version": 400, "conflict": 409,
    }


def test_unknown_error_code_maps_to_400() -> None:
    assert STATUS_BY_ERROR_CODE.get("something_new", 400) == 400


def test_adapter_response_shapes(service: SubmissionService) -> None:
    ok = accept_payload(service, changed())
    assert isinstance(ok, PayloadResponse)
    assert set(ok.body) == {"status", "submission_id", "content_hash"}
    assert len(ok.body["content_hash"]) == 64
    err = accept_payload(service, changed(student_id=""))
    assert set(err.body) == {"error"}
    assert set(err.body["error"]) == {"code", "field", "message"}


def test_adapter_duplicate_returns_same_hash(service: SubmissionService) -> None:
    first = accept_payload(service, changed())
    again = accept_payload(service, changed())
    assert again.body["content_hash"] == first.body["content_hash"]


def test_adapter_error_does_not_change_state(
    service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    accept_payload(service, changed(student_id=""))
    assert len(repository) == 0


def test_adapter_response_is_frozen() -> None:
    response = PayloadResponse(200, {})
    with pytest.raises(AttributeError):
        response.status = 500


def test_adapter_does_not_mutate_payload(service: SubmissionService) -> None:
    payload = changed()
    before = json.dumps(payload, sort_keys=True)
    accept_payload(service, payload)
    assert json.dumps(payload, sort_keys=True) == before


def test_accept_payload_statuses() -> None:
    service = SubmissionService(InMemorySubmissionRepository())
    created = accept_payload(service, changed())
    assert (created.status, created.body["status"]) == (201, "accepted")
    again = accept_payload(service, changed())
    assert (again.status, again.body["status"]) == (200, "duplicate")
    conflict = accept_payload(service, changed(text="Другая версия"))
    assert conflict.status == 409 and conflict.body["error"]["code"] == "conflict"
    invalid = accept_payload(service, changed(student_id=""))
    assert invalid.status == 400 and invalid.body["error"]["field"] == "student_id"
    version = accept_payload(service, changed(schema_version=2))
    assert version.status == 400 and version.body["error"]["code"] == "unsupported_version"
