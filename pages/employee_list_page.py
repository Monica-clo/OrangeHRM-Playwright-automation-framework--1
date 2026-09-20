"""PIM > Employee List page object."""
from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Locator, Page, expect

from api.models import EmployeeSnapshot
from locators.common_locators import Messages
from locators.pim_locators import EmployeeListLocators as L
from pages.pim_base_page import PimBasePage


class EmployeeListPage(PimBasePage):
    URL_PATH = "/web/index.php/pim/viewEmployeeList"
    URL_PATTERN = re.compile(r"/pim/viewEmployeeList")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.employee_name_input = page.locator(L.EMPLOYEE_NAME_INPUT)
        self.employee_id_input = page.locator(L.EMPLOYEE_ID_INPUT)
        self.search_button = page.locator(L.SEARCH_BUTTON)
        self.reset_button = page.locator(L.RESET_BUTTON)
        self.table_loader = page.locator(L.TABLE_LOADER)
        self.header_cells = page.locator(L.TABLE_HEADER_CELLS)
        self.table_rows = page.locator(L.TABLE_ROWS)
        self.records_found = page.get_by_text(re.compile(L.RECORDS_FOUND_PATTERN))
        self.no_records_found = page.get_by_text(L.NO_RECORDS_FOUND_TEXT, exact=True)
        self.confirm_delete_button = page.locator(L.CONFIRM_DELETE_BUTTON)

    # ------------------------------------------------------------------ page state
    def open(self) -> "EmployeeListPage":
        self.navigate(self.URL_PATH)
        self.verify_loaded()
        return self

    def verify_loaded(self) -> "EmployeeListPage":
        expect(self.page, "Employee List page should be opened").to_have_url(self.URL_PATTERN)
        self.verify_module_header(self.MODULE_NAME)
        expect(self.search_button, "Search button should be visible on Employee List").to_be_visible()
        return self

    def wait_for_table(self) -> None:
        expect(self.table_loader, "Employee table should finish loading").to_have_count(0)

    # ------------------------------------------------------------------ search
    def search(self, employee_id: str) -> "EmployeeListPage":
        """Type the Employee Id and click Search (no assertion on the result)."""
        self.wait_for_table()
        self.fill(self.employee_id_input, employee_id, "Employee Id (search)")
        self.click(self.search_button, "Search button")
        self.wait_for_table()
        return self

    def search_by_employee_id(self, employee_id: str) -> "EmployeeListPage":
        """Search and assert that exactly the requested employee is returned."""
        self.search(employee_id)
        expect(
            self.row_by_employee_id(employee_id),
            f"Search by Employee Id '{employee_id}' should return the employee",
        ).to_have_count(1)
        expect(
            self.table_rows,
            f"Search by unique Employee Id '{employee_id}' should return exactly one row",
        ).to_have_count(1)
        return self

    # ------------------------------------------------------------------ table helpers
    def column_index(self, column_name: str) -> int:
        expect(self.header_cells.first, "Table header should be visible").to_be_visible()
        headers = [text.strip() for text in self.header_cells.all_inner_texts()]
        for index, header in enumerate(headers):
            if header == column_name or header.startswith(column_name):
                return index
        raise AssertionError(f"Column '{column_name}' not found in table. Columns: {headers}")

    def row_by_employee_id(self, employee_id: str) -> Locator:
        id_cell = self.page.locator(L.ROW_CELLS).filter(
            has_text=re.compile(rf"^\s*{re.escape(employee_id)}\s*$")
        )
        return self.table_rows.filter(has=id_cell)

    def cell(self, row: Locator, column_name: str) -> Locator:
        return row.locator(L.ROW_CELLS).nth(self.column_index(column_name))

    def get_row_data(self, employee_id: str) -> dict[str, str]:
        row = self.row_by_employee_id(employee_id)
        headers = [text.strip() for text in self.header_cells.all_inner_texts()]
        values = [text.strip() for text in row.locator(L.ROW_CELLS).all_inner_texts()]
        return {h: v for h, v in zip(headers, values) if h}

    # ------------------------------------------------------------------ verification
    def verify_employee_record(
        self,
        employee_id: str,
        first_name: str,
        last_name: str,
        job_title: Optional[str] = None,
        employment_status: Optional[str] = None,
    ) -> None:
        row = self.row_by_employee_id(employee_id)
        expect(row, f"Employee '{employee_id}' should be listed in the results").to_have_count(1)
        expect(self.cell(row, L.COL_ID), "Id column should match").to_have_text(employee_id)
        expect(
            self.cell(row, L.COL_FIRST_MIDDLE_NAME),
            f"First (& Middle) Name column should contain '{first_name}'",
        ).to_contain_text(first_name)
        expect(
            self.cell(row, L.COL_LAST_NAME), f"Last Name column should be '{last_name}'"
        ).to_have_text(last_name)
        if job_title is not None:
            expect(
                self.cell(row, L.COL_JOB_TITLE), f"Job Title column should be '{job_title}'"
            ).to_have_text(job_title)
        if employment_status is not None:
            expect(
                self.cell(row, L.COL_EMPLOYMENT_STATUS),
                f"Employment Status column should be '{employment_status}'",
            ).to_have_text(employment_status)
        self.log.info("Verified table row: %s", self.get_row_data(employee_id))

    def verify_no_records_found(self, employee_id: str) -> None:
        expect(
            self.row_by_employee_id(employee_id),
            f"Employee '{employee_id}' should NOT be listed any more",
        ).to_have_count(0)
        expect(
            self.no_records_found.first,
            f"'No Records Found' should be shown when searching for deleted employee '{employee_id}'",
        ).to_be_visible()

    def verify_employee_not_found(self, employee_id: str) -> None:
        """Run a fresh search for the Employee Id and assert nothing is returned."""
        self.search(employee_id)
        self.verify_no_records_found(employee_id)

    def get_employee_snapshot(self, employee_id: str, emp_number: Optional[int] = None) -> EmployeeSnapshot:
        """Read the employee's row from the table as a comparable snapshot."""
        expect(self.row_by_employee_id(employee_id), f"Employee '{employee_id}' should be listed").to_have_count(1)
        snapshot = EmployeeSnapshot.from_ui_row(self.get_row_data(employee_id), emp_number)
        self.log.info("UI snapshot: %s", snapshot)
        return snapshot

    # ------------------------------------------------------------------ row actions
    def open_employee_record(self, employee_id: str):
        from pages.personal_details_page import PersonalDetailsPage

        row = self.row_by_employee_id(employee_id)
        self.click(row.locator(L.ROW_EDIT_ICON), f"Edit (pencil) icon of employee '{employee_id}'")
        personal_details = PersonalDetailsPage(self.page)
        personal_details.verify_loaded()
        return personal_details

    def delete_employee(self, employee_id: str) -> None:
        """Search the employee, delete it via the trash icon and confirm the dialog."""
        self.search_by_employee_id(employee_id)
        row = self.row_by_employee_id(employee_id)
        self.click(row.locator(L.ROW_DELETE_ICON), f"Delete (trash) icon of employee '{employee_id}'")
        expect(self.confirm_delete_button, "Delete confirmation dialog should open").to_be_visible()
        self.click(self.confirm_delete_button, "Yes, Delete button")
        self.expect_toast(Messages.SUCCESSFULLY_DELETED, "'Successfully Deleted' toast")
        self.wait_for_table()
