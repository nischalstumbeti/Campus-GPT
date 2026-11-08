"""Attach a question paper to each scheduled exam that does not have one yet."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import ExamSchedule

PAPERS = {
    "CSE501": [
        "Explain the difference between a primary key and a foreign key with an example.",
        "Write a relational schema for a library and show it in third normal form.",
        "What is a transaction? State the ACID properties.",
        "Given tables Student(id, name) and Enrol(student_id, course), write the SQL to list students with no enrolment.",
    ],
    "CSE502": [
        "Compare circuit switching and packet switching.",
        "Explain the TCP three-way handshake.",
        "What is the purpose of a subnet mask? Give an example.",
        "Describe how DNS resolves a hostname.",
    ],
    "CSE503": [
        "Define a deterministic finite automaton and give one for strings ending in 01.",
        "State the pumping lemma for regular languages.",
        "Convert the regular expression (a|b)*abb to an NFA.",
        "What is a context-free grammar? Write one for balanced parentheses.",
    ],
    "CSE505": [
        "Distinguish informed and uninformed search.",
        "Explain the A* algorithm and when its heuristic is admissible.",
        "What is a knowledge-based agent?",
        "Describe overfitting in a simple classifier.",
    ],
}


def _paper(code: str, title: str, exam_type: str, exam_date: str, start: str, venue: str) -> str:
    questions = PAPERS.get(
        code,
        [
            "Answer the questions from the published syllabus for this course.",
            "Show the working for any numerical or design question.",
            "State assumptions before you use them.",
        ],
    )
    lines = [
        "Campus Information System",
        "Question paper",
        "",
        f"Course: {code}  {title}",
        f"Exam: {exam_type}",
        f"Date: {exam_date}    Time: {start}    Venue: {venue}",
        "Max marks: 50",
        "",
        "Answer all questions.",
        "",
    ]
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


async def ensure_exam_papers() -> dict:
    filled = 0
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(ExamSchedule).options(selectinload(ExamSchedule.course)))
        ).scalars().all()
        for exam in rows:
            if (exam.paper_text or "").strip() or not exam.course:
                continue
            exam.paper_text = _paper(
                exam.course.code,
                exam.course.title,
                exam.exam_type,
                exam.exam_date.strftime("%d/%m/%Y"),
                exam.start_time,
                exam.venue,
            )
            filled += 1
        await db.commit()
    return {"ok": True, "filled": filled}
