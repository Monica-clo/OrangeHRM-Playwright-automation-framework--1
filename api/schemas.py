"""JSON schemas (response contracts) for the ReqRes APIs used by the E2E workflows."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

# POST /api/users
CREATED_USER = {
    "type": "object",
    "required": ["name", "job", "id", "createdAt"],
    "properties": {
        "name": {"type": "string"},
        "job": {"type": "string"},
        "id": {"type": ["string", "integer"]},
        "createdAt": {"type": "string"},
    },
}

# PUT / PATCH /api/users/{id}
UPDATED_USER = {
    "type": "object",
    "required": ["updatedAt"],
    "properties": {"updatedAt": {"type": "string"}},
}

# POST /api/login  (valid credentials)
# ReqRes answers with {"token": "...", "_meta": {...}}; only "token" is part of the contract.
LOGIN_SUCCESS = {
    "type": "object",
    "required": ["token"],
    "properties": {
        "token": {"type": "string", "minLength": 1},
        "_meta": {"type": "object"},
    },
}

# POST /api/login  (missing/invalid credentials)
LOGIN_ERROR = {
    "type": "object",
    "required": ["error"],
    "properties": {"error": {"type": "string", "minLength": 1}},
}


def assert_schema(instance: Any, schema: dict, name: str) -> None:
    """Validate `instance` and report every violation in one readable message."""
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(
            f"  - at '{'/'.join(map(str, e.path)) or '<root>'}': {e.message}" for e in errors[:10]
        )
        raise AssertionError(f"Response does not match the '{name}' schema:\n{details}")
