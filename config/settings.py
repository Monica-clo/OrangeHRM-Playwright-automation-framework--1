"""Loads config/config.yaml and applies environment-variable overrides.

Usage anywhere in the framework:
    from config.settings import settings
    settings.base_url
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _env(name: str, default: Any) -> Any:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return bool(default)
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    base_url: str
    login_path: str
    dashboard_path: str
    reqres_base_url: str
    reqres_api_key: str
    reqres_users_min_interval: float
    reqres_default_min_interval: float
    reqres_max_retries: int
    reqres_skip_on_quota: bool
    reqres_timeout_ms: int
    api_max_response_ms: float
    username: str
    password: str
    default_timeout: int
    navigation_timeout: int
    expect_timeout: int
    browser_names: tuple
    browser_channels: dict
    viewport: dict
    record_video: bool
    video_captions: bool
    slow_mo_ms: int
    tracing: str
    data_source: str
    json_data_file: Path
    csv_data_file: Path
    profile_data_file: Path
    reqres_data_file: Path
    cleanup_created_employees: bool
    reports_dir: Path
    project_root: Path = PROJECT_ROOT

    @property
    def browser_name(self) -> str:
        """First configured browser (used by the standalone script)."""
        return self.browser_names[0] if self.browser_names else "chromium"

    def channel_for(self, browser_name: str) -> str:
        return self.browser_channels.get(browser_name, "")

    @staticmethod
    def channel_supports_video(channel: str) -> bool:
        """Playwright's WebDriver-BiDi mode for installed Firefox ('moz-firefox*') cannot record video."""
        return not channel.startswith("moz-")

    @property
    def html_report_dir(self) -> Path:
        return self.reports_dir / "html"

    @property
    def videos_dir(self) -> Path:
        return self.reports_dir / "videos"

    @property
    def screenshots_dir(self) -> Path:
        return self.reports_dir / "screenshots"

    @property
    def traces_dir(self) -> Path:
        return self.reports_dir / "traces"

    @property
    def logs_dir(self) -> Path:
        return self.reports_dir / "logs"

    @property
    def allure_results_dir(self) -> Path:
        return self.reports_dir / "allure-results"

    @property
    def default_profile_picture(self) -> Path:
        return self.project_root / "test_data" / "images" / "profile_picture.png"


def load_settings(config_file: Path = CONFIG_FILE) -> Settings:
    with open(config_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    app = raw.get("app", {})
    reqres = raw.get("reqres", {})
    creds = raw.get("credentials", {})
    timeouts = raw.get("timeouts", {})
    browser = raw.get("browser", {})
    data = raw.get("test_data", {})
    reports = raw.get("reports", {})

    return Settings(
        base_url=str(_env("ORANGEHRM_BASE_URL", app.get("base_url", ""))).rstrip("/"),
        login_path=str(_env("ORANGEHRM_LOGIN_PATH", app.get("login_path", "/web/index.php/auth/login"))),
        dashboard_path=str(_env("ORANGEHRM_DASHBOARD_PATH", app.get("dashboard_path", "/web/index.php/dashboard/index"))),
        reqres_base_url=str(_env("REQRES_BASE_URL", reqres.get("base_url", "https://reqres.in"))).rstrip("/"),
        reqres_api_key=str(_env("REQRES_API_KEY", reqres.get("api_key", "") or "")),
        reqres_users_min_interval=float(_env("REQRES_USERS_MIN_INTERVAL", reqres.get("users_min_interval_sec", 3.2))),
        reqres_default_min_interval=float(_env("REQRES_DEFAULT_MIN_INTERVAL", reqres.get("default_min_interval_sec", 0.0))),
        reqres_max_retries=int(_env("REQRES_MAX_RETRIES", reqres.get("max_retries_on_429", 3))),
        reqres_skip_on_quota=_env_bool("REQRES_SKIP_ON_QUOTA", reqres.get("skip_on_quota", False)),
        reqres_timeout_ms=int(_env("REQRES_TIMEOUT_MS", reqres.get("timeout_ms", 30000))),
        api_max_response_ms=float(_env("API_MAX_RESPONSE_MS", reqres.get("max_response_ms", 5000))),
        username=str(_env("ORANGEHRM_USERNAME", creds.get("username", ""))),
        password=str(_env("ORANGEHRM_PASSWORD", creds.get("password", ""))),
        default_timeout=int(_env("DEFAULT_TIMEOUT", timeouts.get("default", 20000))),
        navigation_timeout=int(_env("NAVIGATION_TIMEOUT", timeouts.get("navigation", 45000))),
        expect_timeout=int(_env("EXPECT_TIMEOUT", timeouts.get("expect", 20000))),
        browser_names=tuple(
            name.strip()
            for name in str(_env("BROWSER", browser.get("name", "chromium"))).lower().replace(";", ",").split(",")
            if name.strip()
        ),
        browser_channels={
            "chromium": str(_env("CHROMIUM_CHANNEL", (browser.get("channels") or {}).get("chromium", "")) or ""),
            "firefox": str(_env("FIREFOX_CHANNEL", (browser.get("channels") or {}).get("firefox", "")) or ""),
            "webkit": "",
        },
        viewport={
            "width": int(_env("VIEWPORT_WIDTH", browser.get("viewport_width", 1366))),
            "height": int(_env("VIEWPORT_HEIGHT", browser.get("viewport_height", 768))),
        },
        record_video=_env_bool("RECORD_VIDEO", browser.get("record_video", True)),
        video_captions=_env_bool("VIDEO_CAPTIONS", browser.get("video_captions", True)),
        slow_mo_ms=int(_env("SLOW_MO_MS", browser.get("slow_mo_ms", 0))),
        tracing=str(_env("TRACING", browser.get("tracing", "retain-on-failure"))).lower(),
        data_source=str(_env("DATA_SOURCE", data.get("source", "json"))).lower(),
        json_data_file=PROJECT_ROOT / _env("JSON_DATA_FILE", data.get("json_file", "test_data/employees.json")),
        csv_data_file=PROJECT_ROOT / _env("CSV_DATA_FILE", data.get("csv_file", "test_data/employees.csv")),
        profile_data_file=PROJECT_ROOT / _env("PROFILE_DATA_FILE", data.get("profile_file", "test_data/employee_profile.json")),
        reqres_data_file=PROJECT_ROOT / _env("REQRES_DATA_FILE", data.get("reqres_file", "test_data/api/reqres_test_data.json")),
        cleanup_created_employees=_env_bool("CLEANUP_CREATED_EMPLOYEES", data.get("cleanup_created_employees", True)),
        reports_dir=PROJECT_ROOT / _env("REPORTS_DIR", reports.get("root", "reports")),
    )


settings = load_settings()
