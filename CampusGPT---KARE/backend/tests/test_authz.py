"""Authorization isolation tests. Run from backend/: pytest -q"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str = "campus123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_student_cannot_use_faculty_identity_on_sis(client):
    token = _login(client, "student@example.com")
    res = client.get("/api/academic/attendance", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["student"]["roll_no"] == "DEMO2024CSE099"


def test_faculty_cannot_read_student_attendance_endpoint(client):
    token = _login(client, "faculty@example.com")
    res = client.get("/api/academic/attendance", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_two_students_are_isolated(client):
    a = _login(client, "student@example.com")
    b = _login(client, "student.demo@klu.ac.in")
    ra = client.get("/api/academic/attendance", headers={"Authorization": f"Bearer {a}"}).json()
    rb = client.get("/api/academic/attendance", headers={"Authorization": f"Bearer {b}"}).json()
    assert ra["student"]["roll_no"] != rb["student"]["roll_no"]


def test_consent_revoke_blocks_attendance(client):
    token = _login(client, "student@example.com")
    h = {"Authorization": f"Bearer {token}"}
    deny = client.post("/api/privacy/consents", headers=h, json={"key": "academic.attendance", "status": "deny"})
    assert deny.status_code == 200
    blocked = client.get("/api/academic/attendance", headers=h)
    assert blocked.status_code == 403
    client.post("/api/privacy/consents", headers=h, json={"key": "academic.attendance", "status": "allow"})


def test_admin_can_read_audit(client):
    token = _login(client, "admin@example.com")
    res = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_student_cannot_read_audit(client):
    token = _login(client, "student@example.com")
    res = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
