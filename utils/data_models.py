"""Typed test-data models used by page objects and tests."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

EMPLOYEE_ID_MAX_LENGTH = 10  # OrangeHRM limit


def random_digits(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(max(length, 1)))


@dataclass(frozen=True)
class JobDetails:
    job_title: str
    employment_status: str


@dataclass(frozen=True)
class EmployeeData:
    test_id: str
    first_name: str
    last_name: str
    middle_name: str = ""
    employee_id_prefix: str = "QA"
    employee_id: str = ""
    profile_picture: Optional[Path] = None
    edit_profile_picture: Optional[Path] = None   # new photo uploaded while editing
    create_login_details: bool = False
    username_prefix: str = ""
    username: str = ""
    password: str = ""
    login_status: str = "Enabled"
    job: Optional[JobDetails] = None

    @property
    def display_name(self) -> str:
        """Name shown above the avatar on the profile page, e.g. 'Monica N'."""
        return f"{self.first_name} {self.last_name}"

    def with_unique_identifiers(self) -> "EmployeeData":
        """Return a copy with a unique Employee Id (and username) for this run.

        The demo site is shared by many people, so hard-coded IDs would collide.
        """
        prefix = self.employee_id_prefix[: EMPLOYEE_ID_MAX_LENGTH - 4]
        suffix = random_digits(EMPLOYEE_ID_MAX_LENGTH - len(prefix))
        username = ""
        if self.create_login_details:
            username = f"{self.username_prefix or self.first_name.lower()}{suffix}"
        return replace(self, employee_id=f"{prefix}{suffix}", username=username)


@dataclass(frozen=True)
class PersonalInfo:
    other_id: str = ""
    drivers_license_number: str = ""
    nationality: str = ""
    marital_status: str = ""
    gender: str = ""  # "Male" | "Female"


@dataclass(frozen=True)
class ContactInfo:
    street_1: str = ""
    street_2: str = ""
    city: str = ""
    state_province: str = ""
    zip_postal_code: str = ""
    country: str = ""
    home_telephone: str = ""
    mobile: str = ""
    work_telephone: str = ""
    work_email: str = ""
    other_email: str = ""
