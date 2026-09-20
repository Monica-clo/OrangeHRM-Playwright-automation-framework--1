"""PIM > Add Employee page object (screenshots 1 & 2)."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from locators.common_locators import Messages
from locators.pim_locators import AddEmployeeLocators as L
from pages.pim_base_page import PimBasePage
from utils.data_models import EmployeeData
from utils.image_utils import validate_profile_photo


class AddEmployeePage(PimBasePage):
    URL_PATH = "/web/index.php/pim/addEmployee"
    URL_PATTERN = re.compile(r"/pim/addEmployee")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.page_title = page.locator(L.PAGE_TITLE)
        self.first_name_input = page.locator(L.FIRST_NAME_INPUT)
        self.middle_name_input = page.locator(L.MIDDLE_NAME_INPUT)
        self.last_name_input = page.locator(L.LAST_NAME_INPUT)
        self.employee_id_input = page.locator(L.EMPLOYEE_ID_INPUT)
        self.add_picture_button = page.locator(L.ADD_PROFILE_PICTURE_BUTTON)
        self.profile_picture_input = page.locator(L.PROFILE_PICTURE_FILE_INPUT)
        self.profile_picture_hint = page.locator(L.PROFILE_PICTURE_HINT)
        self.profile_picture_preview = page.locator(L.PROFILE_PICTURE_PREVIEW)
        self.create_login_toggle = page.locator(L.CREATE_LOGIN_DETAILS_TOGGLE)
        self.create_login_checkbox = page.locator(L.CREATE_LOGIN_DETAILS_CHECKBOX)
        self.username_input = page.locator(L.USERNAME_INPUT)
        self.password_input = page.locator(L.PASSWORD_INPUT)
        self.confirm_password_input = page.locator(L.CONFIRM_PASSWORD_INPUT)
        self.cancel_button = page.locator(L.CANCEL_BUTTON)
        self.save_button = page.locator(L.SAVE_BUTTON)

    # ------------------------------------------------------------------ page state
    def open(self) -> "AddEmployeePage":
        self.navigate(self.URL_PATH)
        self.verify_loaded()
        return self

    def verify_loaded(self) -> "AddEmployeePage":
        expect(self.page, "Add Employee page should be opened").to_have_url(self.URL_PATTERN)
        expect(self.page_title, "'Add Employee' title should be visible").to_be_visible()
        # OrangeHRM auto-fills the next Employee Id asynchronously (e.g. '0465').
        # Wait for it, otherwise it can overwrite the value we type.
        expect(
            self.employee_id_input, "Employee Id should be auto-generated before editing the form"
        ).to_have_value(re.compile(r"\S+"))
        return self

    # ------------------------------------------------------------------ form actions
    def enter_full_name(self, first_name: str, middle_name: str, last_name: str) -> None:
        self.fill(self.first_name_input, first_name, "First Name")
        if middle_name:
            self.fill(self.middle_name_input, middle_name, "Middle Name")
        self.fill(self.last_name_input, last_name, "Last Name")

    def enter_employee_id(self, employee_id: str) -> None:
        self.fill(self.employee_id_input, employee_id, "Employee Id")

    def upload_profile_picture(self, image_path: Path) -> None:
        """Click the orange '+' on the avatar, pick the photo in the file chooser, check the preview."""
        validate_profile_photo(image_path)
        expect(self.profile_picture_hint, "Photo hint 'Accepts jpg, .png, .gif up to 1MB' should be shown").to_be_visible()
        self.log.info("Add profile picture: %s", image_path)
        try:
            with self.page.expect_file_chooser(timeout=10_000) as chooser_info:
                self.click(self.add_picture_button.first, "Add profile picture (+) button")
            chooser_info.value.set_files(str(image_path))
        except (PlaywrightTimeoutError, AssertionError) as error:
            # Fallback keeps the test running if the '+' button markup changes
            self.log.warning("File chooser did not open (%s) - setting the file on the hidden input", error)
            self.profile_picture_input.set_input_files(str(image_path))
        expect(
            self.profile_picture_preview,
            f"Avatar preview should show '{image_path.name}' after it is added",
        ).to_have_attribute("src", re.compile(r"^data:image/"))
        self.log.info("Profile picture added successfully: %s", image_path.name)

    def enable_create_login_details(self) -> None:
        if not self.create_login_checkbox.is_checked():
            self.click(self.create_login_toggle, "Create Login Details toggle")
        expect(self.create_login_checkbox, "Create Login Details toggle should be ON").to_be_checked()
        expect(
            self.username_input, "Username field should appear after enabling Create Login Details"
        ).to_be_visible()

    def enter_login_details(self, username: str, password: str, status: str = "Enabled") -> None:
        self.enable_create_login_details()
        self.fill(self.username_input, username, "Username")
        self.select_radio(status, f"Status '{status}' radio")
        self.fill(self.password_input, password, "Password", secret=True)
        self.fill(self.confirm_password_input, password, "Confirm Password", secret=True)

    def click_save(self, on_saved=None):
        """Click Save. `on_saved()` is called right after the save is confirmed, before the
        next page is checked - so tests can register the employee for cleanup even if that check fails."""
        from pages.personal_details_page import PersonalDetailsPage

        self.click(self.save_button, "Save button")
        try:
            self.expect_toast(Messages.SUCCESSFULLY_SAVED, "'Successfully Saved' toast")
        except AssertionError as error:
            errors = self.get_field_errors()
            raise AssertionError(
                f"Employee was not saved. Validation errors on the form: {errors or 'none shown'}"
            ) from error
        if on_saved is not None:
            on_saved()
        personal_details = PersonalDetailsPage(self.page)
        personal_details.verify_loaded()
        return personal_details

    # ------------------------------------------------------------------ business flow
    def add_employee(self, employee: EmployeeData, on_saved=None):
        """Fill the Add Employee form (name, Employee Id, profile photo, optional login) and save it."""
        if not employee.employee_id:
            raise ValueError("Call EmployeeData.with_unique_identifiers() before adding the employee")
        self.enter_full_name(employee.first_name, employee.middle_name, employee.last_name)
        self.enter_employee_id(employee.employee_id)
        if employee.profile_picture:
            self.upload_profile_picture(employee.profile_picture)
        if employee.create_login_details:
            self.enter_login_details(employee.username, employee.password, employee.login_status)
        return self.click_save(on_saved)
