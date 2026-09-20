"""Reusable API response validation.

Every API call made by the E2E workflows is checked with `validate_response()`, so a
response is never accepted on its status code alone. One call verifies, in this order:

    1. status code                      (exactly the expected one)
    2. Content-Type header              (JSON, or no body at all for 204 responses)
    3. response time                    (below API_MAX_RESPONSE_MS)
    4. JSON schema / contract           (api/schemas.py)
    5. values echoed from the request   (what the UI sent must come back unchanged)
    6. generated fields                 (e.g. `id` non-empty, `createdAt` is a fresh ISO timestamp)
    7. error message and forbidden keys (negative cases, e.g. no `token` in an error response)

The individual `assert_*` helpers are public as well, in case a test needs only one check.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from api.base_client import ApiResponse
from api.schemas import assert_schema
from config.settings import settings

_MAX_BODY_IN_MESSAGE = 300


def _body_hint(response: ApiResponse) -> str:
    return f"Response body: {response.text[:_MAX_BODY_IN_MESSAGE]!r}"


# ============================================================================ single checks
def assert_status_code(response: ApiResponse, expected: int) -> None:
    assert response.status == expected, (
        f"{response.method} {response.url}: expected status code {expected}, "
        f"but got {response.status}. {_body_hint(response)}"
    )


def assert_json_content_type(response: ApiResponse) -> None:
    content_type = next((v for k, v in response.headers.items() if k.lower() == "content-type"), "")
    assert "application/json" in content_type.lower(), (
        f"{response.method} {response.url}: expected a JSON Content-Type, got {content_type!r}"
    )


def assert_response_time(response: ApiResponse, max_ms: Optional[float] = None) -> None:
    limit = settings.api_max_response_ms if max_ms is None else max_ms
    assert response.elapsed_ms <= limit, (
        f"{response.method} {response.url}: responded in {response.elapsed_ms:.0f} ms, "
        f"limit is {limit:.0f} ms"
    )


def assert_empty_body(response: ApiResponse) -> None:
    assert response.text.strip() == "", (
        f"{response.method} {response.url}: expected an empty body, got {response.text[:_MAX_BODY_IN_MESSAGE]!r}"
    )


def assert_fields_echoed(body: dict, expected: dict, api_name: str) -> None:
    """Every field sent in the request must come back with the same value."""
    mismatches = [
        f"  - {field}: sent {value!r}, API returned {body.get(field)!r}"
        for field, value in expected.items()
        if body.get(field) != value
    ]
    assert not mismatches, f"{api_name} response does not match the data that was sent:\n" + "\n".join(mismatches)


def assert_fields_present(body: dict, fields: Iterable[str], api_name: str) -> None:
    """Generated fields (id, token ...) must exist and must not be blank."""
    blank = [f for f in fields if str(body.get(f, "")).strip() == ""]
    assert not blank, f"{api_name} response has missing or empty field(s) {blank}: {body}"


def assert_fields_absent(body: dict, fields: Iterable[str], api_name: str) -> None:
    """Negative cases: e.g. a rejected login must not leak a token."""
    present = [f for f in fields if f in body]
    assert not present, f"{api_name} response must not contain {present}: {body}"


def assert_recent_timestamp(body: dict, field: str, max_age: timedelta = timedelta(days=1)) -> None:
    """The timestamp must be a valid ISO-8601 date close to the current time."""
    value = body.get(field)
    assert value, f"'{field}' is missing in the response: {body}"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise AssertionError(f"'{field}' is not a valid ISO-8601 timestamp: {value!r}") from None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = abs(datetime.now(timezone.utc) - timestamp)
    assert age < max_age, f"'{field}' should be close to now, got {value!r}"


# ============================================================================ all-in-one
def validate_response(
    response: ApiResponse,
    *,
    status: int,
    api_name: str = "",
    schema: Optional[dict] = None,
    echo: Optional[dict] = None,
    generated: Iterable[str] = (),
    timestamp: Optional[str] = None,
    error: Optional[str] = None,
    forbidden: Iterable[str] = (),
    empty_body: bool = False,
    max_ms: Optional[float] = None,
) -> Any:
    """Validate a response completely and return its parsed JSON body (None for empty bodies).

    status     expected HTTP status code
    schema     JSON schema the body must satisfy
    echo       {field: value} that the body must repeat unchanged
    generated  fields the server generates (must be present and non-blank)
    timestamp  name of an ISO-8601 field that must be close to 'now'
    error      exact text expected in the body's "error" field (negative cases)
    forbidden  fields that must NOT be in the body (negative cases)
    empty_body True for 204 responses: no body, and therefore no JSON checks
    """
    name = api_name or f"{response.method} {response.url}"

    assert_status_code(response, status)
    assert_response_time(response, max_ms)

    if empty_body:
        assert_empty_body(response)
        return None

    assert_json_content_type(response)
    body = response.json()
    if schema is not None:
        assert_schema(body, schema, name)
    if echo:
        assert_fields_echoed(body, echo, name)
    if generated:
        assert_fields_present(body, generated, name)
    if timestamp:
        assert_recent_timestamp(body, timestamp)
    if error is not None:
        assert body.get("error") == error, f"{name}: expected the error {error!r}, got {body.get('error')!r}"
    if forbidden:
        assert_fields_absent(body, forbidden, name)
    return body
