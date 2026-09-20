"""ReqRes (https://reqres.in) client - the ONLY APIs used by this framework:

    POST   /api/login            authenticate, returns a bearer token
    POST   /api/users            create a user
    PUT    /api/users/{id}       full update
    PATCH  /api/users/{id}       partial update
    DELETE /api/users/{id}       delete

/api/login is used by the E2E workflows: the token authenticates the API half of the positive
workflows and the "missing password" case is the API half of the negative workflow.
The same two endpoints (login + create user) are load-tested by performance/k6/.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
from playwright.sync_api import APIRequestContext

from api.base_client import ApiQuotaExceededError, ApiResponse, BaseApiClient, assert_status
from config.settings import settings


class ReqResClient(BaseApiClient):
    USERS = "/api/users"
    LOGIN = "/api/login"

    def __init__(self, request_context: APIRequestContext) -> None:
        headers = {"Accept": "application/json", "User-Agent": "orangehrm-hybrid-automation/1.0"}
        if settings.reqres_api_key:
            headers["x-api-key"] = settings.reqres_api_key
        super().__init__(
            request_context,
            settings.reqres_base_url,
            name="ReqRes",
            default_headers=headers,
            throttle_rules={self.USERS: settings.reqres_users_min_interval},
            default_min_interval=settings.reqres_default_min_interval,
            max_retries_on_429=settings.reqres_max_retries,
            timeout_ms=settings.reqres_timeout_ms,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> ApiResponse:
        expected = kwargs.pop("expected_status", None)
        try:
            response = super().request(method, path, **kwargs)
        except ApiQuotaExceededError as error:
            if settings.reqres_skip_on_quota:
                pytest.skip(f"ReqRes daily quota used up - {error}")
            raise
        if response.status in (401, 403):
            key_state = "is set" if settings.reqres_api_key else "is NOT set"
            raise AssertionError(
                f"ReqRes rejected {method} {path} with {response.status} (REQRES_API_KEY {key_state}). "
                f"Check the key (python tools/check_reqres.py) or remove it with "
                f"'Remove-Item Env:REQRES_API_KEY'. Body: {response.text[:200]}"
            )
        if expected is not None:
            assert_status(response, expected)
        return response

    # ------------------------------------------------------------------ authentication
    def login(self, email: str, password: Optional[str] = None, **kwargs: Any) -> ApiResponse:
        """POST /api/login

        `password=None` sends the request without the field, which is how the
        negative case ('Missing password' -> 400) is exercised.
        """
        payload: dict[str, Any] = {"email": email}
        if password is not None:
            payload["password"] = password
        return self.post(self.LOGIN, json_body=payload, **kwargs)

    @staticmethod
    def bearer_headers(token: str) -> dict[str, str]:
        """Authorization header built from a /api/login token."""
        return {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------ user APIs
    def create_user(self, name: str, job: str, **kwargs: Any) -> ApiResponse:
        """POST /api/users"""
        return self.post(self.USERS, json_body={"name": name, "job": job}, **kwargs)

    def update_user(self, user_id: int | str, name: str, job: str, **kwargs: Any) -> ApiResponse:
        """PUT /api/users/{id}"""
        return self.put(f"{self.USERS}/{user_id}", json_body={"name": name, "job": job}, **kwargs)

    def patch_user(self, user_id: int | str, fields: dict[str, Any], **kwargs: Any) -> ApiResponse:
        """PATCH /api/users/{id}"""
        return self.patch(f"{self.USERS}/{user_id}", json_body=fields, **kwargs)

    def delete_user(self, user_id: int | str, **kwargs: Any) -> ApiResponse:
        """DELETE /api/users/{id}"""
        return self.delete(f"{self.USERS}/{user_id}", **kwargs)
