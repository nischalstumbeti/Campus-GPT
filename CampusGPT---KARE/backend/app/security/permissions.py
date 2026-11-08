"""Granular consent keys. The LLM never sees this catalog as authority — the gateway does."""
from __future__ import annotations

from typing import Literal

PermissionState = Literal["allow", "deny"]

CATEGORIES: dict[str, dict] = {
    "campus_gpt": {
        "label": "Campus-GPT Consent",
        "purpose": "Control whether Campus-GPT may use your records for answers and model training.",
        "keys": {
            "campus_gpt.assist": "Use my data for Campus-GPT assistance",
            "campus_gpt.train": "Allow admin model training with my anonymized profile",
        },
    },
    "academic": {
        "label": "Academic Records",
        "purpose": "Personalized academics: attendance, marks, CGPA, and study planning.",
        "keys": {
            "academic.attendance": "Attendance",
            "academic.marks": "Marks",
            "academic.grades": "Grades",
            "academic.cgpa": "CGPA",
            "academic.credits": "Credits",
            "academic.history": "Academic history / timetable",
            "academic.timetable": "Class timetable",
            "academic.courses": "Enrolled courses",
            "academic.exams": "Exam schedule",
        },
    },
    "hostel": {
        "label": "Hostel",
        "purpose": "Hostel leave, room, and hostel records assistance.",
        "keys": {
            "hostel.room": "Room information",
            "hostel.leave": "Leave information",
            "hostel.records": "Hostel records",
        },
    },
    "achievements": {
        "label": "Achievements",
        "purpose": "Certifications, awards, and activities for career/resume help.",
        "keys": {
            "achievements.certs": "Certifications",
            "achievements.awards": "Awards",
            "achievements.activities": "Activities",
        },
    },
    "financial": {
        "label": "Financial",
        "purpose": "Fees and scholarship information when you ask about them.",
        "keys": {
            "financial.fees": "Fees",
            "financial.scholarship": "Scholarship information",
        },
    },
    "services": {
        "label": "Campus services",
        "purpose": "Messages and complaints through Campus-GPT / UIS.",
        "keys": {
            "messaging.inbox": "Messages inbox (incl. hostel warden)",
            "complaints.own": "My complaints",
        },
    },
}

ALL_KEYS: list[str] = [k for g in CATEGORIES.values() for k in g["keys"]]

INTENT_PERMISSIONS: dict[str, list[str]] = {
    "greeting": [],
    "overview": [
        "academic.attendance",
        "academic.marks",
        "academic.grades",
        "academic.cgpa",
        "academic.credits",
        "academic.history",
        "hostel.room",
        "hostel.leave",
        "hostel.records",
        "achievements.certs",
    ],
    "attendance": ["academic.attendance"],
    "marks": ["academic.marks", "academic.grades"],
    "grades": ["academic.grades", "academic.marks"],
    "cgpa": ["academic.cgpa", "academic.marks", "academic.credits"],
    "credits": ["academic.credits", "academic.history", "academic.courses"],
    "timetable": ["academic.history", "academic.timetable"],
    "forecast": ["academic.attendance", "academic.marks"],
    "graduation": ["academic.credits", "academic.history", "academic.courses"],
    "leave": ["hostel.leave", "hostel.room"],
    "hostel": ["hostel.room", "hostel.leave", "hostel.records"],
    "complaints": ["hostel.records", "academic.history"],
    "faculty_directory": [],
    "achievements": ["achievements.certs", "achievements.awards", "achievements.activities"],
    "career": ["achievements.certs", "achievements.activities", "academic.history", "academic.courses"],
    "fees": ["financial.fees"],
    "scholarship": ["financial.scholarship"],
    "letter": ["academic.history", "academic.credits", "academic.exams"],
    "workflow": ["hostel.leave"],
}


def catalog_payload() -> list[dict]:
    groups = []
    for gid, g in CATEGORIES.items():
        groups.append(
            {
                "id": gid,
                "label": g["label"],
                "purpose": g["purpose"],
                "permissions": [{"key": k, "label": lab} for k, lab in g["keys"].items()],
            }
        )
    return groups
