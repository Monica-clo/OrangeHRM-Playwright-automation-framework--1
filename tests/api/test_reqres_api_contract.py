"""API-only contract suite - ReqRes endpoints checked on their own, no browser needed.

This is the fast feedback loop: it needs no Playwright browser and no OrangeHRM session,
so it can gate a pull request in seconds before the slower UI workflows start.

It does not repeat the E2E workflows. tests/e2e checks the API as the mirror of a UI
action (the employee created in PIM is posted to /api/users); this file checks the
endpoint contract on its own: status code, JSON content type, response time, schema,
echoed payload, generated ids, fresh timestamps and error bodies.

    1. POST   /api/login          valid credentials  -> 200 + token
    2. POST   /api/login          password missing   -> 400 + error, no token
    3. POST   /api/users          {"name","job"}     -> 201 + id + createdAt
    4. PUT    /api/users/{id}     full update        -> 200 + updatedAt
    5. PATCH  /api/users/{id}     partial update     -> 200 + updatedAt
    6. DELETE /api/users/{id}                        -> 204 + empty body

Inputs and expected values come from test_data/api/reqres_test_data.json.

Run:  python -m pytest -m api
"""
from __future__ import annotations

import pytest

from api.reqres_client import ReqResClient
from api.schemas import CREATED_USER, LOGIN_ERROR, LOGIN_SUCCESS, UPDATED_USER
from api.validators import validate_response
from utils.data_reader import load_reqres_data
from utils.logger import get_logger
from utils.reporting import step

DATA = load_reqres_data()
AUTH = DATA["auth_apis"]
USER_API = DATA["user_apis"]

log = get_logger("test.api")

# The `api` marker is also added automatically by conftest for everything under tests/api.
pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------- 1. login
@pytest.mark.positive
@pytest.mark.smoke
def test_login_returns_a_token(reqres: ReqResClient) -> None:
    """POST /api/login with valid credentials returns a usable bearer token."""
    case = AUTH["login"]
    payload = case["payload"]

    with step(f"POST {case['endpoint']} as {payload['email']}"):
        response = reqres.login(payload["email"], payload["password"])

    with step(f"Validate status {case['expected_status']}, schema and a non-empty token"):
        body = validate_response(
            response,
            status=case["expected_status"],
            api_name=f"POST {case['endpoint']}",
            schema=LOGIN_SUCCESS,
            generated=("token",),
        )
        log.info("Token acquired (%d characters)", len(str(body["token"])))


# ---------------------------------------------------------------------------- 2. login (negative)
@pytest.mark.negative
@pytest.mark.smoke
def test_login_without_password_is_rejected(reqres: ReqResClient) -> None:
    """POST /api/login without a password is refused with 400 and leaks no token."""
    case = AUTH["login_missing_password"]

    with step(f"POST {case['endpoint']} without the password field"):
        response = reqres.login(case["payload"]["email"], password=None)

    with step(f"Validate status {case['expected_status']}, the error text and that no token is returned"):
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"POST {case['endpoint']} (missing password)",
            schema=LOGIN_ERROR,
            error=case["expected_error"],
            forbidden=("token",),
        )


# ---------------------------------------------------------------------------- 3. create
@pytest.mark.positive
@pytest.mark.smoke
def test_create_user(reqres: ReqResClient) -> None:
    """POST /api/users echoes the payload and generates an id plus a createdAt timestamp."""
    case = USER_API["create_user"]
    payload = case["payload"]

    with step(f"POST /api/users with {payload}"):
        response = reqres.create_user(payload["name"], payload["job"])

    with step("Validate status, schema, echoed payload, generated id and createdAt"):
        body = validate_response(
            response,
            status=case["expected_status"],
            api_name="POST /api/users",
            schema=CREATED_USER,
            echo=payload,
            generated=("id",),
            timestamp="createdAt",
        )
        log.info("Created user id %s", body["id"])


# ---------------------------------------------------------------------------- 4. full update
@pytest.mark.positive
@pytest.mark.regression
def test_update_user_put(reqres: ReqResClient) -> None:
    """PUT /api/users/{id} replaces every field and stamps updatedAt."""
    case = USER_API["update_user_put"]
    payload = case["payload"]

    with step(f"PUT /api/users/{case['user_id']} with {payload}"):
        response = reqres.update_user(case["user_id"], payload["name"], payload["job"])

    with step("Validate status, schema, echoed payload and updatedAt"):
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"PUT /api/users/{case['user_id']}",
            schema=UPDATED_USER,
            echo=payload,
            timestamp="updatedAt",
        )


# ---------------------------------------------------------------------------- 5. partial update
@pytest.mark.positive
@pytest.mark.regression
def test_update_user_patch(reqres: ReqResClient) -> None:
    """PATCH /api/users/{id} updates only the fields that were sent."""
    case = USER_API["update_user_patch"]
    payload = case["payload"]

    with step(f"PATCH /api/users/{case['user_id']} with {payload}"):
        response = reqres.patch_user(case["user_id"], payload)

    with step("Validate status, schema, echoed payload and updatedAt"):
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"PATCH /api/users/{case['user_id']}",
            schema=UPDATED_USER,
            echo=payload,
            timestamp="updatedAt",
        )


# ---------------------------------------------------------------------------- 6. delete
@pytest.mark.positive
@pytest.mark.regression
def test_delete_user(reqres: ReqResClient) -> None:
    """DELETE /api/users/{id} answers 204 with no body at all."""
    case = USER_API["delete_user"]

    with step(f"DELETE /api/users/{case['user_id']}"):
        response = reqres.delete_user(case["user_id"])

    with step(f"Validate status {case['expected_status']} and an empty body"):
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"DELETE /api/users/{case['user_id']}",
            empty_body=True,
        )
