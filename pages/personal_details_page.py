"""Employee profile > Personal Details page object (screenshots 3 & 4)."""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from locators.common_locators import Messages
from locators.pim_locators import PersonalDetailsLocators as L
from pages.employee_profile_base_page import EmployeeProfileBasePage
from utils.data_models import EmployeeData, PersonalInfo

_UPDATED = re.compile(rf"{Messages.SUCCESSFULLY_UPDATED}|{Messages.SUCCESSFULLY_SAVED}")


class PersonalDetailsPage(EmployeeProfileBasePage):
    URL_PATTERN = re.compile(r"/pim/viewPersonalDetails/empNumber/\d+")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.page_title = page.locator(L.PAGE_TITLE)
        self.first_name_input = page.locator(L.FIRST_NAME_INPUT)
        self.middle_name_input = page.locator(L.MIDDLE_NAME_INPUT)
        self.last_name_input = page.locator(L.LAST_NAME_INPUT)
        self.employee_id_input = page.locator(L.EMPLOYEE_ID_INPUT)
        self.other_id_input = page.locator(L.OTHER_ID_INPUT)
        self.drivers_license_input = page.locator(L.DRIVERS_LICENSE_NUMBER_INPUT)
        self.license_expiry_date_input = page.locator(L.LICENSE_EXPIRY_DATE_INPUT)
        self.nationality_dropdown = page.locator(L.NATIONALITY_DROPDOWN)
        self.marital_status_dropdown = page.locator(L.MARITAL_STATUS_DROPDOWN)
        self.date_of_birth_input = page.locator(L.DATE_OF_BIRTH_INPUT)
        self.save_button = page.locator(L.PERSONAL_DETAILS_SAVE_BUTTON)
        self.blood_type_dropdown = page.locator(L.BLOOD_TYPE_DROPDOWN)
        self.custom_fields_save_button = page.locator(L.CUSTOM_FIELDS_SAVE_BUTTON)

    def verify_loaded(self) -> "PersonalDetailsPage":
        expect(self.page, "Personal Details page should be opened").to_have_url(self.URL_PATTERN)
        try:
            expect(self.page_title, "'Personal Details' title should be visible").to_be_visible()
        except AssertionError:
            # The shared demo site sometimes leaves the page half-loaded under load - reload once
            self.log.warning("Personal Details did not render in time - reloading once: %s", self.page.url)
            self.page.reload(wait_until="domcontentloaded")
            expect(
                self.page_title, "'Personal Details' title should be visible (after one reload)"
            ).to_be_visible()
        self.wait_for_page_ready()
        expect(self.first_name_input, "Personal details should finish loading").not_to_have_value("")
        return self

    # ------------------------------------------------------------------ verification
    def verify_employee_details(self, employee: EmployeeData) -> None:
        self.verify_employee_name_header(employee.display_name)
        self.verify_input_value(self.first_name_input, employee.first_name, "First Name")
        self.verify_input_value(self.middle_name_input, employee.middle_name, "Middle Name")
        self.verify_input_value(self.last_name_input, employee.last_name, "Last Name")
        self.verify_input_value(self.employee_id_input, employee.employee_id, "Employee Id")

    def verify_personal_info(self, info: PersonalInfo) -> None:
        if info.other_id:
            self.verify_input_value(self.other_id_input, info.other_id, "Other Id")
        if info.drivers_license_number:
            self.verify_input_value(
                self.drivers_license_input, info.drivers_license_number, "Driver's License Number"
            )
        if info.nationality:
            self.verify_dropdown_value(self.nationality_dropdown, info.nationality, "Nationality")
        if info.marital_status:
            self.verify_dropdown_value(self.marital_status_dropdown, info.marital_status, "Marital Status")
        if info.gender:
            self.verify_radio_selected(info.gender)

    # ------------------------------------------------------------------ actions
    def update_personal_info(self, info: PersonalInfo) -> "PersonalDetailsPage":
        if info.other_id:
            self.fill(self.other_id_input, info.other_id, "Other Id")
        if info.drivers_license_number:
            self.fill(self.drivers_license_input, info.drivers_license_number, "Driver's License Number")
        if info.nationality:
            self.select_dropdown_option(self.nationality_dropdown, info.nationality, "Nationality")
        if info.marital_status:
            self.select_dropdown_option(self.marital_status_dropdown, info.marital_status, "Marital Status")
        if info.gender:
            self.select_radio(info.gender, f"Gender '{info.gender}' radio")
        self.click(self.save_button, "Personal Details Save button")
        self.expect_toast(_UPDATED, "Personal details update toast")
        return self
