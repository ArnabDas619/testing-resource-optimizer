"""
services/api_stub.py
--------------------
Mocks a company HR API that returns employee roster JSON.
In production this would call an internal HR system endpoint.
"""
import random
from faker import Faker

fake = Faker()
random.seed(42)

_SKILL_POOLS = {
    "Low":  ["Manual Testing", "Exploratory Testing", "UI/UX Testing"],
    "Mid":  ["Manual Testing", "API Testing", "Cypress", "Selenium", "Accessibility", "SQL Testing"],
    "High": ["Automation", "Selenium", "Cypress", "Playwright", "Performance Testing",
             "Security Testing", "Penetration Testing", "K6", "JMeter", "WCAG Audit",
             "CI/CD Integration", "API Testing", "SQL Testing"],
}

_DEPT_SKILL_MAP = {
    "QA Manual":        ("Low",  ["Manual Testing", "Exploratory Testing", "UI/UX Testing"]),
    "QA Automation":    ("High", ["Automation", "Selenium", "Cypress", "Playwright", "CI/CD Integration"]),
    "QA Performance":   ("High", ["Performance Testing", "K6", "JMeter", "Load Testing"]),
    "QA Security":      ("High", ["Security Testing", "Penetration Testing", "OWASP", "SQL Injection"]),
    "QA Accessibility": ("Mid",  ["Accessibility", "WCAG Audit", "Screen Reader Testing"]),
    "QA API":           ("Mid",  ["API Testing", "Postman", "REST Assured", "SQL Testing"]),
}

def _build_employee(dept_name: str, dept_info: tuple) -> dict:
    proficiency, skills = dept_info
    # Randomly pick 2-4 skills from the pool
    chosen = random.sample(skills, min(len(skills), random.randint(2, 4)))
    return {
        "employee_id": f"EMP-{random.randint(1000, 9999)}",
        "name": fake.name(),
        "department": dept_name,
        "experience_years": random.randint(1, 15),
        "skills": chosen,
        "proficiency": proficiency,
        "available_hours_per_week": random.choice([20, 30, 40]),
        "email": fake.email(),
    }

# Stable roster — generated once at import time
_ROSTER: list[dict] = []
for dept, info in _DEPT_SKILL_MAP.items():
    count = random.randint(2, 4)
    for _ in range(count):
        _ROSTER.append(_build_employee(dept, info))


def get_employees(department: str | None = None) -> list[dict]:
    """Return stubbed employee list, optionally filtered by department."""
    if department:
        return [e for e in _ROSTER if e["department"].lower() == department.lower()]
    return _ROSTER


def get_employee_by_id(employee_id: str) -> dict | None:
    """Lookup a single employee by ID."""
    for emp in _ROSTER:
        if emp["employee_id"] == employee_id:
            return emp
    return None


def get_departments() -> list[str]:
    """Return unique department names."""
    return list(_DEPT_SKILL_MAP.keys())
