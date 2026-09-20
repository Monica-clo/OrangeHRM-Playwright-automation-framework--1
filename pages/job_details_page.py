"""Employee profile > Job page object (scenario step 3)."""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from locators.common_locators import Messages
from locators.pim_locators import JobDetailsLocators as L
from pages.employee_profile_base_page import EmployeeProfileBasePage
from utils.data_models import JobDetails

_UPDATED = re.compile(rf"{Messages.SUCCESSFULLY_UPDATED}|{Messages.SUCCESSFULLY_SAVED}")


class JobDetailsPage(EmployeeProfileBasePage):
    URL_PATTERN = re.compile(r"/pim/viewJobDetails/empNumber/\d+")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.page_title = page.locator(L.PAGE_TITLE)
        self.joined_date_input = page.locator(L.JOINED_DATE_INPUT)
        self.job_title_dropdown = page.locator(L.JOB_TITLE_DROPDOWN)
        self.job_category_dropdown = page.locator(L.JOB_CATEGORY_DROPDOWN)
        self.sub_unit_dropdown = page.locator(L.SUB_UNIT_DROPDOWN)
        self.location_dropdown = page.locator(L.LOCATION_DROPDOWN)
        self.employment_status_dropdown = page.locator(L.EMPLOYMENT_STATUS_DROPDOWN)
        self.save_button = page.locator(L.SAVE_BUTTON)

    def verify_loaded(self) -> "JobDetailsPage":
        expect(self.page, "Job Details page should be opened").to_have_url(self.URL_PATTERN)
        expect(self.page_title, "'Job Details' title should be visible").to_be_visible()
        self.wait_for_page_ready()
        expect(self.job_title_dropdown, "Job Title dropdown should be visible").to_be_visible()
        return self

    def select_job_title(self, job_title: str) -> None:
        self.select_dropdown_option(self.job_title_dropdown, job_title, "Job Title")

    def select_employment_status(self, employment_status: str) -> None:
        self.select_dropdown_option(
            self.employment_status_dropdown, employment_status, "Employment Status"
        )

    def update_job_details(self, job: JobDetails) -> "JobDetailsPage":
        self.select_job_title(job.job_title)
        self.select_employment_status(job.employment_status)
        self.click(self.save_button, "Job Details Save button")
        self.expect_toast(_UPDATED, "Job details update toast")
        return self

    def verify_job_details(self, job: JobDetails) -> None:
        self.verify_dropdown_value(self.job_title_dropdown, job.job_title, "Job Title")
        self.verify_dropdown_value(
            self.employment_status_dropdown, job.employment_status, "Employment Status"
        )

    def get_job_details(self) -> JobDetails:
        """Read the values currently displayed in the Job Title / Employment Status dropdowns."""
        return JobDetails(
            job_title=self.get_dropdown_value(self.job_title_dropdown),
            employment_status=self.get_dropdown_value(self.employment_status_dropdown),
        )

    def reload_and_verify_job_details(self, job: JobDetails) -> None:
        """Reload so the check proves the values were persisted, not just shown in the form."""
        self.reload()
        self.verify_loaded()
        self.verify_job_details(job)
