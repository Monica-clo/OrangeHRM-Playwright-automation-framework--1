"""Employee profile > Change Profile Picture page object.

Opened by clicking the avatar on any employee profile tab
(/web/index.php/pim/viewPhotograph/empNumber/<n>).
"""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

from locators.common_locators import Messages
from locators.pim_locators import ChangeProfilePictureLocators as L
from pages.employee_profile_base_page import EmployeeProfileBasePage
from utils.image_utils import validate_profile_photo

_UPDATED = re.compile(rf"{Messages.SUCCESSFULLY_UPDATED}|{Messages.SUCCESSFULLY_SAVED}")


class ChangeProfilePicturePage(EmployeeProfileBasePage):
    URL_PATTERN = re.compile(r"/pim/viewPhotograph/empNumber/\d+")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.page_title = page.locator(L.PAGE_TITLE)
        self.photo_file_input = page.locator(L.PHOTO_FILE_INPUT)
        self.photo_preview = page.locator(L.PHOTO_PREVIEW)
        self.save_button = page.locator(L.SAVE_BUTTON)

    def verify_loaded(self) -> "ChangeProfilePicturePage":
        expect(self.page, "Change Profile Picture page should be opened").to_have_url(self.URL_PATTERN)
        expect(self.page_title, "'Change Profile Picture' title should be visible").to_be_visible()
        self.wait_for_page_ready()
        return self

    def upload_photo(self, photo: Path) -> None:
        validate_profile_photo(photo)
        self.log.info("Upload new profile photo: %s", photo)
        self.photo_file_input.set_input_files(str(photo))
        expect(
            self.photo_preview, "Preview should show the newly selected photo before saving"
        ).to_have_attribute("src", re.compile(r"^data:image/"))

    def save(self) -> "ChangeProfilePicturePage":
        self.click(self.save_button, "Change Profile Picture Save button")
        try:
            self.expect_toast(_UPDATED, "Profile picture update toast")
        except AssertionError as error:
            raise AssertionError(
                f"Profile picture was not saved. Validation errors: {self.get_field_errors() or 'none shown'}"
            ) from error
        self.wait_for_page_ready()
        return self

    def change_photo(self, photo: Path) -> "ChangeProfilePicturePage":
        self.upload_photo(photo)
        return self.save()
