"""BasePage - reusable actions (keyword layer) shared by all page objects."""
from __future__ import annotations

import re
from typing import Pattern, Union

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from locators.common_locators import CommonLocators, SideMenu
from utils.logger import get_logger

TextMatcher = Union[str, Pattern[str]]


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.log = get_logger(type(self).__name__)
        self.module_header = page.locator(CommonLocators.MODULE_HEADER)
        self.user_dropdown = page.locator(CommonLocators.USER_DROPDOWN)
        self.user_dropdown_name = page.locator(CommonLocators.USER_DROPDOWN_NAME)
        self.logout_link = page.locator(CommonLocators.LOGOUT_LINK)
        self.toast_message = page.locator(CommonLocators.TOAST_MESSAGE)
        self.form_loader = page.locator(CommonLocators.FORM_LOADER)
        self.field_errors = page.locator(CommonLocators.FIELD_ERROR)

    # ------------------------------------------------------------------ navigation
    def navigate(self, path: str) -> None:
        url = f"{settings.base_url}{path}"
        self.log.info("Navigate to %s", url)
        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            # The shared public demo occasionally stalls on the very first request of a test
            # (no app code has run yet, so this is pure site/network slowness). One retry with
            # a fresh navigation clears it far more often than it recurs.
            self.log.warning("Navigation to %s timed out once - retrying", url)
            self.page.goto(url, wait_until="domcontentloaded")
        self.wait_for_page_ready()

    def reload(self) -> None:
        self.log.info("Reload page %s", self.page.url)
        self.page.reload(wait_until="domcontentloaded")
        self.wait_for_page_ready()

    def wait_for_page_ready(self) -> None:
        """Wait for network to settle (best effort) and for OrangeHRM form loaders to vanish."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightError:
            self.log.debug("networkidle not reached in 10s - continuing")
        expect(self.form_loader, "Form loading spinner should disappear").to_have_count(0)

    def open_side_menu(self, menu_name: str) -> None:
        item = self.page.locator(CommonLocators.SIDE_MENU_ITEM.format(name=menu_name))
        self.click(item, f"Side menu '{menu_name}'")
        self.wait_for_page_ready()

    def open_top_nav_tab(self, tab_name: str) -> None:
        tab = self.page.locator(CommonLocators.TOP_NAV_TAB.format(name=tab_name))
        self.click(tab, f"Top navigation tab '{tab_name}'")
        self.wait_for_page_ready()

    # ------------------------------------------------------------------ element lookup
    def input_by_label(self, label: str) -> Locator:
        return self.page.locator(CommonLocators.INPUT_BY_LABEL.format(label=label))

    def dropdown_by_label(self, label: str) -> Locator:
        return self.page.locator(CommonLocators.SELECT_BY_LABEL.format(label=label))

    # ------------------------------------------------------------------ actions
    def click(self, locator: Locator, description: str) -> None:
        self.log.info("Click: %s", description)
        expect(locator, f"'{description}' should be visible before clicking").to_be_visible()
        locator.click()

    def fill(self, locator: Locator, value: str, description: str, *, secret: bool = False) -> None:
        self.log.info("Type: %s = %s", description, "******" if secret else repr(value))
        expect(locator, f"'{description}' should be editable").to_be_editable()
        locator.fill(value)
        expect(locator, f"'{description}' should contain the typed value").to_have_value(value)

    def select_dropdown_option(self, dropdown: Locator, option_text: str, description: str) -> None:
        """Select an option in OrangeHRM's custom <div role='listbox'> dropdown."""
        self.log.info("Select: %s = %r", description, option_text)
        expect(dropdown, f"Dropdown '{description}' should be visible").to_be_visible()
        dropdown.click()
        listbox = self.page.locator(CommonLocators.DROPDOWN_LISTBOX)
        expect(listbox, f"Options list of '{description}' should open").to_be_visible()

        all_options = listbox.locator(CommonLocators.DROPDOWN_OPTION)
        option = all_options.filter(has_text=re.compile(rf"^\s*{re.escape(option_text)}\s*$"))
        if option.count() == 0:
            available = [text.strip() for text in all_options.all_inner_texts()]
            self.page.keyboard.press("Escape")
            raise AssertionError(
                f"Option '{option_text}' is not available in dropdown '{description}'. "
                f"Available options: {available}"
            )
        option.first.click()
        self.verify_dropdown_value(dropdown, option_text, description)

    def get_dropdown_value(self, dropdown: Locator) -> str:
        return dropdown.locator(CommonLocators.DROPDOWN_SELECTED_TEXT).inner_text().strip()

    def select_radio(self, label: str, description: str) -> None:
        self.click(self.page.locator(CommonLocators.RADIO_LABEL.format(label=label)), description)
        expect(
            self.page.locator(CommonLocators.RADIO_INPUT.format(label=label)),
            f"Radio '{label}' should be selected",
        ).to_be_checked()

    # ------------------------------------------------------------------ assertions
    def verify_dropdown_value(self, dropdown: Locator, expected: str, description: str) -> None:
        expect(
            dropdown.locator(CommonLocators.DROPDOWN_SELECTED_TEXT),
            f"Dropdown '{description}' should display '{expected}'",
        ).to_have_text(expected)

    def verify_input_value(self, locator: Locator, expected: str, description: str) -> None:
        expect(locator, f"'{description}' should have value '{expected}'").to_have_value(expected)

    def verify_radio_selected(self, label: str) -> None:
        expect(
            self.page.locator(CommonLocators.RADIO_INPUT.format(label=label)),
            f"Radio button '{label}' should be selected",
        ).to_be_checked()

    def verify_module_header(self, expected: str) -> None:
        expect(self.module_header, f"Top bar header should read '{expected}'").to_have_text(expected)

    def expect_toast(self, expected: TextMatcher, description: str = "Success toast") -> None:
        self.log.info("Waiting for toast: %s", expected if isinstance(expected, str) else expected.pattern)
        expect(self.toast_message.first, f"{description} should be displayed").to_contain_text(expected)

    def get_field_errors(self) -> list[str]:
        return [text.strip() for text in self.field_errors.all_inner_texts() if text.strip()]

    # ------------------------------------------------------------------ session
    def logout(self):
        """Log out via the user menu and return the Login page."""
        from pages.login_page import LoginPage

        self.click(self.user_dropdown, "User profile dropdown")
        self.click(self.logout_link, "Logout link")
        login_page = LoginPage(self.page)
        login_page.verify_loaded()
        return login_page

    def go_to_dashboard(self) -> None:
        self.open_side_menu(SideMenu.DASHBOARD)
