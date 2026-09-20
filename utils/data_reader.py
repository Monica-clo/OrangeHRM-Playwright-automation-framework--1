"""Data-driven layer: reads employee test data from JSON or CSV."""
from __future__ import annotations

import csv
import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Optional

from config.settings import settings
from utils.data_models import ContactInfo, EmployeeData, JobDetails, PersonalInfo

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_REQUIRED_EMPLOYEE_KEYS = ("test_id", "first_name", "last_name")


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in _TRUE_VALUES


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _resolve_path(value: Any) -> Optional[Path]:
    text = _clean(value)
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else settings.project_root / path


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Test data file not found: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Test data file not found: {path}")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if any((v or "").strip() for v in row.values())]


def build_employee(record: dict[str, Any]) -> EmployeeData:
    missing = [key for key in _REQUIRED_EMPLOYEE_KEYS if not _clean(record.get(key))]
    if missing:
        raise ValueError(f"Test data record {record!r} is missing required keys: {missing}")

    job = None
    if _clean(record.get("job_title")) or _clean(record.get("employment_status")):
        job = JobDetails(
            job_title=_clean(record.get("job_title")),
            employment_status=_clean(record.get("employment_status")),
        )

    return EmployeeData(
        test_id=_clean(record["test_id"]),
        first_name=_clean(record["first_name"]),
        middle_name=_clean(record.get("middle_name")),
        last_name=_clean(record["last_name"]),
        employee_id_prefix=_clean(record.get("employee_id_prefix")) or "QA",
        profile_picture=_resolve_path(record.get("profile_picture")),
        edit_profile_picture=_resolve_path(record.get("edit_profile_picture")),
        create_login_details=_to_bool(record.get("create_login_details")),
        username_prefix=_clean(record.get("username_prefix")),
        password=_clean(record.get("password")),
        login_status=_clean(record.get("login_status")) or "Enabled",
        job=job,
    )


def load_employees(source: Optional[str] = None) -> list[EmployeeData]:
    """Load employees from the configured source ('json' or 'csv')."""
    source = (source or settings.data_source).lower()
    if source == "json":
        records = read_json(settings.json_data_file)
    elif source == "csv":
        records = read_csv(settings.csv_data_file)
    else:
        raise ValueError(f"Unsupported DATA_SOURCE '{source}'. Use 'json' or 'csv'.")
    if not records:
        raise ValueError(f"No employee records found for data source '{source}'.")
    return [build_employee(record) for record in records]


def _build(model: type, data: dict[str, Any]):
    allowed = {f.name for f in fields(model)}
    return model(**{k: _clean(v) for k, v in (data or {}).items() if k in allowed})


def load_employee_profile() -> tuple[EmployeeData, PersonalInfo, ContactInfo, dict[str, str]]:
    """Load the data for the personal/contact details regression test."""
    data = read_json(settings.profile_data_file)
    employee = build_employee(data["employee"])
    personal = _build(PersonalInfo, data.get("personal_details", {}))
    contact_raw = dict(data.get("contact_details", {}))
    email_domains = {
        "work": contact_raw.pop("work_email_domain", "example.com"),
        "other": contact_raw.pop("other_email_domain", "example.org"),
    }
    contact = _build(ContactInfo, contact_raw)
    return employee, personal, contact, email_domains


def load_reqres_data() -> dict[str, Any]:
    """Load the data-driven inputs/expectations for the ReqRes API suite."""
    return read_json(settings.reqres_data_file)
