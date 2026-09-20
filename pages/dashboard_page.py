"""Dashboard page object (landing page after login)."""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from locators.common_locators import SideMenu
from locators.login_locators import DashboardLocators as L
from pages.base_page import BasePage


class DashboardPage(BasePage):
    URL_PATTERN = re.compile(r"/dashboard/index")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.widgets = page.locator(L.DASHBOARD_WIDGETS)

    def verify_loaded(self) -> "DashboardPage":
        expect(self.page, "User should be redirected to the Dashboard after login").to_have_url(self.URL_PATTERN)
        self.verify_module_header(L.DASHBOARD_HEADER_TEXT)
        expect(self.user_dropdown, "Logged-in user profile menu should be visible").to_be_visible()
        # Right after login the SPA can still be hydrating: the dropdown element is visible but
        # briefly shows a CSS loading-skeleton placeholder ('ssssssss') instead of the real name,
        # and the dashboard widgets/router aren't wired up yet. Clicking side-menu/top-nav items
        # during this window can silently fail to navigate (or bounce back to /auth/login on the
        # shared demo). Wait for the network to settle and the widgets to actually render before
        # treating the Dashboard as ready for the next action.
        self.wait_for_page_ready()
        expect(self.widgets.first, "Dashboard widgets should be rendered").to_be_visible()
        expect(
            self.user_dropdown_name, "Logged-in user name should be loaded (not the loading placeholder)"
        ).not_to_have_text(re.compile(r"^s+$"))
        self.log.info("Logged in as '%s'", self.user_dropdown_name.inner_text().strip())
        return self

    def go_to_pim(self):
        from pages.employee_list_page import EmployeeListPage

        self.open_side_menu(SideMenu.PIM)
        employee_list = EmployeeListPage(self.page)
        employee_list.verify_loaded()
        return employee_list
