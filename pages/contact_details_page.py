"""Employee profile > Contact Details page object (screenshot 5)."""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from locators.common_locators import Messages
from locators.pim_locators import ContactDetailsLocators as L
from pages.employee_profile_base_page import EmployeeProfileBasePage
from utils.data_models import ContactInfo

_UPDATED = re.compile(rf"{Messages.SUCCESSFULLY_UPDATED}|{Messages.SUCCESSFULLY_SAVED}")


class ContactDetailsPage(EmployeeProfileBasePage):
    URL_PATTERN = re.compile(r"/pim/contactDetails/empNumber/\d+")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.page_title = page.locator(L.PAGE_TITLE)
        self.country_dropdown = page.locator(L.COUNTRY_DROPDOWN)
        self.save_button = page.locator(L.SAVE_BUTTON)
        # text inputs keyed by the ContactInfo attribute name
        self.text_fields = {
            "street_1": (page.locator(L.STREET_1_INPUT), "Street 1"),
            "street_2": (page.locator(L.STREET_2_INPUT), "Street 2"),
            "city": (page.locator(L.CITY_INPUT), "City"),
            "state_province": (page.locator(L.STATE_PROVINCE_INPUT), "State/Province"),
            "zip_postal_code": (page.locator(L.ZIP_POSTAL_CODE_INPUT), "Zip/Postal Code"),
            "home_telephone": (page.locator(L.HOME_TELEPHONE_INPUT), "Home telephone"),
            "mobile": (page.locator(L.MOBILE_INPUT), "Mobile"),
            "work_telephone": (page.locator(L.WORK_TELEPHONE_INPUT), "Work telephone"),
            "work_email": (page.locator(L.WORK_EMAIL_INPUT), "Work Email"),
            "other_email": (page.locator(L.OTHER_EMAIL_INPUT), "Other Email"),
        }

    def verify_loaded(self) -> "ContactDetailsPage":
        expect(self.page, "Contact Details page should be opened").to_have_url(self.URL_PATTERN)
        expect(self.page_title, "'Contact Details' title should be visible").to_be_visible()
        self.wait_for_page_ready()
        return self

    def update_contact_info(self, info: ContactInfo) -> "ContactDetailsPage":
        for attribute, (locator, description) in self.text_fields.items():
            value = getattr(info, attribute)
            if value:
                self.fill(locator, value, description)
        if info.country:
            self.select_dropdown_option(self.country_dropdown, info.country, "Country")
        self.click(self.save_button, "Contact Details Save button")
        self.expect_toast(_UPDATED, "Contact details update toast")
        return self

    def verify_contact_info(self, info: ContactInfo) -> None:
        for attribute, (locator, description) in self.text_fields.items():
            value = getattr(info, attribute)
            if value:
                self.verify_input_value(locator, value, description)
        if info.country:
            self.verify_dropdown_value(self.country_dropdown, info.country, "Country")
