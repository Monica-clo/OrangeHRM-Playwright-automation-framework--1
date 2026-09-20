"""Normalised employee view read from the UI (used to build API payloads and compare data)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class EmployeeSnapshot:
    employee_id: str
    first_name: str
    middle_name: str
    last_name: str
    job_title: str = ""
    employment_status: str = ""
    emp_number: Optional[int] = None

    @property
    def first_and_middle_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.middle_name) if part)

    @property
    def full_name(self) -> str:
        return f"{self.first_and_middle_name} {self.last_name}".strip()

    @classmethod
    def from_ui_row(cls, row: dict[str, str], emp_number: Optional[int] = None) -> "EmployeeSnapshot":
        """Build from an Employee List table row (column header -> cell text)."""
        names = row.get("First (& Middle) Name", "").split()
        return cls(
            employee_id=row.get("Id", "").strip(),
            first_name=names[0] if names else "",
            middle_name=" ".join(names[1:]),
            last_name=row.get("Last Name", "").strip(),
            job_title=row.get("Job Title", "").strip(),
            employment_status=row.get("Employment Status", "").strip(),
            emp_number=emp_number,
        )

    def differences(self, other: "EmployeeSnapshot", ignore: tuple[str, ...] = ("emp_number",)) -> dict[str, tuple]:
        mine, theirs = asdict(self), asdict(other)
        return {k: (mine[k], theirs[k]) for k in mine if k not in ignore and mine[k] != theirs[k]}


def assert_snapshots_match(actual: EmployeeSnapshot, expected: EmployeeSnapshot, context: str) -> None:
    diff = actual.differences(expected)
    if diff:
        rows = "\n".join(f"  - {field}: actual={a!r} | expected={e!r}" for field, (a, e) in diff.items())
        raise AssertionError(f"{context}: employee data is inconsistent:\n{rows}")
