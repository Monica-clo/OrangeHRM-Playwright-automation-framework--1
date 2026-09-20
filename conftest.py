"""Global pytest fixtures and hooks.

* browser context per test with video recording + tracing
* failure screenshot and video embedded into the pytest-html report
* the same artifacts attached to Allure
* login / cleanup fixtures used by the tests
"""
from __future__ import annotations

import base64
import os
import shutil
import re
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, expect

from api.reqres_client import ReqResClient
from api.schemas import LOGIN_SUCCESS
from api.validators import validate_response
from config.settings import settings
from pages.dashboard_page import DashboardPage
from pages.employee_list_page import EmployeeListPage
from pages.login_page import LoginPage
from utils.data_reader import load_reqres_data
from utils.image_utils import ensure_png
from utils.logger import get_logger
from utils.screen_recorder import ScreenRecorder, video_file_for

try:
    import allure
except ImportError:
    allure = None

try:
    import pytest_html
except ImportError:
    pytest_html = None

log = get_logger("conftest")


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")[:120]


def _test_failed(node: pytest.Item) -> bool:
    return any(
        getattr(node, f"rep_{phase}", None) is not None and getattr(node, f"rep_{phase}").failed
        for phase in ("setup", "call")
    )


# ============================================================================ hooks
def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # Default browser from config/BROWSER env when --browser is not given on the command line
    if hasattr(config.option, "browser") and not config.option.browser:
        config.option.browser = list(settings.browser_names)

    # Clean old Allure results ONCE in the main process (never inside parallel workers,
    # otherwise one worker would delete the results of the others)
    allure_dir = getattr(config.option, "allure_report_dir", None)
    if allure_dir and not _is_xdist_worker(config):
        shutil.rmtree(allure_dir, ignore_errors=True)

    for folder in (
        settings.html_report_dir,
        settings.videos_dir,
        settings.screenshots_dir,
        settings.traces_dir,
        settings.logs_dir,
        settings.allure_results_dir,
    ):
        folder.mkdir(parents=True, exist_ok=True)
    expect.set_options(timeout=settings.expect_timeout)


_SUITE_MARKERS = {"api": "api", "e2e": "e2e"}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag every test with its suite (`api` or `e2e`) based on the folder it lives in."""
    tests_root = settings.project_root / "tests"
    for item in items:
        try:
            suite = Path(item.path).relative_to(tests_root).parts[0]
        except (ValueError, IndexError):
            continue
        if suite in _SUITE_MARKERS:
            item.add_marker(getattr(pytest.mark, _SUITE_MARKERS[suite]))


def pytest_html_report_title(report) -> None:
    report.title = "OrangeHRM Employee Lifecycle - E2E Workflows (UI + API) Report"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)

    if report.when != "call":
        return
    page: Page | None = item.funcargs.get("page")
    if page is None:
        return

    extras = getattr(report, "extras", [])

    if report.failed:
        try:
            png = page.screenshot(full_page=True)
            (settings.screenshots_dir / f"{_safe_name(item.name)}.png").write_bytes(png)
            if pytest_html:
                extras.append(pytest_html.extras.png(base64.b64encode(png).decode(), name="Failure screenshot"))
            if allure:
                allure.attach(png, name="failure-screenshot", attachment_type=allure.attachment_type.PNG)
        except Exception as exc:  # never hide the real failure
            log.warning("Could not capture failure screenshot: %s", exc)

    if pytest_html and page.video:
        try:
            video_path = video_file_for(item.name)
            relative = os.path.relpath(video_path, settings.html_report_dir).replace(os.sep, "/")
            extras.append(
                pytest_html.extras.html(
                    f'<div><p><b>UI screen recording</b> ({relative})</p>'
                    f'<video src="{relative}" width="640" controls></video></div>'
                )
            )
        except Exception as exc:
            log.warning("Could not link video in HTML report: %s", exc)

    report.extras = extras


# ============================================================================ fixtures
@pytest.fixture(scope="session", autouse=True)
def test_assets() -> None:
    """Make sure the default profile picture exists (generated if missing)."""
    ensure_png(settings.default_profile_picture)


@pytest.fixture(scope="session")
def reqres(playwright: Playwright) -> Generator[ReqResClient, None, None]:
    """Session-wide ReqRes client (no browser needed)."""
    request_context = playwright.request.new_context(ignore_https_errors=True)
    yield ReqResClient(request_context)
    request_context.dispose()


@pytest.fixture(scope="session")
def reqres_token(reqres: ReqResClient) -> str:
    """Bearer token from POST /api/login, fetched once per worker and reused by the API half of
    the positive workflows (one login per session keeps the ReqRes request quota low).

    The login response itself is fully validated: status, JSON content type, response time,
    schema and a non-empty token.
    """
    case = load_reqres_data()["auth_apis"]["login"]
    credentials = case["payload"]
    response = reqres.login(credentials["email"], credentials["password"])
    body = validate_response(
        response,
        status=case["expected_status"],
        api_name=f"POST {case['endpoint']}",
        schema=LOGIN_SUCCESS,
        generated=("token",),
    )
    log.info("Authenticated against ReqRes %s - token acquired", case["endpoint"])
    return str(body["token"])


@pytest.fixture
def context(
    browser: Browser, browser_type_launch_args: dict, request: pytest.FixtureRequest
) -> Generator[BrowserContext, None, None]:
    """Overrides pytest-playwright's context: adds video, tracing and timeouts from config."""
    test_name = _safe_name(request.node.name)
    options: dict = {"viewport": settings.viewport, "ignore_https_errors": True}
    channel = browser_type_launch_args.get("channel", "") or ""
    record_video = settings.record_video and settings.channel_supports_video(channel)
    if settings.record_video and not record_video:
        log.warning("Screen recording is not supported for channel '%s' - recording OFF for %s", channel, test_name)
    if record_video:
        options["record_video_dir"] = str(settings.videos_dir / "_raw" / test_name)
        options["record_video_size"] = settings.viewport

    ctx = browser.new_context(**options)
    # Routing disables the browser HTTP cache for these URLs, so a changed profile
    # photo is always downloaded again instead of showing the cached old one.
    ctx.route("**/pim/viewPhoto/**", lambda route: route.continue_())
    ctx.set_default_timeout(settings.default_timeout)
    ctx.set_default_navigation_timeout(settings.navigation_timeout)

    tracing = settings.tracing != "off"
    if tracing:
        ctx.tracing.start(title=test_name, screenshots=True, snapshots=True, sources=True)

    yield ctx

    failed = _test_failed(request.node)
    if tracing:
        if settings.tracing == "on" or failed:
            trace_file = settings.traces_dir / f"{test_name}.zip"
            ctx.tracing.stop(path=str(trace_file))
            log.info("Trace saved: %s (open with: playwright show-trace %s)", trace_file, trace_file)
            if allure:
                allure.attach.file(str(trace_file), name="playwright-trace", extension="zip")
        else:
            ctx.tracing.stop()

    videos = [p.video for p in ctx.pages if p.video]
    ctx.close()  # the browser finishes writing the videos on close
    for index, video in enumerate(videos):
        final = video_file_for(request.node.name)
        if index:
            final = final.with_name(f"{final.stem}_page{index + 1}.webm")
        try:
            final.parent.mkdir(parents=True, exist_ok=True)
            video.save_as(str(final))
            video.delete()
        except Exception as exc:
            log.warning("Could not rename video (%s) - keeping %s", exc, video.path())
            final = Path(video.path())
        log.info("UI screen recording saved: %s", final)
        raw_dir = settings.videos_dir / "_raw" / test_name
        if raw_dir.is_dir() and not any(raw_dir.iterdir()):
            raw_dir.rmdir()
        if allure:
            allure.attach.file(str(final), name="ui-screen-recording", attachment_type=allure.attachment_type.WEBM)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict, browser_name: str) -> dict:
    """Per-browser launch options.

    * channel: --browser-channel (CLI, applies to all browsers) wins; otherwise
      CHROMIUM_CHANNEL / FIREFOX_CHANNEL from config, so one run can use
      Google Chrome AND installed Firefox together.
    * slow_mo: SLOW_MO_MS from config unless --slowmo was given.
    """
    args = dict(browser_type_launch_args)
    if "channel" not in args and settings.channel_for(browser_name):
        args["channel"] = settings.channel_for(browser_name)
    if settings.slow_mo_ms and not args.get("slow_mo"):
        args["slow_mo"] = settings.slow_mo_ms
    log.info("Launching %s%s", browser_name, f" (channel '{args['channel']}')" if args.get("channel") else "")
    return args


@pytest.fixture
def page(context: BrowserContext) -> Page:
    return context.new_page()


@pytest.fixture
def screen_recorder(page: Page, request: pytest.FixtureRequest) -> ScreenRecorder:
    """On-screen step captions for the recorded video of this test."""
    return ScreenRecorder(page, request.node.name)


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture
def dashboard(login_page: LoginPage) -> DashboardPage:
    """Logged-in session using the configured credentials."""
    return login_page.open().login(settings.username, settings.password)


@pytest.fixture
def created_employee_ids(page: Page) -> Generator[list[str], None, None]:
    """Tests append the Employee Ids they create; optionally deleted after the test."""
    ids: list[str] = []
    yield ids
    if not settings.cleanup_created_employees:
        if ids:
            log.info("Cleanup disabled - employees kept for review: %s", ids)
        return
    for employee_id in ids:
        try:
            EmployeeListPage(page).open().delete_employee(employee_id)
            log.info("Deleted test employee %s", employee_id)
        except Exception as exc:
            log.warning("Cleanup failed for employee %s: %s", employee_id, exc)
