"""Shared behaviour for the employee profile tabs (Personal Details, Contact Details, Job ...)."""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from config.settings import settings
from locators.pim_locators import ChangeProfilePictureLocators as L
from pages.pim_base_page import PimBasePage
from utils.reporting import attach_png

_EMP_NUMBER = re.compile(r"/empNumber/(\d+)")


class EmployeeProfileBasePage(PimBasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.employee_name_header = page.locator(L.EMPLOYEE_NAME_HEADER)
        self.profile_picture = page.locator(L.PROFILE_PICTURE)

    @property
    def emp_number(self) -> str:
        match = _EMP_NUMBER.search(self.page.url)
        if not match:
            raise AssertionError(f"Could not read empNumber from URL: {self.page.url}")
        return match.group(1)

    def open_tab(self, tab_name: str) -> None:
        tab = self.page.get_by_role("link", name=tab_name, exact=True)
        self.click(tab, f"Employee profile tab '{tab_name}'")
        self.wait_for_page_ready()

    def verify_employee_name_header(self, expected_name: str) -> None:
        expect(
            self.employee_name_header, f"Profile header should show '{expected_name}'"
        ).to_have_text(expected_name)

    def wait_for_profile_picture_loaded(self) -> None:
        expect(self.profile_picture, "Profile picture should be visible").to_be_visible()
        self.page.wait_for_function(
            "img => img.complete && img.naturalWidth > 0",
            arg=self.profile_picture.element_handle(),
        )

    def get_profile_picture_size(self) -> tuple[int, int]:
        """Natural (intrinsic) width/height of the avatar image currently displayed."""
        self.wait_for_profile_picture_loaded()
        width, height = self.profile_picture.evaluate("img => [img.naturalWidth, img.naturalHeight]")
        return int(width), int(height)

    def capture_profile_picture(self, name: str) -> bytes:
        """Screenshot of the avatar only - used to prove the picture really changed."""
        self.wait_for_profile_picture_loaded()
        path = settings.screenshots_dir / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image = self.profile_picture.screenshot(path=str(path))
        attach_png(image, name)
        return image

    def open_change_profile_picture(self):
        from pages.change_profile_picture_page import ChangeProfilePicturePage

        self.click(self.page.locator(L.AVATAR_LINK), "Employee avatar (opens Change Profile Picture)")
        return ChangeProfilePicturePage(self.page).verify_loaded()

    def verify_profile_picture_uploaded(self) -> None:
        expect(
            self.profile_picture,
            "Profile picture should be the uploaded image, not the default avatar",
        ).to_have_attribute("src", re.compile(r"^(?!.*default-photo).+"))

    def go_to_personal_details(self):
        from pages.personal_details_page import PersonalDetailsPage

        self.open_tab(L.TAB_PERSONAL_DETAILS)
        return PersonalDetailsPage(self.page).verify_loaded()

    def go_to_contact_details(self):
        from pages.contact_details_page import ContactDetailsPage

        self.open_tab(L.TAB_CONTACT_DETAILS)
        return ContactDetailsPage(self.page).verify_loaded()

    def go_to_job_details(self):
        from pages.job_details_page import JobDetailsPage

        self.open_tab(L.TAB_JOB)
        return JobDetailsPage(self.page).verify_loaded()
