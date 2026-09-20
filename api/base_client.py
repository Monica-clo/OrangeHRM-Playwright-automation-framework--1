"""BaseApiClient - thin wrapper around Playwright's APIRequestContext.

Adds: request/response logging, Allure attachments, client-side throttling,
automatic retry on HTTP 429 (Retry-After aware) and descriptive status assertions.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from playwright.sync_api import APIRequestContext

from utils.logger import get_logger

try:
    import allure
except ImportError:
    allure = None

_MAX_LOGGED_BODY = 2000


@dataclass
class ApiResponse:
    method: str
    url: str
    status: int
    headers: dict[str, str]
    text: str
    elapsed_ms: float
    request_body: Any = None
    body: Any = field(default=None)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        if self.body is None:
            raise AssertionError(f"{self.method} {self.url} did not return a JSON body. Raw body: {self.text[:300]!r}")
        return self.body

    def summary(self) -> str:
        return f"{self.method} {self.url} -> {self.status} ({self.elapsed_ms:.0f} ms)"


class ApiQuotaExceededError(AssertionError):
    """The API refused the call because a daily/long quota is used up - retrying will not help."""


def _long_rate_limit(response: "ApiResponse") -> Optional[str]:
    """Return a readable reason when a 429 is a long (e.g. daily) quota rather than a short burst limit."""
    if response.status != 429:
        return None
    body = response.body if isinstance(response.body, dict) else {}
    retry_after = response.headers.get("retry-after", "")
    long_retry = retry_after.replace(".", "", 1).isdigit() and float(retry_after) > 60
    daily = body.get("remaining") == 0 or "day" in str(body.get("message", "")).lower()
    if not (long_retry or daily):
        return None
    parts = [str(body.get("message") or "Rate limit exceeded")]
    if body.get("resets_in"):
        parts.append(f"Resets in {body['resets_in']}")
    signup = body.get("signup") if isinstance(body.get("signup"), dict) else {}
    if signup.get("url"):
        parts.append(f"Get a free API key: {signup['url']}")
    return " | ".join(parts)


class BaseApiClient:
    def __init__(
        self,
        request_context: APIRequestContext,
        base_url: str,
        *,
        name: str = "API",
        default_headers: Optional[dict[str, str]] = None,
        throttle_rules: Optional[dict[str, float]] = None,
        default_min_interval: float = 0.0,
        max_retries_on_429: int = 0,
        timeout_ms: int = 30000,
    ) -> None:
        self.request_context = request_context
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.default_headers = default_headers or {}
        self.throttle_rules = throttle_rules or {}
        self.default_min_interval = default_min_interval
        self.max_retries_on_429 = max_retries_on_429
        self.timeout_ms = timeout_ms
        self.log = get_logger(f"api.{name}")
        self._last_call: dict[str, float] = {}

    # ------------------------------------------------------------------ internals
    def _throttle(self, path: str) -> None:
        bucket, interval = "default", self.default_min_interval
        for prefix, min_interval in self.throttle_rules.items():
            if path.startswith(prefix):
                bucket, interval = prefix, min_interval
                break
        if interval <= 0:
            return
        wait = interval - (time.monotonic() - self._last_call.get(bucket, 0.0))
        if wait > 0:
            self.log.debug("Throttling %s for %.2fs", bucket, wait)
            time.sleep(wait)
        self._last_call[bucket] = time.monotonic()

    def _attach(self, response: ApiResponse) -> None:
        if allure is None:
            return
        payload = {
            "request": {"method": response.method, "url": response.url, "body": response.request_body},
            "response": {"status": response.status, "elapsed_ms": round(response.elapsed_ms),
                         "body": response.body if response.body is not None else response.text[:_MAX_LOGGED_BODY]},
        }
        allure.attach(json.dumps(payload, indent=2, default=str), name=f"{self.name}: {response.method} {response.url}",
                      attachment_type=allure.attachment_type.JSON)

    # ------------------------------------------------------------------ public API
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[dict[str, str]] = None,
        expected_status: Optional[int] = None,
    ) -> ApiResponse:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        merged_headers = {**self.default_headers, **(headers or {})}
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        attempt = 0
        while True:
            self._throttle(path)
            self.log.info("%s -> %s %s params=%s body=%s", self.name, method, url, clean_params or "-",
                          json.dumps(json_body) if json_body is not None else "-")
            started = time.perf_counter()
            raw = self.request_context.fetch(
                url,
                method=method,
                params=clean_params or None,
                data=json_body,
                headers=merged_headers or None,
                timeout=self.timeout_ms,
                fail_on_status_code=False,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            text = raw.text()
            try:
                body = json.loads(text) if text.strip() else None
            except ValueError:
                body = None
            response = ApiResponse(method, raw.url, raw.status, dict(raw.headers), text, elapsed_ms, json_body, body)

            quota_reason = _long_rate_limit(response)
            if quota_reason:
                self.log.error("%s quota exceeded - not retrying: %s", self.name, quota_reason)
                self._attach(response)
                raise ApiQuotaExceededError(f"{self.name} quota exceeded for {method} {url}: {quota_reason}")
            if response.status == 429 and attempt < self.max_retries_on_429:
                attempt += 1
                retry_after = response.headers.get("retry-after", "")
                delay = min(float(retry_after), 60.0) if retry_after.replace(".", "", 1).isdigit() else 5.0 * attempt
                self.log.warning("%s rate limited (429). Retry %d/%d in %.1fs", self.name, attempt,
                                 self.max_retries_on_429, delay)
                time.sleep(delay)
                continue
            break

        self.log.info("%s <- %s | body=%s", self.name, response.summary(), text[:_MAX_LOGGED_BODY] or "<empty>")
        self._attach(response)
        if expected_status is not None:
            assert_status(response, expected_status)
        return response

    def get(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("DELETE", path, **kwargs)


def assert_status(response: ApiResponse, expected: int | tuple[int, ...]) -> None:
    expected_set = expected if isinstance(expected, tuple) else (expected,)
    assert response.status in expected_set, (
        f"Unexpected HTTP status for {response.method} {response.url}: "
        f"expected {' or '.join(map(str, expected_set))}, got {response.status}. "
        f"Response body: {response.text[:500]!r}"
    )
