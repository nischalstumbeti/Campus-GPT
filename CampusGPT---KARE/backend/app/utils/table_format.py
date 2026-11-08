"""Format structured campus data as clean ASCII / pipe tables for chat."""
from __future__ import annotations

from typing import Any, Sequence


def format_table(headers: Sequence[str], rows: Sequence[Sequence[Any]], title: str = "") -> str:
    """Build a monospace-friendly pipe table. Empty rows → short notice."""
    headers = [str(h) for h in headers]
    clean_rows: list[list[str]] = []
    for row in rows:
        clean_rows.append([("" if v is None else str(v)).strip() for v in row])

    if not clean_rows:
        body = title + ("\n" if title else "") + "(no rows)"
        return body.strip()

    widths = [len(h) for h in headers]
    for row in clean_rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    def fmt_row(vals: Sequence[str]) -> str:
        parts = []
        for i, w in enumerate(widths):
            cell = vals[i] if i < len(vals) else ""
            parts.append(cell.ljust(w))
        return "| " + " | ".join(parts) + " |"

    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    lines = []
    if title:
        lines.append(title)
    lines.append(fmt_row(headers))
    lines.append(sep)
    for row in clean_rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def timetable_table(slots: list[dict], title: str = "Timetable") -> str:
    rows = [
        [
            s.get("day") or "",
            f"{s.get('start_time') or ''}-{s.get('end_time') or ''}",
            s.get("course_name") or s.get("course") or "",
            s.get("faculty") or s.get("faculty_name") or "",
            s.get("room") or s.get("location") or "",
        ]
        for s in slots
    ]
    return format_table(["Day", "Time", "Course", "Faculty", "Room"], rows, title)


def attendance_table(rows_in: list[dict], title: str = "Attendance") -> str:
    rows = [
        [
            r.get("course_name") or r.get("course") or "",
            r.get("present", ""),
            r.get("conducted", ""),
            f"{r.get('percentage', '')}%",
        ]
        for r in rows_in
    ]
    return format_table(["Course", "Present", "Conducted", "Percent"], rows, title)


def marks_table(rows_in: list[dict], title: str = "Marks") -> str:
    rows = [
        [
            r.get("course_name") or r.get("course") or "",
            r.get("assessment") or "",
            r.get("score", r.get("marks", "")),
            r.get("max_score", r.get("max_marks", "")),
        ]
        for r in rows_in
    ]
    return format_table(["Course", "Assessment", "Score", "Max"], rows, title)


def faculty_directory_table(rows_in: list[dict], title: str = "Faculty schedule") -> str:
    rows = [
        [
            r.get("faculty") or "",
            r.get("kind") or "",
            r.get("day") or "",
            f"{r.get('start_time') or r.get('start') or ''}-{r.get('end_time') or r.get('end') or ''}",
            r.get("location") or r.get("cabin") or "",
        ]
        for r in rows_in
    ]
    return format_table(["Faculty", "Type", "Day", "Time", "Location"], rows, title)
