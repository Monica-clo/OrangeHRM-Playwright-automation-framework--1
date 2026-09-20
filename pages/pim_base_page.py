"""Common behaviour for every page inside the PIM module."""
from __future__ import annotations

from locators.common_locators import PimTopNav
from pages.base_page import BasePage


class PimBasePage(BasePage):
    MODULE_NAME = "PIM"

    def go_to_employee_list(self):
        from pages.employee_list_page import EmployeeListPage

        self.open_top_nav_tab(PimTopNav.EMPLOYEE_LIST)
        employee_list = EmployeeListPage(self.page)
        employee_list.verify_loaded()
        return employee_list

    def go_to_add_employee(self):
        from pages.add_employee_page import AddEmployeePage

        self.open_top_nav_tab(PimTopNav.ADD_EMPLOYEE)
        add_employee = AddEmployeePage(self.page)
        add_employee.verify_loaded()
        return add_employee
