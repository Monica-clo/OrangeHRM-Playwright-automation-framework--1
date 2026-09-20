"""The 5 end-to-end Employee Lifecycle workflows - each one combines OrangeHRM UI with the ReqRes API.

This file is the whole functional suite: exactly five workflows, ONE negative and FOUR positive.

| # | Type     | Workflow                        | UI (OrangeHRM)                                          | API (ReqRes)                     |
|---|----------|---------------------------------|---------------------------------------------------------|----------------------------------|
| 1 | NEGATIVE | Rejected authentication         | wrong password -> error -> no session is created       | POST /api/login (no password) -> 400 |
| 2 | positive | Create employee in PIM          | login -> Add Employee + photo + login details -> list   | POST   /api/users      -> 201    |
| 3 | positive | Edit employee                   | search by Id -> personal details + photo -> reload      | PUT    /api/users/{id} -> 200    |
| 4 | positive | Add contact details             | Contact Details tab -> address/phone/email -> reload    | PATCH  /api/users/{id} -> 200    |
| 5 | positive | Job details, delete & logout    | Job tab -> list columns -> delete -> No Records Found   | DELETE /api/users/{id} -> 204    |

Every API response is checked with `api.validators.validate_response()` - status code, JSON
Content-Type, response time, JSON schema, values echoed from the UI data, generated fields,
timestamps (and, for the negative case, the exact error text and the absence of a token).

Each workflow is self-contained: it logs in, creates its own employee with a unique Employee Id,
verifies its own result and cleans up after itself. Any single workflow can be run on its own and a
failure in one never cascades into the others, so they also run in parallel (pytest-xdist).

The positive workflows use the bearer token from POST /api/login (session fixture `reqres_token`,
validated in conftest.py) as the Authorization header of their API call. ReqRes is a public demo API
and does not enforce the header, but the chain login -> token -> authenticated call is what a real
hybrid suite does.

Tags:  e2e (all) | workflow (all) | positive (2-5) | negative (1) | smoke (1, 2) | regression (3, 4, 5)

Run all five:      python -m pytest -m workflow
Only positive:     python -m pytest -m positive
Only negative:     python -m pytest -m negative
Just one:          python -m pytest -k workflow_3
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from api.models import EmployeeSnapshot, assert_snapshots_match
from api.reqres_client import ReqResClient
from api.schemas import CREATED_USER, LOGIN_ERROR, UPDATED_USER
from api.validators import validate_response
from config.settings import settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from pages.personal_details_page import PersonalDetailsPage
from utils.data_models import EmployeeData, random_digits
from utils.data_reader import load_employee_profile, load_employees, load_reqres_data
from utils.logger import get_logger
from utils.screen_recorder import ScreenRecorder

REQRES_DATA = load_reqres_data()
UI_AUTH = REQRES_DATA["auth_ui"]
API_AUTH = REQRES_DATA["auth_apis"]
USER_API = REQRES_DATA["user_apis"]

# The workflows use the first record of employees.json / employees.csv (DATA_SOURCE).
EMPLOYEE_TEMPLATE = load_employees()[0]

log = get_logger("test.workflows")

pytestmark = pytest.mark.workflow


# ============================================================================ fixtures & helpers
@pytest.fixture
def employee() -> EmployeeData:
    """A fresh employee with a unique Employee Id and username for this workflow."""
    return EMPLOYEE_TEMPLATE.with_unique_identifiers()


@pytest.fixture
def auth_headers(reqres_token: str) -> dict[str, str]:
    """Authorization header built from the POST /api/login token (see conftest.reqres_token)."""
    return ReqResClient.bearer_headers(reqres_token)


def create_employee(
    recorder: ScreenRecorder,
    dashboard: DashboardPage,
    employee: EmployeeData,
    created_employee_ids: list[str],
) -> PersonalDetailsPage:
    """Shared setup step: create the employee through PIM > Add Employee and verify it was saved."""
    with recorder.step(
        f"Setup: PIM > Add Employee '{employee.display_name}' (Employee Id {employee.employee_id})"
    ):
        personal_details = dashboard.go_to_pim().go_to_add_employee().add_employee(
            employee, on_saved=lambda: created_employee_ids.append(employee.employee_id)
        )
        personal_details.verify_employee_details(employee)
    return personal_details


def ui_snapshot(employee: EmployeeData, job_title: str = "", employment_status: str = "") -> EmployeeSnapshot:
    return EmployeeSnapshot(
        employee_id=employee.employee_id,
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        last_name=employee.last_name,
        job_title=job_title,
        employment_status=employment_status,
    )


# ============================================================================ workflow 1 (NEGATIVE)
@pytest.mark.negative
@pytest.mark.smoke
def test_workflow_1_negative_rejected_authentication(
    screen_recorder: ScreenRecorder, login_page: LoginPage, reqres: ReqResClient
) -> None:
    """WORKFLOW 1 (negative) - authentication must be REJECTED, on the UI and on the API.

    UI : a valid user name with a wrong password shows 'Invalid credentials', keeps the user on
         the login page and creates no session (a protected URL still redirects to login).
    API: POST /api/login without a password -> 400 with the exact error text and no token.
    """
    invalid_ui = UI_AUTH["invalid_login"]
    case = API_AUTH["login_missing_password"]

    with screen_recorder.step("1.1 UI: open the OrangeHRM login page"):
        login_page.open()

    with screen_recorder.step(f"1.2 UI: submit user '{settings.username}' with a wrong password"):
        login_page.login_expecting_failure(settings.username, invalid_ui["password"])

    with screen_recorder.step(
        f"1.3 UI: verify '{invalid_ui['expected_error']}' is shown and the user stays on the login page"
    ):
        login_page.verify_invalid_credentials_error()

    with screen_recorder.step("1.4 UI: verify no session exists (a protected page redirects to login)"):
        login_page.verify_protected_page_redirects_to_login()

    with screen_recorder.step(
        f"1.5 API: POST {case['endpoint']} without a password -> {case['expected_status']} '{case['expected_error']}'"
    ):
        response = reqres.login(case["payload"]["email"], password=None)
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"POST {case['endpoint']} (missing password)",
            schema=LOGIN_ERROR,
            error=case["expected_error"],
            forbidden=("token",),
        )


# ============================================================================ workflow 2
@pytest.mark.positive
@pytest.mark.smoke
def test_workflow_2_create_employee(
    screen_recorder: ScreenRecorder,
    dashboard: DashboardPage,
    reqres: ReqResClient,
    auth_headers: dict[str, str],
    created_employee_ids: list[str],
    employee: EmployeeData,
) -> None:
    """WORKFLOW 2 - log in, create an employee in PIM (name, Employee Id, profile photo, login
    details) and mirror the created record through POST /api/users."""
    assert employee.profile_picture is not None, (
        f"Test data '{employee.test_id}' must define profile_picture for this workflow"
    )

    with screen_recorder.step("2.1 UI: logged in - the Dashboard is displayed and PIM > Add Employee opens"):
        dashboard.verify_loaded()
        add_employee = dashboard.go_to_pim().go_to_add_employee()

    with screen_recorder.step(
        f"2.2 UI: enter '{employee.display_name}' and Employee Id {employee.employee_id}"
    ):
        add_employee.enter_full_name(employee.first_name, employee.middle_name, employee.last_name)
        add_employee.enter_employee_id(employee.employee_id)

    with screen_recorder.step(f"2.3 UI: click '+' and add the photo '{employee.profile_picture.name}'"):
        add_employee.upload_profile_picture(employee.profile_picture)

    if employee.create_login_details:
        with screen_recorder.step(f"2.4 UI: create login details for '{employee.username}'"):
            add_employee.enter_login_details(employee.username, employee.password, employee.login_status)

    with screen_recorder.step("2.5 UI: Save -> 'Successfully Saved' toast and Personal Details page"):
        personal_details = add_employee.click_save(
            on_saved=lambda: created_employee_ids.append(employee.employee_id)
        )
        personal_details.verify_employee_details(employee)
        personal_details.verify_profile_picture_uploaded()
        personal_details.capture_profile_picture(f"{employee.employee_id}_workflow2_photo")

    with screen_recorder.step("2.6 UI: verify the new record is listed in PIM > Employee List"):
        employee_list = personal_details.go_to_employee_list()
        employee_list.search_by_employee_id(employee.employee_id)
        employee_list.verify_employee_record(
            employee.employee_id, employee.first_name, employee.last_name
        )

    with screen_recorder.step("2.7 UI: read the row from the Employee List and compare it with the test data"):
        ui = employee_list.get_employee_snapshot(employee.employee_id)
        assert_snapshots_match(ui, ui_snapshot(employee), "Employee List (UI) vs test data")

    with screen_recorder.step("2.8 API: POST /api/users with the UI data -> 201 and validate the response"):
        case = USER_API["create_user"]
        payload = {"name": ui.full_name, "job": employee.test_id}
        response = reqres.create_user(payload["name"], payload["job"], headers=auth_headers)
        created = validate_response(
            response,
            status=case["expected_status"],
            api_name="POST /api/users",
            schema=CREATED_USER,
            echo=payload,
            generated=("id",),
            timestamp="createdAt",
        )
        log.info("Employee %s mirrored to the API as user id %s", employee.employee_id, created["id"])


# ============================================================================ workflow 3
@pytest.mark.positive
@pytest.mark.regression
def test_workflow_3_edit_employee(
    screen_recorder: ScreenRecorder,
    dashboard: DashboardPage,
    reqres: ReqResClient,
    auth_headers: dict[str, str],
    created_employee_ids: list[str],
    employee: EmployeeData,
) -> None:
    """WORKFLOW 3 - edit an employee: search by Employee Id, update the Personal Details and the
    profile photo, prove both were persisted, then mirror the update with PUT /api/users/{id}."""
    _, personal_info, _, _ = load_employee_profile()
    create_employee(screen_recorder, dashboard, employee, created_employee_ids)

    with screen_recorder.step(f"3.1 UI: search PIM > Employee List by Employee Id {employee.employee_id}"):
        employee_list = dashboard.go_to_pim()
        employee_list.search_by_employee_id(employee.employee_id)

    with screen_recorder.step("3.2 UI: open the record from the search result"):
        personal_details = employee_list.open_employee_record(employee.employee_id)
        personal_details.verify_employee_details(employee)

    with screen_recorder.step(
        "3.3 UI: update Personal Details (Other Id, Driver's License, Nationality, Marital Status, Gender)"
    ):
        personal_details.update_personal_info(personal_info)

    with screen_recorder.step("3.4 UI: reload and verify the personal details were really saved"):
        personal_details.reload()
        personal_details.verify_loaded()
        personal_details.verify_employee_details(employee)
        personal_details.verify_personal_info(personal_info)

    if employee.edit_profile_picture:
        with screen_recorder.step(f"3.5 UI: change the profile photo to '{employee.edit_profile_picture.name}'"):
            photo_before = personal_details.capture_profile_picture(f"{employee.employee_id}_photo_before")
            size_before = personal_details.get_profile_picture_size()
            change_photo_page = personal_details.open_change_profile_picture()
            change_photo_page.change_photo(employee.edit_profile_picture)

        with screen_recorder.step("3.6 UI: verify the avatar on Personal Details really changed"):
            personal_details = change_photo_page.go_to_personal_details()
            personal_details.verify_profile_picture_uploaded()
            photo_after = personal_details.capture_profile_picture(f"{employee.employee_id}_photo_after")
            size_after = personal_details.get_profile_picture_size()
            assert photo_after != photo_before, (
                "Profile photo did not change: the avatar looks identical before and after the upload"
            )
            assert size_after != size_before, (
                f"Profile photo size should change from {size_before} after the upload, but it is still {size_after}"
            )

    with screen_recorder.step("3.7 API: PUT /api/users/{id} with the updated UI data -> 200 and validate the response"):
        case = USER_API["update_user_put"]
        ui = ui_snapshot(employee)
        payload = {"name": ui.full_name, "job": f"{personal_info.nationality} / {personal_info.marital_status}"}
        response = reqres.update_user(case["user_id"], payload["name"], payload["job"], headers=auth_headers)
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"PUT /api/users/{case['user_id']}",
            schema=UPDATED_USER,
            echo=payload,
            timestamp="updatedAt",
        )


# ============================================================================ workflow 4
@pytest.mark.positive
@pytest.mark.regression
def test_workflow_4_add_contact_details(
    screen_recorder: ScreenRecorder,
    dashboard: DashboardPage,
    reqres: ReqResClient,
    auth_headers: dict[str, str],
    created_employee_ids: list[str],
    employee: EmployeeData,
) -> None:
    """WORKFLOW 4 - add one more set of details to the same employee: the Contact Details tab
    (address, telephone, email), verified after a reload and mirrored with PATCH /api/users/{id}."""
    _, _, contact_template, email_domains = load_employee_profile()
    unique = random_digits(6)
    contact_info = replace(  # the work email must be unique in OrangeHRM
        contact_template,
        work_email=f"{employee.first_name.lower()}.{unique}@{email_domains['work']}",
        other_email=f"{employee.first_name.lower()}.{unique}@{email_domains['other']}",
    )
    personal_details = create_employee(screen_recorder, dashboard, employee, created_employee_ids)

    with screen_recorder.step("4.1 UI: open the Contact Details tab of the employee"):
        contact_details = personal_details.go_to_contact_details()

    with screen_recorder.step(
        f"4.2 UI: fill in Address, Telephone and Email ({contact_info.city}, {contact_info.work_email})"
    ):
        contact_details.update_contact_info(contact_info)

    with screen_recorder.step("4.3 UI: reload and verify every contact field was saved"):
        contact_details.reload()
        contact_details.verify_loaded()
        contact_details.verify_contact_info(contact_info)

    with screen_recorder.step("4.4 UI: verify the employee is still listed with the same Employee Id"):
        employee_list = contact_details.go_to_employee_list()
        employee_list.search_by_employee_id(employee.employee_id)
        employee_list.verify_employee_record(employee.employee_id, employee.first_name, employee.last_name)

    with screen_recorder.step("4.5 API: PATCH /api/users/{id} with the new contact data -> 200 and validate the response"):
        case = USER_API["update_user_patch"]
        payload = {"job": f"{contact_info.city}, {contact_info.country}"}
        response = reqres.patch_user(case["user_id"], payload, headers=auth_headers)
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"PATCH /api/users/{case['user_id']}",
            schema=UPDATED_USER,
            echo=payload,
            timestamp="updatedAt",
        )


# ============================================================================ workflow 5
@pytest.mark.positive
@pytest.mark.regression
def test_workflow_5_job_details_delete_and_logout(
    screen_recorder: ScreenRecorder,
    dashboard: DashboardPage,
    reqres: ReqResClient,
    auth_headers: dict[str, str],
    created_employee_ids: list[str],
    employee: EmployeeData,
) -> None:
    """WORKFLOW 5 - close the lifecycle: set Job Title and Employment Status, cross-check the
    Employee List columns, delete the employee in the UI, confirm the deletion through
    DELETE /api/users/{id} -> 204, and log out."""
    assert employee.job is not None, (
        f"Test data '{employee.test_id}' must define job_title and employment_status"
    )
    personal_details = create_employee(screen_recorder, dashboard, employee, created_employee_ids)

    with screen_recorder.step(
        f"5.1 UI: set Job Title='{employee.job.job_title}' and "
        f"Employment Status='{employee.job.employment_status}'"
    ):
        job_details = personal_details.go_to_job_details()
        job_details.update_job_details(employee.job)

    with screen_recorder.step("5.2 UI: reload and verify the job details were persisted"):
        job_details.reload_and_verify_job_details(employee.job)

    with screen_recorder.step("5.3 UI: verify the updated columns in PIM > Employee List"):
        employee_list = job_details.go_to_employee_list()
        employee_list.search_by_employee_id(employee.employee_id)
        employee_list.verify_employee_record(
            employee.employee_id,
            employee.first_name,
            employee.last_name,
            job_title=employee.job.job_title,
            employment_status=employee.job.employment_status,
        )

    with screen_recorder.step("5.4 UI: cross-check the Employee List row against the test data"):
        ui = employee_list.get_employee_snapshot(employee.employee_id)
        expected = ui_snapshot(employee, employee.job.job_title, employee.job.employment_status)
        assert_snapshots_match(ui, expected, "Employee List (UI) vs test data")

    with screen_recorder.step("5.5 UI: delete the employee and confirm the dialog"):
        employee_list.delete_employee(employee.employee_id)

    with screen_recorder.step("5.6 UI: search again - 'No Records Found' proves the deletion"):
        employee_list = employee_list.go_to_employee_list()
        employee_list.verify_employee_not_found(employee.employee_id)
        created_employee_ids.remove(employee.employee_id)  # nothing left to clean up

    with screen_recorder.step("5.7 API: DELETE /api/users/{id} -> 204 with an empty body"):
        case = USER_API["delete_user"]
        response = reqres.delete_user(case["user_id"], headers=auth_headers)
        validate_response(
            response,
            status=case["expected_status"],
            api_name=f"DELETE /api/users/{case['user_id']}",
            empty_body=True,
        )

    with screen_recorder.step("5.8 UI: log out and verify the session is invalidated"):
        login_page = employee_list.logout()
        login_page.verify_protected_page_redirects_to_login()
